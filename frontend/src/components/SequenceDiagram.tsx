import { useState, useEffect, useCallback } from 'react'
import mermaid from 'mermaid'
import { ZoomIn, ZoomOut, Copy, Download, Loader2, AlertCircle, GitBranch, Search } from 'lucide-react'
import { api, type SequenceData } from '../api'

interface SequenceDiagramProps {
  repoUrl?: string
  onNodeClick?: (node: any) => void
}

// Mermaid 主题定制（浅色现代风）
const MERMAID_THEME = {
  theme: 'base',
  themeVariables: {
    primaryColor: '#e0f2fe',
    primaryTextColor: '#0f172a',
    primaryBorderColor: '#0ea5e9',
    lineColor: '#64748b',
    secondaryColor: '#f1f5f9',
    tertiaryColor: '#ffffff',
    fontSize: '14px',
    actorBkg: '#e0f2fe',
    actorBorder: '#0ea5e9',
    actorTextColor: '#0f172a',
    signalColor: '#475569',
    signalTextColor: '#0f172a',
    labelBoxBkgColor: '#f1f5f9',
    labelBoxBorderColor: '#94a3b8',
    labelTextColor: '#0f172a',
  },
} as const

mermaid.initialize({
  startOnLoad: false,
  ...MERMAID_THEME,
  sequence: {
    diagramMarginX: 30,
    diagramMarginY: 20,
    actorMargin: 80,
    boxMargin: 10,
    messageMargin: 35,
    mirrorActors: true,
    bottomMarginAdj: 1,
    useMaxWidth: true,
  },
})

export default function SequenceDiagram({ repoUrl, onNodeClick }: SequenceDiagramProps) {
  const [entryFunction, setEntryFunction] = useState('')
  const [sequenceData, setSequenceData] = useState<SequenceData | null>(null)
  const [loading, setLoading] = useState(false)
  const [error, setError] = useState<string | null>(null)
  const [svg, setSvg] = useState<string>('')
  const [zoom, setZoom] = useState(1)

  // 渲染 Mermaid
  const renderMermaid = useCallback(async (syntax: string) => {
    if (!syntax) {
      setSvg('')
      return
    }
    try {
      const id = 'seq-' + Date.now()
      const { svg: rendered } = await mermaid.render(id, syntax)
      setSvg(rendered)
    } catch (e) {
      setError(`Mermaid 渲染失败: ${(e as Error).message}`)
      setSvg('')
    }
  }, [])

  // 拉取时序图数据
  const fetchSequence = useCallback(async (entry: string) => {
    if (!repoUrl || !entry.trim()) return
    setLoading(true)
    setError(null)
    try {
      const data = await api.getSequenceDiagram(repoUrl, entry.trim())
      setSequenceData(data)
      if (data.mermaid_syntax) {
        await renderMermaid(data.mermaid_syntax)
      } else {
        setSvg('')
        setError('未生成时序图语法（可能未找到该入口函数的调用链）')
      }
    } catch (e) {
      setError((e as Error).message)
      setSequenceData(null)
      setSvg('')
    } finally {
      setLoading(false)
    }
  }, [repoUrl, renderMermaid])

  // 仓库变更时重置
  useEffect(() => {
    setSequenceData(null)
    setSvg('')
    setError(null)
    setEntryFunction('')
  }, [repoUrl])

  const handleSearch = () => {
    if (entryFunction.trim()) {
      fetchSequence(entryFunction)
    }
  }

  const handleCopy = () => {
    if (sequenceData?.mermaid_syntax) {
      navigator.clipboard.writeText(sequenceData.mermaid_syntax)
    }
  }

  const handleDownload = () => {
    if (!svg) return
    const blob = new Blob([svg], { type: 'image/svg+xml' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `sequence-${entryFunction || 'diagram'}.svg`
    a.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 工具栏 */}
      <div className="flex items-center gap-3 px-4 py-2 border-b border-slate-200 bg-slate-50 flex-wrap">
        <div className="flex items-center gap-2">
          <GitBranch size={16} className="text-brand-600" />
          <span className="text-sm font-medium text-slate-700">时序图</span>
        </div>

        {/* 入口函数输入 */}
        <div className="flex items-center gap-2 flex-1 min-w-[260px]">
          <div className="relative flex-1 max-w-md">
            <Search size={14} className="absolute left-3 top-1/2 -translate-y-1/2 text-slate-400" />
            <input
              type="text"
              value={entryFunction}
              onChange={(e) => setEntryFunction(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && handleSearch()}
              placeholder="输入入口函数名，如 parseRepo / main"
              disabled={!repoUrl || loading}
              className="w-full pl-9 pr-3 py-1.5 text-sm border border-slate-300 rounded-md focus:outline-none focus:border-brand-500 focus:ring-1 focus:ring-brand-500 disabled:bg-slate-100 disabled:text-slate-400"
            />
          </div>
          <button
            onClick={handleSearch}
            disabled={!repoUrl || !entryFunction.trim() || loading}
            className="px-3 py-1.5 text-sm font-medium text-white bg-brand-600 rounded-md hover:bg-brand-700 disabled:bg-slate-300 disabled:cursor-not-allowed transition-colors"
          >
            生成
          </button>
        </div>

        {/* 缩放与导出 */}
        {svg && (
          <div className="flex items-center gap-1">
            <button
              onClick={() => setZoom((z) => Math.max(0.5, z - 0.2))}
              className="p-1.5 rounded hover:bg-slate-200 text-slate-600"
              title="缩小"
            >
              <ZoomOut size={16} />
            </button>
            <span className="text-xs text-slate-500 w-10 text-center">{Math.round(zoom * 100)}%</span>
            <button
              onClick={() => setZoom((z) => Math.min(3, z + 0.2))}
              className="p-1.5 rounded hover:bg-slate-200 text-slate-600"
              title="放大"
            >
              <ZoomIn size={16} />
            </button>
            <button
              onClick={handleCopy}
              className="p-1.5 rounded hover:bg-slate-200 text-slate-600"
              title="复制 Mermaid 语法"
            >
              <Copy size={16} />
            </button>
            <button
              onClick={handleDownload}
              className="p-1.5 rounded hover:bg-slate-200 text-slate-600"
              title="下载 SVG"
            >
              <Download size={16} />
            </button>
          </div>
        )}
      </div>

      {/* 内容区 */}
      <div className="flex-1 overflow-auto p-4">
        {!repoUrl ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <GitBranch size={48} className="mb-3 opacity-50" />
            <p className="text-sm">请先解析仓库</p>
            <p className="text-xs mt-1">解析后输入入口函数名生成调用时序图</p>
          </div>
        ) : loading ? (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <Loader2 size={40} className="mb-3 animate-spin text-brand-500" />
            <p className="text-sm font-medium">正在提取调用链...</p>
            <p className="text-xs mt-1">从 {entryFunction} 出发遍历调用关系</p>
          </div>
        ) : error ? (
          <div className="flex flex-col items-center justify-center h-full text-red-400">
            <AlertCircle size={40} className="mb-3" />
            <p className="text-sm font-medium">时序图生成失败</p>
            <p className="text-xs mt-1 text-red-300 max-w-md text-center">{error}</p>
          </div>
        ) : svg ? (
          <div className="flex flex-col items-center">
            {sequenceData && (
              <div className="mb-3 text-xs text-slate-500">
                参与者 {sequenceData.participants.length} · 消息 {sequenceData.messages.length} ·
                耗时 {sequenceData.elapsed_seconds.toFixed(2)}s
              </div>
            )}
            <div
              className="mermaid-container"
              style={{ transform: `scale(${zoom})`, transformOrigin: 'top center', transition: 'transform 0.2s' }}
              dangerouslySetInnerHTML={{ __html: svg }}
              onClick={(e) => {
                // 点击参与者标签跳转（尽力匹配）
                const target = e.target as HTMLElement
                const text = target.textContent || ''
                onNodeClick?.({ label: text, file_path: '' })
              }}
            />
          </div>
        ) : (
          <div className="flex flex-col items-center justify-center h-full text-slate-400">
            <GitBranch size={48} className="mb-3 opacity-50" />
            <p className="text-sm">输入入口函数名</p>
            <p className="text-xs mt-1">点击「生成」按钮提取调用链时序图</p>
          </div>
        )}
      </div>
    </div>
  )
}
