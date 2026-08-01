import { useState, useEffect, useRef } from 'react'
import { createHighlighter, type Highlighter, type BundledLanguage } from 'shiki'
import { FileText, Copy, Check } from 'lucide-react'
import type { FileInfo, CodeChunk } from '../api'
import { useRepoStore } from '../stores/repoStore'

interface CodePreviewProps {
  file: FileInfo | null
  onChunkSelect?: (chunk: CodeChunk) => void
}

// 语言映射
const LANGUAGE_MAP: Record<string, BundledLanguage> = {
  'python': 'python',
  'javascript': 'javascript',
  'typescript': 'typescript',
  'java': 'java',
  'go': 'go',
  'rust': 'rust',
  'html': 'html',
  'css': 'css',
  'json': 'json',
  'yaml': 'yaml',
  'markdown': 'markdown',
  'bash': 'bash',
  'shell': 'bash',
}

export default function CodePreview({ file, onChunkSelect }: CodePreviewProps) {
  const [highlighter, setHighlighter] = useState<Highlighter | null>(null)
  const [highlightedCode, setHighlightedCode] = useState('')
  const [copied, setCopied] = useState(false)
  const [activeLine, setActiveLine] = useState<number | null>(null)
  const codeRef = useRef<HTMLPreElement>(null)
  
  const selectChunk = useRepoStore(state => state.selectChunk)
  const selectedChunk = useRepoStore(state => state.selectedChunk)

  // 初始化 Shiki
  useEffect(() => {
    let mounted = true
    createHighlighter({
      themes: ['github-light'],
      langs: ['python', 'javascript', 'typescript', 'java', 'go', 'rust', 'html', 'css', 'json', 'yaml', 'markdown', 'bash'],
    }).then(h => {
      if (mounted) setHighlighter(h)
    })
    return () => { mounted = false }
  }, [])

  // 高亮代码
  useEffect(() => {
    if (!file || !highlighter) {
      setHighlightedCode('')
      return
    }

    const lang = LANGUAGE_MAP[file.language] || 'plaintext'
    const code = file.chunks.map(c => c.content).join('\n')
    
    try {
      const html = highlighter.codeToHtml(code, {
        lang: lang as any,
        theme: 'github-light',
      })
      setHighlightedCode(html)
    } catch (e) {
      // 如果语言不支持，使用纯文本
      const html = highlighter.codeToHtml(code, {
        lang: 'plaintext',
        theme: 'github-light',
      })
      setHighlightedCode(html)
    }
  }, [file, highlighter])

  // 复制代码
  const handleCopy = async () => {
    if (!file) return
    const code = file.chunks.map(c => c.content).join('\n')
    await navigator.clipboard.writeText(code)
    setCopied(true)
    setTimeout(() => setCopied(false), 2000)
  }

  // 点击代码块
  const handleChunkClick = (chunk: CodeChunk) => {
    selectChunk(chunk)
    onChunkSelect?.(chunk)
    setActiveLine(chunk.start_line)
    
    // 滚动到代码块位置
    if (codeRef.current) {
      const lineElements = codeRef.current.querySelectorAll('[data-line]')
      const targetLine = lineElements[chunk.start_line - 1]
      if (targetLine) {
        targetLine.scrollIntoView({ behavior: 'smooth', block: 'center' })
      }
    }
  }

  if (!file) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-8 text-slate-400">
        <FileText size={64} className="mb-4 opacity-30" />
        <p className="text-sm">请从左侧选择一个文件查看代码</p>
      </div>
    )
  }

  const code = file.chunks.map(c => c.content).join('\n')
  const totalLines = code.split('\n').length

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 文件信息栏 */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-slate-200 bg-slate-50">
        <div className="flex items-center gap-2">
          <FileText size={16} className="text-slate-500" />
          <span className="text-sm font-medium text-slate-700 font-mono">{file.path}</span>
          <span className="text-xs px-1.5 py-0.5 rounded bg-slate-200 text-slate-600">
            {file.language}
          </span>
        </div>
        <div className="flex items-center gap-3 text-xs text-slate-500">
          <span>{totalLines} 行</span>
          <span>{file.symbol_count} 符号</span>
          <span>{(file.size_bytes / 1024).toFixed(1)} KB</span>
          <button
            onClick={handleCopy}
            className="flex items-center gap-1 px-2 py-1 rounded hover:bg-slate-200 transition-colors"
          >
            {copied ? <Check size={14} className="text-green-500" /> : <Copy size={14} />}
            {copied ? '已复制' : '复制'}
          </button>
        </div>
      </div>

      {/* 代码区域 */}
      <div className="flex-1 overflow-auto">
        <div className="flex min-h-full">
          {/* 行号栏 */}
          <div className="flex-shrink-0 w-12 bg-slate-50 border-r border-slate-200 py-3 text-right pr-2 font-mono text-xs text-slate-400 select-none">
            {Array.from({ length: totalLines }, (_, i) => (
              <div
                key={i}
                className={`leading-6 ${activeLine === i + 1 ? 'text-brand-500 font-medium' : ''}`}
              >
                {i + 1}
              </div>
            ))}
          </div>

          {/* 高亮代码 */}
          <div className="flex-1 relative">
            <pre
              ref={codeRef}
              className="p-3 font-mono text-sm leading-6 overflow-x-auto"
              style={{ margin: 0 }}
            >
              <code
                dangerouslySetInnerHTML={{ __html: highlightedCode || escapeHtml(code) }}
              />
            </pre>

            {/* 代码块导航 */}
            {file.chunks.length > 0 && (
              <div className="sticky top-0 bg-white/95 backdrop-blur-sm border-b border-slate-100 px-3 py-2">
                <div className="flex items-center gap-2 text-xs text-slate-500 mb-2">
                  <span>代码符号导航</span>
                </div>
                <div className="flex flex-wrap gap-1.5">
                  {file.chunks.map((chunk, idx) => (
                    <button
                      key={idx}
                      onClick={() => handleChunkClick(chunk)}
                      className={`px-2 py-1 rounded text-xs font-mono transition-colors ${
                        selectedChunk?.qualified_name === chunk.qualified_name
                          ? 'bg-brand-100 text-brand-700'
                          : 'bg-slate-100 text-slate-600 hover:bg-slate-200'
                      }`}
                      title={`${chunk.qualified_name} (${chunk.start_line}-${chunk.end_line})`}
                    >
                      <span className="text-slate-400">{chunk.symbol_type}:</span>
                      <span className="ml-1">{chunk.symbol_name}</span>
                    </button>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      </div>
    </div>
  )
}

// HTML 转义
function escapeHtml(text: string): string {
  const div = document.createElement('div')
  div.textContent = text
  return div.innerHTML
}