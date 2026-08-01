import { create } from 'zustand'
import { persist } from 'zustand/middleware'
import {
  api,
  type QAAnswer,
  type QAQuestion,
  type QAPersistMessage,
  type QAPersistResult,
  type RetrievedChunk,
} from '../api'

export interface QAReference {
  file_path: string
  line_start: number
  line_end: number
  code: string
}

export interface QAMessage {
  id: string
  role: 'user' | 'assistant'
  content: string
  timestamp: number
  references?: QAReference[]
  isStreaming?: boolean
  isPinned?: boolean
  answer?: QAAnswer
}

export interface QAState {
  // 问答会话
  messages: QAMessage[]
  isLoading: boolean
  isPersisting: boolean
  currentQuestion: string
  error: string | null
  lastPersistedDoc: QAPersistResult | null
  // 当前流式请求的 abort 句柄（用于一键停止）
  _streamController: { abort: () => void } | null

  // 操作方法
  setCurrentQuestion: (q: string) => void
  addMessage: (message: QAMessage) => void
  updateMessage: (id: string, updates: Partial<QAMessage>) => void
  sendQuestion: (question: string, repoUrl?: string) => Promise<void>
  stopStreaming: () => void
  persistAsDoc: (repoUrl?: string, pinnedOnly?: boolean) => Promise<QAPersistResult | null>
  clearMessages: () => void
  pinMessage: (id: string) => void
  unpinMessage: (id: string) => void
  setError: (error: string | null) => void
}

export const useQAStore = create<QAState>()(
  persist(
    (set, get) => ({
      messages: [],
      isLoading: false,
      isPersisting: false,
      currentQuestion: '',
      error: null,
      lastPersistedDoc: null,
      _streamController: null,

  setCurrentQuestion: (q: string) => set({ currentQuestion: q }),

  addMessage: (message: QAMessage) => {
    set(state => ({
      messages: [...state.messages, message]
    }))
  },

  updateMessage: (id: string, updates: Partial<QAMessage>) => {
    set(state => ({
      messages: state.messages.map(msg =>
        msg.id === id ? { ...msg, ...updates } : msg
      )
    }))
  },

  sendQuestion: async (question: string, repoUrl?: string) => {
    const state = get()

    // 添加用户消息
    const userMessage: QAMessage = {
      id: `user-${Date.now()}`,
      role: 'user',
      content: question,
      timestamp: Date.now(),
    }

    // 添加临时助手消息（用于流式显示）
    const assistantId = `assistant-${Date.now()}`
    const assistantMessage: QAMessage = {
      id: assistantId,
      role: 'assistant',
      content: '',
      timestamp: Date.now(),
      isStreaming: true,
    }

    set({
      messages: [...state.messages, userMessage, assistantMessage],
      isLoading: true,
      currentQuestion: '',
      error: null,
    })

    const payload: QAQuestion = {
      question,
      repo_url: repoUrl || undefined,
    }

    const stream = api.askQuestionStream(payload)
    set({ _streamController: stream })

    let accumulated = ''
    let references: QAReference[] | undefined
    let finalAnswer: QAAnswer | undefined

    try {
      for await (const event of stream as AsyncIterable<Record<string, any>>) {
        const type = event?.type

        if (type === 'sources') {
          // 检索完成，推送来源
          references = extractReferences((event.sources || []) as RetrievedChunk[])
          get().updateMessage(assistantId, { references })
        } else if (type === 'delta') {
          // 增量文本
          accumulated += event.content || ''
          get().updateMessage(assistantId, { content: accumulated, isStreaming: true })
        } else if (type === 'done') {
          // 完整答案
          finalAnswer = event.answer as QAAnswer
          if (finalAnswer?.answer && !accumulated) {
            accumulated = finalAnswer.answer
          }
          if (!references && finalAnswer?.sources) {
            references = extractReferences(finalAnswer.sources)
          }
          get().updateMessage(assistantId, {
            content: accumulated,
            references,
            isStreaming: false,
            answer: finalAnswer,
          })
        } else if (type === 'error') {
          const errMsg = event.message || '未知错误'
          get().updateMessage(assistantId, {
            content: accumulated || `抱歉，出现了错误：${errMsg}`,
            isStreaming: false,
          })
          set({ error: errMsg })
        }
      }
      // 流正常结束但未收到 done 事件时，也置为完成
      const cur = get().messages.find(m => m.id === assistantId)
      if (cur?.isStreaming) {
        get().updateMessage(assistantId, { isStreaming: false })
      }
    } catch (e) {
      // AbortError 是用户主动取消，不显示错误
      if ((e as Error).name === 'AbortError') {
        get().updateMessage(assistantId, {
          content: accumulated + (accumulated ? '\n\n_(已停止生成)_' : '_(已停止生成)_'),
          isStreaming: false,
        })
      } else {
        get().updateMessage(assistantId, {
          content: accumulated || `抱歉，出现了错误：${(e as Error).message}`,
          isStreaming: false,
        })
        set({ error: (e as Error).message })
      }
    } finally {
      set({ isLoading: false, _streamController: null })
    }
  },

  stopStreaming: () => {
    const ctrl = get()._streamController
    if (ctrl) {
      ctrl.abort()
    }
  },

  persistAsDoc: async (repoUrl?: string, pinnedOnly = true) => {
    const { messages } = get()
    // 优先取 pinned 的 assistant 消息；若没有则取所有非流式 assistant 消息
    let target = pinnedOnly ? messages.filter(m => m.isPinned) : []
    if (target.length === 0) {
      target = messages.filter(m => m.role === 'assistant' && !m.isStreaming && m.content)
    }
    if (target.length === 0) {
      set({ error: '没有可固化的消息' })
      return null
    }

    // 配对前一条用户问题（若存在）
    const persistMessages: QAPersistMessage[] = []
    for (const msg of target) {
      const idx = messages.findIndex(m => m.id === msg.id)
      if (idx > 0 && messages[idx - 1].role === 'user') {
        const userMsg = messages[idx - 1]
        persistMessages.push({
          role: 'user',
          content: userMsg.content,
          timestamp: userMsg.timestamp,
        })
      }
      persistMessages.push({
        role: 'assistant',
        content: msg.content,
        timestamp: msg.timestamp,
        references: msg.references,
      })
    }

    set({ isPersisting: true, error: null })
    try {
      const result = await api.persistQA({
        title: 'CodeNova 问答沉淀',
        repo_url: repoUrl,
        messages: persistMessages,
        pinned_only: pinnedOnly,
      })
      set({ isPersisting: false, lastPersistedDoc: result })
      return result
    } catch (e) {
      set({ isPersisting: false, error: (e as Error).message })
      return null
    }
  },

  clearMessages: () => {
    set({ messages: [], error: null })
  },

  pinMessage: (id: string) => {
    set(state => ({
      messages: state.messages.map(msg =>
        msg.id === id ? { ...msg, isPinned: true } : msg
      )
    }))
  },

  unpinMessage: (id: string) => {
    set(state => ({
      messages: state.messages.map(msg =>
        msg.id === id ? { ...msg, isPinned: false } : msg
      )
    }))
  },

  setError: (error: string | null) => set({ error }),
    }),
    {
      name: 'codenova-qa-history',
      // 仅持久化消息列表与固化结果，不持久化瞬时状态
      partialize: (state) => ({
        messages: state.messages,
        lastPersistedDoc: state.lastPersistedDoc,
      }),
    }
  )
)

// 从检索结果中提取引用信息
function extractReferences(sources: RetrievedChunk[]): QAReference[] {
  return sources.map(source => ({
    file_path: source.metadata.file_path,
    line_start: source.metadata.start_line || 1,
    line_end: source.metadata.end_line || 1,
    code: source.content.slice(0, 200), // 截取前200字符用于预览
  }))
}
