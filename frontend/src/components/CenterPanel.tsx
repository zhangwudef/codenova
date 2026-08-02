import { useState } from 'react'
import { Code2, Network, GitBranch, Loader2, AlertCircle } from 'lucide-react'
import CodePreview from './CodePreview'
import DependencyGraph from './DependencyGraph'
import SequenceDiagram from './SequenceDiagram'
import { useRepoStore } from '../stores/repoStore'

type TabType = 'code' | 'graph' | 'sequence'

interface CenterPanelProps {
  onJumpToLine?: (filePath: string, lineStart: number, lineEnd: number) => void
}

export default function CenterPanel({ onJumpToLine }: CenterPanelProps) {
  const [activeTab, setActiveTab] = useState<TabType>('code')

  const selectedFile = useRepoStore(state => state.selectedFile)
  const dependencyGraph = useRepoStore(state => state.dependencyGraph)
  const isFetchingGraph = useRepoStore(state => state.isFetchingGraph)
  const graphError = useRepoStore(state => state.graphError)
  const repoUrl = useRepoStore(state => state.repoUrl)

  const tabs = [
    { id: 'code' as TabType, label: '代码预览', icon: Code2 },
    { id: 'graph' as TabType, label: '依赖图', icon: Network },
    { id: 'sequence' as TabType, label: '时序图', icon: GitBranch },
  ]

  const handleNodeClick = (node: any) => {
    if (node.file_path) {
      onJumpToLine?.(node.file_path, 1, 1)
      setActiveTab('code')
    }
  }

  // 依赖图加载中状态
  const renderGraphPanel = () => {
    if (isFetchingGraph) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-slate-400">
          <Loader2 size={40} className="mb-3 animate-spin text-brand-500" />
          <p className="text-sm font-medium">正在构建依赖图...</p>
          <p className="text-xs mt-1">基于 AST 提取模块/调用/继承关系</p>
        </div>
      )
    }
    if (graphError) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-red-400">
          <AlertCircle size={40} className="mb-3" />
          <p className="text-sm font-medium">依赖图加载失败</p>
          <p className="text-xs mt-1 text-red-300">{graphError}</p>
        </div>
      )
    }
    if (!dependencyGraph || dependencyGraph.nodes.length === 0) {
      return (
        <div className="flex flex-col items-center justify-center h-full text-slate-400">
          <Network size={48} className="mb-3 opacity-50" />
          <p className="text-sm">暂无依赖图数据</p>
          <p className="text-xs mt-1">请先解析仓库</p>
        </div>
      )
    }
    return (
      <DependencyGraph
        nodes={dependencyGraph.nodes}
        edges={dependencyGraph.edges}
        onNodeClick={handleNodeClick}
      />
    )
  }

  return (
    <div className="flex flex-col h-full bg-slate-50">
      {/* Tab 栏 */}
      <div className="flex items-center border-b border-slate-200 bg-white px-2">
        {tabs.map((tab) => {
          const Icon = tab.icon
          return (
            <button
              key={tab.id}
              onClick={() => setActiveTab(tab.id)}
              className={`flex items-center gap-2 px-4 py-3 text-sm font-medium transition-colors border-b-2 ${
                activeTab === tab.id
                  ? 'border-brand-600 text-brand-600'
                  : 'border-transparent text-slate-500 hover:text-slate-700 hover:bg-slate-50'
              }`}
            >
              <Icon size={16} />
              {tab.label}
            </button>
          )
        })}
      </div>

      {/* Tab 内容 */}
      <div className="flex-1 overflow-hidden">
        {activeTab === 'code' && (
          <CodePreview
            file={selectedFile}
            onChunkSelect={(chunk) => {
              onJumpToLine?.(chunk.file_path, chunk.start_line, chunk.end_line)
            }}
          />
        )}
        {activeTab === 'graph' && renderGraphPanel()}
        {activeTab === 'sequence' && (
          <SequenceDiagram repoUrl={repoUrl} onNodeClick={handleNodeClick} />
        )}
      </div>
    </div>
  )
}
