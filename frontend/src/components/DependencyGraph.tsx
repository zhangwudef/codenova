import { useCallback, useMemo, useState } from 'react'
import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  applyNodeChanges,
  applyEdgeChanges,
  type Node,
  type Edge,
  type NodeChange,
  type EdgeChange,
  Connection,
  NodeProps,
} from '@xyflow/react'
import '@xyflow/react/dist/style.css'
import { Box, Code, FileCode, Network, Plus } from 'lucide-react'
import type { GraphNode, GraphEdge } from '../api'

// 图标映射
const iconMap = {
  module: FileCode,
  class: Box,
  function: Code,
  interface: Network,
} as const

// 自定义节点组件
const CustomNode = ({ data, type }: NodeProps) => {
  const nodeData = data as any
  const Icon = iconMap[nodeData.type as keyof typeof iconMap] || Box

  const colorMap: Record<string, string> = {
    module: 'border-blue-300 bg-blue-50',
    class: 'border-green-300 bg-green-50',
    function: 'border-purple-300 bg-purple-50',
    interface: 'border-orange-300 bg-orange-50',
  }
  const labelMap: Record<string, string> = {
    module: '模块',
    class: '类',
    function: '函数',
    interface: '接口',
  }

  return (
    <div className={`rounded-lg border-2 shadow-sm px-3 py-2 min-w-[150px] ${colorMap[type] || 'border-gray-300 bg-gray-50'}`}>
      <div className="flex items-center gap-2">
        <Icon size={16} className="flex-shrink-0" />
        <div className="flex-1 min-w-0">
          <div className="font-medium text-sm text-slate-800 truncate" title={nodeData.label}>
            {nodeData.label}
          </div>
          <div className="text-xs text-slate-500">{labelMap[type]}</div>
        </div>
      </div>
    </div>
  )
}

// 节点类型配置
const nodeTypes = {
  module: (props: NodeProps) => <CustomNode {...props} type="module" />,
  class: (props: NodeProps) => <CustomNode {...props} type="class" />,
  function: (props: NodeProps) => <CustomNode {...props} type="function" />,
  interface: (props: NodeProps) => <CustomNode {...props} type="interface" />,
}

// 边类型配置
const edgeStyles: Record<string, { stroke: string; strokeDasharray?: string }> = {
  import: { stroke: '#6366f1' },
  call: { stroke: '#10b981' },
  inherit: { stroke: '#f59e0b', strokeDasharray: '5,5' },
  implement: { stroke: '#3b82f6', strokeDasharray: '5,5' },
}

// 自动布局：按节点类型分层环形/网格布局
function autoLayout(nodes: GraphNode[]): Record<string, { x: number; y: number }> {
  const positions: Record<string, { x: number; y: number }> = {}
  // 按类型分组
  const groups: Record<string, GraphNode[]> = { module: [], class: [], function: [], interface: [] }
  for (const n of nodes) {
    groups[n.type]?.push(n)
  }

  // 模块放顶部一行，类中间一行，函数底部网格，接口右侧
  const colWidth = 200
  const rowHeight = 160
  let col = 0
  for (const n of groups.module) {
    positions[n.id] = { x: col * colWidth, y: 0 }
    col++
  }
  col = 0
  for (const n of groups.interface) {
    positions[n.id] = { x: col * colWidth, y: rowHeight }
    col++
  }
  col = 0
  for (const n of groups.class) {
    positions[n.id] = { x: col * colWidth, y: rowHeight * 2 }
    col++
  }
  // 函数较多，按 4 列网格
  const funcCols = 4
  groups.function.forEach((n, i) => {
    positions[n.id] = {
      x: (i % funcCols) * colWidth,
      y: rowHeight * 3 + Math.floor(i / funcCols) * 120,
    }
  })
  return positions
}

interface DependencyGraphProps {
  nodes?: GraphNode[]
  edges?: GraphEdge[]
  onNodeClick?: (node: GraphNode) => void
}

export default function DependencyGraph({
  nodes = [],
  edges = [],
  onNodeClick
}: DependencyGraphProps) {
  const [rfNodes, setRfNodes] = useState<Node[]>([])
  const [rfEdges, setRfEdges] = useState<Edge[]>([])
  const [filters, setFilters] = useState({
    module: true,
    class: true,
    function: true,
    interface: true,
  })
  const [edgeFilters, setEdgeFilters] = useState({
    import: true,
    call: true,
    inherit: true,
    implement: true,
  })

  // 转换数据为 ReactFlow 格式 + 自动布局
  useMemo(() => {
    const filteredNodes = nodes.filter(n => filters[n.type])
    const filteredEdges = edges.filter(e => edgeFilters[e.type])

    // 仅保留过滤后节点相关的边
    const keepIds = new Set(filteredNodes.map(n => n.id))
    const validEdges = filteredEdges.filter(e => keepIds.has(e.source) && keepIds.has(e.target))

    const layout = autoLayout(filteredNodes)

    const rfNodesData: Node[] = filteredNodes.map(node => ({
      id: node.id,
      type: node.type,
      position: layout[node.id] || { x: 0, y: 0 },
      data: {
        label: node.label,
        type: node.type,
        file_path: node.file_path,
      } as any,
    }))

    const rfEdgesData: Edge[] = validEdges.map(edge => ({
      id: edge.id,
      source: edge.source,
      target: edge.target,
      type: edge.type === 'call' ? 'smoothstep' : 'bezier',
      animated: edge.type === 'call',
      style: edgeStyles[edge.type],
      label: edge.type === 'import' ? '导入' : edge.type === 'call' ? '调用' : edge.type === 'inherit' ? '继承' : '实现',
      labelStyle: { fill: '#64748b', fontSize: 10 },
      labelBgStyle: { fill: '#f1f5f9' },
    }))

    setRfNodes(rfNodesData)
    setRfEdges(rfEdgesData)
  }, [nodes, edges, filters, edgeFilters])

  const onNodesChange = useCallback(
    (changes: NodeChange[]) => setRfNodes((nds) => applyNodeChanges(changes, nds)),
    []
  )
  const onEdgesChange = useCallback(
    (changes: EdgeChange[]) => setRfEdges((eds) => applyEdgeChanges(changes, eds)),
    []
  )
  const onConnect = useCallback(
    (connection: Connection) => setRfEdges((eds) => addEdge(connection, eds)),
    []
  )

  const handleNodeClick = (_: React.MouseEvent, node: Node) => {
    const originalNode = nodes.find(n => n.id === node.id)
    if (originalNode) {
      onNodeClick?.(originalNode)
    }
  }

  return (
    <div className="flex flex-col h-full bg-white">
      {/* 工具栏 */}
      <div className="flex items-center gap-4 px-4 py-2 border-b border-slate-200 bg-slate-50 flex-wrap">
        <div className="flex items-center gap-2">
          <span className="text-sm font-medium text-slate-700">依赖图</span>
          <span className="text-xs text-slate-500">({nodes.length} 节点, {edges.length} 关系)</span>
        </div>

        {/* 节点类型过滤 */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-slate-500">节点:</span>
          {Object.entries(filters).map(([key, value]) => (
            <button
              key={key}
              onClick={() => setFilters(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
              className={`px-2 py-0.5 rounded transition-colors ${
                value ? 'bg-brand-100 text-brand-700' : 'bg-slate-200 text-slate-500'
              }`}
            >
              {key === 'module' ? '模块' : key === 'class' ? '类' : key === 'function' ? '函数' : '接口'}
            </button>
          ))}
        </div>

        {/* 边类型过滤 */}
        <div className="flex items-center gap-1 text-xs">
          <span className="text-slate-500">关系:</span>
          {Object.entries(edgeFilters).map(([key, value]) => (
            <button
              key={key}
              onClick={() => setEdgeFilters(prev => ({ ...prev, [key]: !prev[key as keyof typeof prev] }))}
              className={`px-2 py-0.5 rounded transition-colors ${
                value ? 'bg-emerald-100 text-emerald-700' : 'bg-slate-200 text-slate-500'
              }`}
            >
              {key === 'import' ? '导入' : key === 'call' ? '调用' : key === 'inherit' ? '继承' : '实现'}
            </button>
          ))}
        </div>
      </div>

      {/* 画布 */}
      <div className="flex-1">
        <ReactFlow
          nodes={rfNodes}
          edges={rfEdges}
          onNodesChange={onNodesChange}
          onEdgesChange={onEdgesChange}
          onConnect={onConnect}
          onNodeClick={handleNodeClick}
          nodeTypes={nodeTypes}
          fitView
          minZoom={0.1}
          maxZoom={2}
        >
          <Background />
          <Controls />
          <MiniMap
            nodeColor={(node) => {
              const type = node.type
              return type === 'module' ? '#3b82f6' : type === 'class' ? '#10b981' : type === 'function' ? '#8b5cf6' : '#f97316'
            }}
            nodeStrokeWidth={2}
          />
        </ReactFlow>
      </div>
    </div>
  )
}

// 添加新节点的功能（可选）
export function AddNodeButton({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      className="flex items-center gap-1 px-3 py-1.5 rounded-lg bg-brand-600 text-white text-sm hover:bg-brand-700 transition-colors"
    >
      <Plus size={16} />
      添加节点
    </button>
  )
}