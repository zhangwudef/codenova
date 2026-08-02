/**
 * 设置面板: 主题切换 + API Key 管理 + 仓库历史
 */
import { useState } from 'react'
import { Settings, Sun, Moon, Monitor, Key, Trash2, Clock, X } from 'lucide-react'
import { useThemeStore, useApiKeyStore, useRepoHistoryStore, type ThemeMode } from '../stores/themeStore'

interface SettingsPanelProps {
  open: boolean
  onClose: () => void
}

export function SettingsPanel({ open, onClose }: SettingsPanelProps) {
  const { mode, setMode } = useThemeStore()
  const { apiKey, setApiKey, clear: clearApiKey } = useApiKeyStore()
  const { entries: history, remove: removeHistory, clear: clearHistory } = useRepoHistoryStore()
  const [keyInput, setKeyInput] = useState(apiKey || '')

  if (!open) return null

  const themeOptions: Array<{ value: ThemeMode; label: string; icon: typeof Sun }> = [
    { value: 'light', label: '浅色', icon: Sun },
    { value: 'dark', label: '深色', icon: Moon },
    { value: 'system', label: '跟随系统', icon: Monitor },
  ]

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/40 backdrop-blur-sm">
      <div className="bg-white dark:bg-zinc-900 rounded-xl shadow-2xl w-full max-w-lg mx-4 max-h-[85vh] overflow-y-auto">
        {/* 头部 */}
        <div className="flex items-center justify-between p-5 border-b border-zinc-200 dark:border-zinc-800">
          <h2 className="text-lg font-semibold flex items-center gap-2 text-zinc-900 dark:text-zinc-100">
            <Settings size={20} /> 设置
          </h2>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-zinc-100 dark:hover:bg-zinc-800 text-zinc-500 hover:text-zinc-700 dark:hover:text-zinc-300"
          >
            <X size={18} />
          </button>
        </div>

        <div className="p-5 space-y-6">
          {/* 主题 */}
          <section>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3 flex items-center gap-2">
              <Sun size={16} /> 外观
            </h3>
            <div className="grid grid-cols-3 gap-2">
              {themeOptions.map((opt) => {
                const Icon = opt.icon
                const active = mode === opt.value
                return (
                  <button
                    key={opt.value}
                    onClick={() => setMode(opt.value)}
                    className={`flex flex-col items-center gap-1 py-3 rounded-lg border transition-colors ${
                      active
                        ? 'border-blue-500 bg-blue-50 dark:bg-blue-900/30 text-blue-600 dark:text-blue-400'
                        : 'border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800'
                    }`}
                  >
                    <Icon size={18} />
                    <span className="text-xs">{opt.label}</span>
                  </button>
                )
              })}
            </div>
          </section>

          {/* API Key */}
          <section>
            <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 mb-3 flex items-center gap-2">
              <Key size={16} /> API Key
            </h3>
            <p className="text-xs text-zinc-500 dark:text-zinc-400 mb-2">
              当后端启用鉴权时，请在此填入 API Key。本地开发通常无需填写。
            </p>
            <div className="flex gap-2">
              <input
                type="password"
                value={keyInput}
                onChange={(e) => setKeyInput(e.target.value)}
                placeholder="sk-..."
                className="flex-1 px-3 py-2 text-sm rounded-lg border border-zinc-200 dark:border-zinc-700 bg-white dark:bg-zinc-800 text-zinc-900 dark:text-zinc-100 focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
              <button
                onClick={() => setApiKey(keyInput || null)}
                className="px-4 py-2 text-sm rounded-lg bg-blue-600 hover:bg-blue-700 text-white font-medium"
              >
                保存
              </button>
              {apiKey && (
                <button
                  onClick={() => {
                    clearApiKey()
                    setKeyInput('')
                  }}
                  className="px-3 py-2 text-sm rounded-lg border border-zinc-200 dark:border-zinc-700 text-zinc-600 dark:text-zinc-400 hover:bg-zinc-50 dark:hover:bg-zinc-800"
                  title="清除 API Key"
                >
                  <Trash2 size={14} />
                </button>
              )}
            </div>
            {apiKey && (
              <p className="text-xs text-green-600 dark:text-green-400 mt-2">
                ✓ API Key 已设置
              </p>
            )}
          </section>

          {/* 仓库历史 */}
          {history.length > 0 && (
            <section>
              <div className="flex items-center justify-between mb-3">
                <h3 className="text-sm font-medium text-zinc-700 dark:text-zinc-300 flex items-center gap-2">
                  <Clock size={16} /> 仓库历史
                </h3>
                <button
                  onClick={clearHistory}
                  className="text-xs text-zinc-400 hover:text-red-500 flex items-center gap-1"
                >
                  <Trash2 size={12} /> 清空
                </button>
              </div>
              <ul className="space-y-1 max-h-40 overflow-y-auto">
                {history.map((entry) => (
                  <li
                    key={entry.url}
                    className="flex items-center justify-between gap-2 px-3 py-2 rounded-lg bg-zinc-50 dark:bg-zinc-800/50 text-sm"
                  >
                    <div className="flex-1 truncate">
                      <span className="text-zinc-700 dark:text-zinc-300">{entry.url}</span>
                      {entry.branch && (
                        <span className="text-zinc-400 ml-2">#{entry.branch}</span>
                      )}
                    </div>
                    <button
                      onClick={() => removeHistory(entry.url)}
                      className="text-zinc-400 hover:text-red-500 flex-shrink-0"
                    >
                      <X size={14} />
                    </button>
                  </li>
                ))}
              </ul>
            </section>
          )}
        </div>
      </div>
    </div>
  )
}
