/** 主题与设置 Store: 暗色模式 + API Key 管理 */
import { create } from 'zustand'
import { persist, createJSONStorage } from 'zustand/middleware'
import { setApiKey as setApiApiKey } from '../api'

export type ThemeMode = 'light' | 'dark' | 'system'

interface ThemeState {
  mode: ThemeMode
  resolved: 'light' | 'dark'  // 实际生效值（system 时根据 prefers-color-scheme 解析）
  setMode: (mode: ThemeMode) => void
  toggle: () => void
  applyToDocument: () => void
}

export const useThemeStore = create<ThemeState>()(
  persist(
    (set, get) => ({
      mode: 'system',
      resolved: 'light',
      setMode: (mode) => {
        const resolved = resolveTheme(mode)
        set({ mode, resolved })
        get().applyToDocument()
      },
      toggle: () => {
        const current = get().resolved
        const next: ThemeMode = current === 'dark' ? 'light' : 'dark'
        get().setMode(next)
      },
      applyToDocument: () => {
        const { resolved } = get()
        if (typeof document !== 'undefined') {
          const root = document.documentElement
          if (resolved === 'dark') {
            root.classList.add('dark')
          } else {
            root.classList.remove('dark')
          }
        }
      },
    }),
    {
      name: 'codenova-theme',
      storage: createJSONStorage(() => localStorage),
      onRehydrateStorage: () => (state) => {
        // 从存储恢复后立即应用到 DOM
        if (state) {
          state.resolved = resolveTheme(state.mode)
          state.applyToDocument()
        }
      },
    }
  )
)

function resolveTheme(mode: ThemeMode): 'light' | 'dark' {
  if (mode === 'system') {
    if (typeof window !== 'undefined' && window.matchMedia) {
      return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light'
    }
    return 'light'
  }
  return mode
}

// 监听系统主题变化（仅 system 模式）
if (typeof window !== 'undefined' && window.matchMedia) {
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    const state = useThemeStore.getState()
    if (state.mode === 'system') {
      const resolved = resolveTheme('system')
      state.setMode('system')  // 触发重新应用
      useThemeStore.setState({ resolved })
      state.applyToDocument()
    }
  })
}

// ------------------------------------------------------------------
// API Key 设置 Store（持久化）
// ------------------------------------------------------------------
interface ApiKeyState {
  apiKey: string | null
  setApiKey: (key: string | null) => void
  clear: () => void
}

export const useApiKeyStore = create<ApiKeyState>()(
  persist(
    (set) => ({
      apiKey: null,
      setApiKey: (key) => {
        setApiApiKey(key)  // 同步到 api 模块的 localStorage
        set({ apiKey: key })
      },
      clear: () => {
        setApiApiKey(null)
        set({ apiKey: null })
      },
    }),
    {
      name: 'codenova-apikey',
      storage: createJSONStorage(() => localStorage),
    }
  )
)

// ------------------------------------------------------------------
// 仓库历史（localStorage 持久化）
// ------------------------------------------------------------------
export interface RepoHistoryEntry {
  url: string
  branch?: string
  visitedAt: number  // 时间戳
}

interface RepoHistoryState {
  entries: RepoHistoryEntry[]
  add: (url: string, branch?: string) => void
  remove: (url: string) => void
  clear: () => void
  MAX_ENTRIES: number
}

const MAX_HISTORY = 10

export const useRepoHistoryStore = create<RepoHistoryState>()(
  persist(
    (set, get) => ({
      entries: [],
      MAX_ENTRIES: MAX_HISTORY,
      add: (url, branch) => {
        if (!url) return
        const existing = get().entries.filter((e) => e.url !== url)
        const entry: RepoHistoryEntry = { url, branch, visitedAt: Date.now() }
        const entries = [entry, ...existing].slice(0, MAX_HISTORY)
        set({ entries })
      },
      remove: (url) => {
        set({ entries: get().entries.filter((e) => e.url !== url) })
      },
      clear: () => set({ entries: [] }),
    }),
    {
      name: 'codenova-repo-history',
      storage: createJSONStorage(() => localStorage),
      // 仅保留最近 30 天的记录
      partialize: (state) => ({
        entries: state.entries.filter(
          (e) => Date.now() - e.visitedAt < 30 * 24 * 60 * 60 * 1000
        ),
      }),
    }
  )
)
