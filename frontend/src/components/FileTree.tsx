import { useState, useMemo } from 'react'
import { ChevronRight, ChevronDown, File, Folder, Search, Code, FileText, Settings, Database, Server, Braces } from 'lucide-react'
import type { FileNode } from '../stores/repoStore'
import { useRepoStore } from '../stores/repoStore'

// 语言图标映射
const LANGUAGE_ICONS: Record<string, { icon: any; color: string }> = {
  'python': { icon: Code, color: 'text-blue-500' },
  'javascript': { icon: Braces, color: 'text-yellow-500' },
  'typescript': { icon: Braces, color: 'text-blue-400' },
  'java': { icon: Server, color: 'text-red-500' },
  'go': { icon: Database, color: 'text-cyan-500' },
  'rust': { icon: Settings, color: 'text-orange-500' },
  'html': { icon: FileText, color: 'text-orange-400' },
  'css': { icon: FileText, color: 'text-blue-400' },
  'json': { icon: Braces, color: 'text-gray-500' },
  'yaml': { icon: FileText, color: 'text-purple-500' },
  'markdown': { icon: FileText, color: 'text-gray-400' },
}

interface FileTreeProps {
  nodes: FileNode[]
  onSelectFile: (path: string) => void
  selectedPath?: string
}

export default function FileTree({ nodes, onSelectFile, selectedPath }: FileTreeProps) {
  const [searchQuery, setSearchQuery] = useState('')
  const [expandedFolders, setExpandedFolders] = useState<Set<string>>(new Set())
  
  const parseResult = useRepoStore(state => state.parseResult)
  const selectFile = useRepoStore(state => state.selectFile)

  // 过滤文件树
  const filteredNodes = useMemo(() => {
    if (!searchQuery) return nodes
    return filterTree(nodes, searchQuery.toLowerCase())
  }, [nodes, searchQuery])

  const toggleFolder = (path: string) => {
    setExpandedFolders(prev => {
      const next = new Set(prev)
      if (next.has(path)) {
        next.delete(path)
      } else {
        next.add(path)
      }
      return next
    })
  }

  const handleFileClick = (node: FileNode) => {
    if (node.type === 'file' && parseResult) {
      const fileInfo = parseResult.files.find(f => f.path === node.path)
      if (fileInfo) {
        selectFile(fileInfo)
        onSelectFile(node.path)
      }
    }
  }

  const renderNode = (node: FileNode, depth: number) => {
    const isExpanded = expandedFolders.has(node.path)
    const isSelected = selectedPath === node.path
    const paddingLeft = `${depth * 16 + 8}px`

    if (node.type === 'folder') {
      return (
        <div key={node.path}>
          <button
            onClick={() => toggleFolder(node.path)}
            className={`flex w-full items-center gap-1 rounded px-2 py-1 text-sm hover:bg-slate-100 transition-colors ${
              isSelected ? 'bg-brand-50 text-brand-700' : 'text-slate-700'
            }`}
            style={{ paddingLeft }}
          >
            {isExpanded ? (
              <ChevronDown size={14} className="text-slate-400 flex-shrink-0" />
            ) : (
              <ChevronRight size={14} className="text-slate-400 flex-shrink-0" />
            )}
            <Folder size={16} className="text-amber-500 flex-shrink-0" />
            <span className="truncate">{node.name}</span>
          </button>
          {isExpanded && node.children && (
            <div>
              {node.children.map(child => renderNode(child, depth + 1))}
            </div>
          )}
        </div>
      )
    }

    // 文件节点
    const langConfig = node.language ? LANGUAGE_ICONS[node.language] : null
    const IconComponent = langConfig?.icon || File
    const iconColor = langConfig?.color || 'text-slate-400'

    return (
      <button
        key={node.path}
        onClick={() => handleFileClick(node)}
        className={`flex w-full items-center gap-2 rounded px-2 py-1 text-sm transition-colors ${
          isSelected 
            ? 'bg-brand-50 text-brand-700 font-medium' 
            : 'text-slate-600 hover:bg-slate-100'
        }`}
        style={{ paddingLeft }}
        title={node.path}
      >
        <span className="w-3 flex-shrink-0" /> {/* 占位，对齐文件夹图标 */}
        <IconComponent size={14} className={`flex-shrink-0 ${iconColor}`} />
        <span className="truncate flex-1 text-left">{node.name}</span>
        {node.symbolCount !== undefined && node.symbolCount > 0 && (
          <span className="ml-auto text-xs text-slate-400 bg-slate-100 rounded px-1.5 py-0.5">
            {node.symbolCount}
          </span>
        )}
      </button>
    )
  }

  if (nodes.length === 0) {
    return (
      <div className="flex flex-col items-center justify-center h-full p-4 text-slate-400">
        <Folder size={48} className="mb-3 opacity-50" />
        <p className="text-sm">暂无文件</p>
        <p className="text-xs mt-1">请先解析仓库</p>
      </div>
    )
  }

  return (
    <div className="flex flex-col h-full">
      {/* 搜索框 */}
      <div className="p-3 border-b border-slate-200">
        <div className="relative">
          <Search size={16} className="absolute left-2.5 top-1/2 -translate-y-1/2 text-slate-400" />
          <input
            type="text"
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            placeholder="搜索文件..."
            className="w-full rounded-md border border-slate-200 bg-slate-50 pl-8 pr-3 py-1.5 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
          />
        </div>
      </div>

      {/* 文件树 */}
      <div className="flex-1 overflow-auto py-2">
        {filteredNodes.map(node => renderNode(node, 0))}
      </div>
    </div>
  )
}

// 过滤文件树
function filterTree(nodes: FileNode[], query: string): FileNode[] {
  const result: FileNode[] = []
  
  for (const node of nodes) {
    if (node.type === 'folder' && node.children) {
      const filteredChildren = filterTree(node.children, query)
      if (filteredChildren.length > 0 || node.name.toLowerCase().includes(query)) {
        result.push({
          ...node,
          children: filteredChildren.length > 0 ? filteredChildren : node.children,
          isExpanded: filteredChildren.length > 0,
        })
      }
    } else if (node.name.toLowerCase().includes(query) || 
               node.path.toLowerCase().includes(query)) {
      result.push(node)
    }
  }
  
  return result
}