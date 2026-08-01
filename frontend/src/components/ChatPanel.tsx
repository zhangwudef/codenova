import { useState, useRef, useEffect } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import {
  Send,
  Sparkles,
  Loader2,
  Trash2,
  Pin,
  PinOff,
  ExternalLink,
  FileCode,
  ChevronDown,
  Bot,
  User,
  Square,
  Download,
  Bookmark,
} from 'lucide-react'
import { useQAStore, type QAReference } from '../stores/qaStore'
import { useRepoStore } from '../stores/repoStore'
import DocPreviewModal from './DocPreviewModal'

// 消息引用卡片组件
function ReferenceCard({ reference, onJump }: { reference: QAReference; onJump?: () => void }) {
  const [expanded, setExpanded] = useState(false)
  
  return (
    <div className="mt-2 rounded-lg border border-slate-200 bg-slate-50 overflow-hidden">
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex w-full items-center justify-between px-3 py-2 hover:bg-slate-100 transition-colors"
      >
        <div className="flex items-center gap-2 min-w-0">
          <FileCode size={14} className="text-brand-500 flex-shrink-0" />
          <span className="text-xs font-mono text-slate-600 truncate">{reference.file_path}</span>
          <span className="text-xs text-slate-400 flex-shrink-0">
            L{reference.line_start}-{reference.line_end}
          </span>
        </div>
        <div className="flex items-center gap-1 flex-shrink-0">
          <button
            onClick={(e) => { e.stopPropagation(); onJump?.() }}
            className="p-1 rounded hover:bg-brand-100 text-brand-600 transition-colors"
            title="跳转到源码位置"
          >
            <ExternalLink size={12} />
          </button>
          <ChevronDown 
            size={12} 
            className={`text-slate-400 transition-transform ${expanded ? 'rotate-180' : ''}`} 
          />
        </div>
      </button>
      {expanded && (
        <pre className="px-3 py-2 border-t border-slate-200 bg-white text-xs font-mono text-slate-600 overflow-x-auto max-h-40">
          {reference.code}
        </pre>
      )}
    </div>
  )
}

// 消息气泡组件
function MessageBubble({ 
  role, 
  content, 
  references, 
  isStreaming,
  isPinned,
  timestamp,
  onPin,
  onJumpToSource,
}: {
  role: 'user' | 'assistant'
  content: string
  references?: QAReference[]
  isStreaming?: boolean
  isPinned?: boolean
  timestamp: number
  onPin?: () => void
  onJumpToSource?: (reference: QAReference) => void
}) {
  const isUser = role === 'user'
  
  return (
    <div className={`flex gap-3 ${isUser ? 'flex-row-reverse' : 'flex-row'}`}>
      {/* 头像 */}
      <div className={`flex-shrink-0 w-8 h-8 rounded-full flex items-center justify-center ${
        isUser 
          ? 'bg-brand-100 text-brand-600' 
          : 'bg-gradient-to-br from-brand-500 to-indigo-500 text-white'
      }`}>
        {isUser ? <User size={16} /> : <Bot size={16} />}
      </div>
      
      {/* 消息内容 */}
      <div className={`flex-1 min-w-0 max-w-[85%] ${isUser ? 'items-end' : 'items-start'}`}>
        <div className={`relative rounded-2xl px-4 py-3 ${
          isUser 
            ? 'bg-brand-600 text-white rounded-tr-sm' 
            : 'bg-white border border-slate-200 rounded-tl-sm shadow-sm'
        }`}>
          {/* 固定标记 */}
          {isPinned && (
            <div className="absolute -top-2 -left-2 bg-amber-500 text-white text-xs px-2 py-0.5 rounded-full flex items-center gap-1">
              <Pin size={10} />
              已固化
            </div>
          )}
          
          {/* 消息内容 */}
          <div className={`prose prose-sm max-w-none ${isUser ? 'prose-invert' : ''}`}>
            {isStreaming && !content ? (
              <div className="flex items-center gap-1 text-slate-400">
                <Loader2 size={14} className="animate-spin" />
                <span>思考中...</span>
              </div>
            ) : (
              <>
                <ReactMarkdown
                  remarkPlugins={[remarkGfm]}
                  className={isUser ? 'text-white' : 'text-slate-700'}
                  components={{
                    code: ({ className, children }) => {
                      const isInline = !className
                      if (isInline) {
                        return <code className="px-1.5 py-0.5 rounded bg-slate-100 text-brand-600 font-mono text-xs">{children}</code>
                      }
                      return (
                        <code className={`block p-3 rounded-lg bg-slate-900 text-slate-100 font-mono text-xs overflow-x-auto ${className}`}>
                          {children}
                        </code>
                      )
                    },
                  }}
                >
                  {content}
                </ReactMarkdown>
                {isStreaming && content && (
                  <span className="inline-block w-1.5 h-4 ml-0.5 bg-brand-500 animate-pulse align-middle" aria-hidden />
                )}
              </>
            )}
          </div>
          
          {/* 引用卡片 */}
          {!isUser && references && references.length > 0 && (
            <div className="mt-3 pt-3 border-t border-slate-200">
              <div className="text-xs text-slate-500 mb-2 flex items-center gap-1">
                <FileCode size={12} />
                参考来源 ({references.length})
              </div>
              <div className="space-y-2">
                {references.map((ref, idx) => (
                  <ReferenceCard 
                    key={idx} 
                    reference={ref} 
                    onJump={() => onJumpToSource?.(ref)}
                  />
                ))}
              </div>
            </div>
          )}
        </div>
        
        {/* 消息元信息和操作 */}
        <div className={`flex items-center gap-2 mt-1 ${isUser ? 'flex-row-reverse' : ''}`}>
          <span className="text-xs text-slate-400">
            {new Date(timestamp).toLocaleTimeString('zh-CN', { hour: '2-digit', minute: '2-digit' })}
          </span>
          {!isUser && onPin && (
            <button
              onClick={onPin}
              className="p-1 rounded hover:bg-slate-100 text-slate-400 hover:text-amber-500 transition-colors"
              title={isPinned ? '取消固化' : '固化为文档'}
            >
              {isPinned ? <PinOff size={12} /> : <Pin size={12} />}
            </button>
          )}
        </div>
      </div>
    </div>
  )
}

// 主问答面板组件
export default function ChatPanel({ 
  onJumpToSource 
}: { 
  onJumpToSource?: (filePath: string, lineStart: number, lineEnd: number) => void 
}) {
  const messagesEndRef = useRef<HTMLDivElement>(null)
  const inputRef = useRef<HTMLTextAreaElement>(null)
  
  const messages = useQAStore(state => state.messages)
  const isLoading = useQAStore(state => state.isLoading)
  const isPersisting = useQAStore(state => state.isPersisting)
  const lastPersistedDoc = useQAStore(state => state.lastPersistedDoc)
  const currentQuestion = useQAStore(state => state.currentQuestion)
  const setCurrentQuestion = useQAStore(state => state.setCurrentQuestion)
  const sendQuestion = useQAStore(state => state.sendQuestion)
  const stopStreaming = useQAStore(state => state.stopStreaming)
  const persistAsDoc = useQAStore(state => state.persistAsDoc)
  const clearMessages = useQAStore(state => state.clearMessages)
  const pinMessage = useQAStore(state => state.pinMessage)
  const unpinMessage = useQAStore(state => state.unpinMessage)
  
  const repoUrl = useRepoStore(state => state.repoUrl)

  // 自动滚动到最新消息
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  // 示例问题
  const exampleQuestions = [
    '这个项目的入口文件是哪个？',
    '订单超时取消在哪里实现？',
    '分析一下 API 认证流程',
    '数据库连接是如何管理的？',
  ]

  const handleSend = async () => {
    if (!currentQuestion.trim() || isLoading) return
    await sendQuestion(currentQuestion, repoUrl)
  }

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      handleSend()
    }
  }

  const handleJumpToSource = (reference: QAReference) => {
    onJumpToSource?.(reference.file_path, reference.line_start, reference.line_end)
  }

  // 一键固化为文档
  const [previewOpen, setPreviewOpen] = useState(false)
  const handlePersist = async () => {
    const result = await persistAsDoc(repoUrl, true)
    if (result) {
      // 弹出预览模态框，由用户决定是否下载
      setPreviewOpen(true)
    }
  }

  // 本地下载上一次固化的文档
  const handleDownloadLocal = () => {
    const doc = lastPersistedDoc
    if (!doc) return
    const blob = new Blob([doc.content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = doc.object_name.split('/').pop() || 'codenova-qa.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 头部 */}
      <div className="flex items-center justify-between px-4 py-3 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          <Sparkles size={18} className="text-brand-500" />
          <span className="text-sm font-semibold text-slate-700">智能问答</span>
          {messages.length > 0 && (
            <span className="text-xs text-slate-500 bg-slate-200 px-2 py-0.5 rounded">
              {messages.length} 条消息
            </span>
          )}
        </div>
        <div className="flex items-center gap-1">
          <button
            onClick={handlePersist}
            disabled={isPersisting || messages.filter(m => m.role === 'assistant' && !m.isStreaming && m.content).length === 0}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-brand-600 hover:bg-brand-50 transition-colors disabled:cursor-not-allowed disabled:opacity-50"
            title="将选中的问答固化为 Markdown 文档（持久化到 MinIO）"
          >
            {isPersisting ? <Loader2 size={14} className="animate-spin" /> : <Bookmark size={14} />}
            {isPersisting ? '固化中...' : '固化'}
          </button>
          {lastPersistedDoc && (
            <button
              onClick={handleDownloadLocal}
              className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-600 hover:bg-slate-200 transition-colors"
              title="下载上次固化的文档"
            >
              <Download size={14} />
            </button>
          )}
          <button
            onClick={clearMessages}
            className="flex items-center gap-1 px-2 py-1 rounded text-xs text-slate-500 hover:bg-red-50 hover:text-red-500 transition-colors"
            title="清空对话"
          >
            <Trash2 size={14} />
          </button>
        </div>
      </div>

      {/* 消息列表 */}
      <div className="flex-1 overflow-auto p-4 space-y-4">
        {messages.length === 0 ? (
          <div className="flex flex-col items-center justify-center h-full text-center">
            <div className="w-16 h-16 rounded-full bg-gradient-to-br from-brand-100 to-indigo-100 flex items-center justify-center mb-4">
              <Sparkles size={32} className="text-brand-500" />
            </div>
            <h3 className="text-lg font-semibold text-slate-700 mb-2">开始与 AI 对话</h3>
            <p className="text-sm text-slate-500 mb-6 max-w-xs">
              选择一个问题开始，或者输入你想了解的内容
            </p>
            <div className="space-y-2 w-full max-w-xs">
              {exampleQuestions.map((question, idx) => (
                <button
                  key={idx}
                  onClick={() => setCurrentQuestion(question)}
                  className="w-full text-left px-4 py-3 rounded-xl border border-slate-200 bg-white hover:border-brand-300 hover:bg-brand-50 transition-all text-sm text-slate-600 hover:text-brand-700"
                >
                  {question}
                </button>
              ))}
            </div>
          </div>
        ) : (
          <>
            {messages.map((message) => (
              <MessageBubble
                key={message.id}
                role={message.role}
                content={message.content}
                references={message.references}
                isStreaming={message.isStreaming}
                isPinned={message.isPinned}
                timestamp={message.timestamp}
                onPin={
                  message.role === 'assistant' && !message.isStreaming
                    ? () => message.isPinned ? unpinMessage(message.id) : pinMessage(message.id)
                    : undefined
                }
                onJumpToSource={handleJumpToSource}
              />
            ))}
          </>
        )}
        <div ref={messagesEndRef} />
      </div>

      {/* 输入区域 */}
      <div className="border-t border-slate-200 bg-white p-4">
        <div className="flex items-end gap-2">
          <div className="flex-1 relative">
            <textarea
              ref={inputRef}
              value={currentQuestion}
              onChange={(e) => setCurrentQuestion(e.target.value)}
              onKeyDown={handleKeyDown}
              placeholder="输入你的问题，Enter 发送，Shift+Enter 换行..."
              className="w-full resize-none rounded-xl border border-slate-200 bg-slate-50 px-4 py-3 pr-12 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
              rows={2}
              disabled={isLoading}
            />
          </div>
          <button
            onClick={isLoading ? stopStreaming : handleSend}
            disabled={!isLoading && !currentQuestion.trim()}
            className={`flex-shrink-0 w-10 h-10 rounded-xl text-white flex items-center justify-center transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${
              isLoading
                ? 'bg-red-500 hover:bg-red-600'
                : 'bg-brand-600 hover:bg-brand-700'
            }`}
            title={isLoading ? '停止生成' : '发送'}
          >
            {isLoading ? <Square size={16} fill="currentColor" /> : <Send size={20} />}
          </button>
        </div>
        {!repoUrl && (
          <p className="text-xs text-amber-500 mt-2 flex items-center gap-1">
            <Sparkles size={12} />
            请先在左侧解析一个仓库
          </p>
        )}
      </div>

      {/* 文档预览模态框 */}
      <DocPreviewModal
        open={previewOpen}
        title="问答沉淀文档"
        content={lastPersistedDoc?.content || ''}
        downloadUrl={lastPersistedDoc?.download_url}
        objectName={lastPersistedDoc?.object_name}
        onClose={() => setPreviewOpen(false)}
      />
    </div>
  )
}