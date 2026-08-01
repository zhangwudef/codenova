import { useMemo } from 'react'
import ReactMarkdown from 'react-markdown'
import remarkGfm from 'remark-gfm'
import { X, Download, FileText, Bookmark } from 'lucide-react'

interface DocPreviewModalProps {
  open: boolean
  title: string
  content: string
  downloadUrl?: string | null
  objectName?: string
  onClose: () => void
}

export default function DocPreviewModal({
  open,
  title,
  content,
  downloadUrl,
  objectName,
  onClose,
}: DocPreviewModalProps) {
  const wordCount = useMemo(() => {
    if (!content) return 0
    return content.replace(/\s+/g, ' ').trim().length
  }, [content])

  if (!open) return null

  const handleDownloadLocal = () => {
    const blob = new Blob([content], { type: 'text/markdown;charset=utf-8' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = objectName?.split('/').pop() || 'codenova-doc.md'
    document.body.appendChild(a)
    a.click()
    document.body.removeChild(a)
    URL.revokeObjectURL(url)
  }

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-3xl max-h-[85vh] flex flex-col overflow-hidden">
        {/* 头部 */}
        <div className="flex-shrink-0 px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <div className="flex items-center gap-2 min-w-0">
            <div className="w-9 h-9 rounded-lg bg-gradient-to-br from-brand-100 to-indigo-100 flex items-center justify-center flex-shrink-0">
              <FileText size={18} className="text-brand-600" />
            </div>
            <div className="min-w-0">
              <h3 className="text-base font-semibold text-slate-800 truncate">{title}</h3>
              <p className="text-xs text-slate-500">
                {wordCount} 字符 · Markdown
              </p>
            </div>
          </div>
          <button
            onClick={onClose}
            className="p-1.5 rounded-lg hover:bg-slate-100 transition-colors flex-shrink-0"
            aria-label="关闭"
          >
            <X size={20} className="text-slate-500" />
          </button>
        </div>

        {/* 工具栏 */}
        <div className="flex-shrink-0 px-6 py-2 border-b border-slate-100 bg-slate-50 flex items-center justify-end gap-2">
          <button
            onClick={handleDownloadLocal}
            className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-slate-600 hover:bg-slate-200 transition-colors"
            title="本地下载 Markdown"
          >
            <Download size={14} />
            下载
          </button>
          {downloadUrl && (
            <a
              href={downloadUrl}
              target="_blank"
              rel="noopener noreferrer"
              className="flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-brand-600 bg-brand-50 hover:bg-brand-100 transition-colors"
              title="从 MinIO 下载（预签名 URL）"
            >
              <Bookmark size={14} />
              持久化版本
            </a>
          )}
        </div>

        {/* 内容预览 */}
        <div className="flex-1 overflow-auto px-6 py-4">
          <article className="prose prose-slate prose-sm max-w-none">
            <ReactMarkdown remarkPlugins={[remarkGfm]}>{content}</ReactMarkdown>
          </article>
        </div>
      </div>
    </div>
  )
}
