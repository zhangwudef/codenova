/** 后端 API 客户端 */

const BASE = import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api/v1'

export interface ServiceCheck {
  status: 'ok' | 'error'
  detail?: string
  collections?: string[]
  buckets?: string[]
}

export interface HealthReady {
  status: 'ok' | 'degraded'
  checks: Record<string, ServiceCheck>
}

export interface CodeChunk {
  symbol_name: string
  symbol_type: string
  qualified_name: string
  file_path: string
  language: string
  start_line: number
  end_line: number
  content: string
  docstring: string | null
}

export interface FileInfo {
  path: string
  language: string
  size_bytes: number
  total_lines: number
  symbol_count: number
  chunks: CodeChunk[]
  skipped: boolean
  skip_reason: string | null
}

export interface ParsingResultSummary {
  repo_url: string
  total_files: number
  parsed_files: number
  skipped_files: number
  total_symbols: number
  total_chunks: number
  files: FileInfo[]
  sample_chunks: CodeChunk[]
  elapsed_seconds: number
}

// RAG 相关接口类型
export interface ChunkMetadata {
  file_path: string
  language: string
  chunk_type: string
  symbol_name?: string
  qualified_name?: string
  start_line?: number
  end_line?: number
  repo_url?: string
  extra?: Record<string, any>
}

export interface IndexResult {
  repo_url: string
  total_files: number
  total_chunks: number
  total_embeddings: number
  collection_name: string
  elapsed_seconds: number
}

export interface RetrievedChunk {
  content: string
  metadata: ChunkMetadata
  score: number
}

export interface QAQuestion {
  question: string
  repo_url?: string
  top_k?: number
  score_threshold?: number
}

export interface QAAnswer {
  answer: string
  sources: RetrievedChunk[]
  question: string
  model?: string
  latency_ms: number
}

export type DocType = 'readme' | 'api' | 'module'

export interface DocGenerateRequest {
  doc_type: DocType
  target_path?: string
  module_name?: string
  repo_url?: string
  extra_context?: Record<string, any>
}

export interface DocGenerateResult {
  doc_type: DocType
  content: string
  template_used: string
  generated_at?: string
  used_rag?: boolean
  repo_url?: string
  rag_sources?: RetrievedChunk[]
}

// 问答固化（文档 4.2 节「问答即文档」）
export interface QAPersistReference {
  file_path: string
  line_start?: number
  line_end?: number
  code?: string
}

export interface QAPersistMessage {
  role: 'user' | 'assistant'
  content: string
  timestamp?: number
  references?: QAPersistReference[]
}

export interface QAPersistRequest {
  title?: string
  repo_url?: string
  messages: QAPersistMessage[]
  pinned_only?: boolean
}

export interface QAPersistResult {
  object_name: string
  bucket: string
  download_url: string | null
  content: string
  message_count: number
  saved_at?: string
}

// 依赖图与时序图相关类型（文档 3.2 / 3.3 节）
export type GraphNodeType = 'module' | 'class' | 'function' | 'interface'
export type GraphEdgeType = 'import' | 'call' | 'inherit' | 'implement'

export interface GraphNode {
  id: string
  type: GraphNodeType
  label: string
  file_path: string
  qualified_name?: string
  start_line?: number
  end_line?: number
}

export interface GraphEdge {
  id: string
  source: string
  target: string
  type: GraphEdgeType
}

export interface GraphData {
  nodes: GraphNode[]
  edges: GraphEdge[]
  repo_url: string
  elapsed_seconds: number
}

export interface SequenceParticipant {
  id: string
  name: string
  type: string
}

export interface SequenceMessage {
  id: string
  from: string
  to: string
  label: string
  kind: string
}

export interface SequenceData {
  title: string
  participants: SequenceParticipant[]
  messages: SequenceMessage[]
  mermaid_syntax: string
  repo_url: string
  entry_function: string
  elapsed_seconds: number
}

// 异步解析任务相关类型（文档 3.4 节）
export interface AsyncParseResponse {
  task_id: string
  repo_url: string
  status: string
  ws_url: string
}

export interface TaskStatusResponse {
  task_id: string
  state: string
  info: Record<string, any>
  result?: Record<string, any>
  error?: string
}

// WebSocket 消息类型
export type WsStep = 'init' | 'clone' | 'parse' | 'split' | 'vectorize' | 'complete'

export interface WsMessage {
  type: 'connected' | 'progress' | 'status' | 'error' | 'pong'
  task_id?: string
  progress?: number
  message?: string
  step?: WsStep
  status?: string
  result?: Record<string, any>
  error?: string
  [key: string]: any
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { 'Content-Type': 'application/json' },
    ...options,
  })
  if (!res.ok) {
    const detail = await res.json().catch(() => ({ detail: res.statusText }))
    throw new Error(detail.detail || `请求失败 ${res.status}`)
  }
  return res.json() as Promise<T>
}

export const api = {
  // 系统
  healthReady: () => request<HealthReady>('/health/ready'),

  // 解析仓库（同步）
  parseRepo: (repo_url: string, branch?: string, max_files = 200) =>
    request<ParsingResultSummary>(`/repos/parse`, {
      method: 'POST',
      body: JSON.stringify({ repo_url, branch, max_files }),
    }),

  // 异步解析仓库（Celery 任务，文档 3.4 节）
  parseRepoAsync: (repo_url: string, branch?: string, max_files = 200) =>
    request<AsyncParseResponse>(`/repos/parse-async`, {
      method: 'POST',
      body: JSON.stringify({ repo_url, branch, max_files }),
    }),

  // 查询异步任务状态
  getAsyncTaskStatus: (task_id: string) =>
    request<TaskStatusResponse>(`/repos/parse-async/${task_id}/status`),

  // RAG 索引
  indexRepo: (repo_url: string, branch?: string, max_files = 200, chunk_strategy = 'ast') =>
    request<IndexResult>('/rag/index', {
      method: 'POST',
      body: JSON.stringify({ repo_url, branch, max_files, chunk_strategy }),
    }),

  // RAG 增量索引（文档 4.1 节「增量文档更新」）
  indexRepoIncremental: (repo_url: string, branch?: string, since_commit?: string, max_files = 500) =>
    request<Record<string, any>>('/rag/index-incremental', {
      method: 'POST',
      body: JSON.stringify({ repo_url, branch, since_commit, max_files }),
    }),

  indexFile: (content: string, file_path: string, language: string, repo_url = '', chunk_strategy = 'ast') =>
    request<IndexResult>('/rag/index-file', {
      method: 'POST',
      body: JSON.stringify({ content, file_path, language, repo_url, chunk_strategy }),
    }),

  // RAG 问答
  askQuestion: (question: QAQuestion) =>
    request<QAAnswer>('/rag/ask', {
      method: 'POST',
      body: JSON.stringify(question),
    }),

  // RAG 流式问答（SSE）- 文档 3.1 节「流式打字机效果」
  // 返回可读取 SSE 事件的 ReadableStream
  askQuestionStream: (question: QAQuestion) => {
    const controller = new AbortController()
    const responsePromise = fetch(`${BASE}/rag/ask-stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
        'Accept': 'text/event-stream',
      },
      body: JSON.stringify(question),
      signal: controller.signal,
    })

    return {
      abort: () => controller.abort(),
      // 异步迭代器：按 SSE 事件逐条 yield
      async *[Symbol.asyncIterator]() {
        const res = await responsePromise
        if (!res.ok || !res.body) {
          const detail = await res.json().catch(() => ({ detail: res.statusText }))
          throw new Error(detail.detail || `流式请求失败 ${res.status}`)
        }

        const reader = res.body.getReader()
        const decoder = new TextDecoder('utf-8')
        let buffer = ''

        try {
          while (true) {
            const { done, value } = await reader.read()
            if (done) break
            buffer += decoder.decode(value, { stream: true })

            // SSE 事件以 "\n\n" 分隔
            let sepIdx: number
            while ((sepIdx = buffer.indexOf('\n\n')) !== -1) {
              const rawEvent = buffer.slice(0, sepIdx)
              buffer = buffer.slice(sepIdx + 2)

              // 解析 data: 前缀
              const dataLines = rawEvent
                .split('\n')
                .filter((l) => l.startsWith('data:'))
                .map((l) => l.slice(5).trim())
                .join('')
              if (!dataLines) continue

              try {
                yield JSON.parse(dataLines)
              } catch {
                // 非 JSON 数据，跳过
              }
            }
          }
        } finally {
          reader.releaseLock()
        }
      },
    }
  },

  // 文档生成
  generateDocument: (req: DocGenerateRequest) =>
    request<DocGenerateResult>('/rag/documents/generate', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  // 问答固化为文档（文档 4.2 节「问答即文档」）
  persistQA: (req: QAPersistRequest) =>
    request<QAPersistResult>('/rag/qa/persist', {
      method: 'POST',
      body: JSON.stringify(req),
    }),

  // 集合统计
  getCollectionStats: () =>
    request<{ code_chunks_count: number; code_collection: string; docs_collection: string }>('/rag/collections/stats'),

  // 删除仓库数据
  deleteRepoData: (repo_url: string) =>
    request<{ deleted_points: number; repo_url: string }>(`/rag/collections/repo/${encodeURIComponent(repo_url)}`, {
      method: 'DELETE',
    }),

  // 依赖图（文档 3.2 节）
  getDependencyGraph: (repo_url: string, branch?: string, max_files = 200, node_type?: string) => {
    const params = new URLSearchParams({ repo_url, max_files: String(max_files) })
    if (branch) params.set('branch', branch)
    if (node_type) params.set('node_type', node_type)
    return request<GraphData>(`/repos/graph?${params.toString()}`)
  },

  // 时序图（文档 3.3 节）
  getSequenceDiagram: (repo_url: string, entry: string, branch?: string, max_files = 200, max_depth = 5) => {
    const params = new URLSearchParams({ repo_url, entry, max_files: String(max_files), max_depth: String(max_depth) })
    if (branch) params.set('branch', branch)
    return request<SequenceData>(`/repos/sequence?${params.toString()}`)
  },
}

// WebSocket 连接管理
export function createWebSocketConnection(taskId: string): WebSocket {
  const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/api/v1'
  const ws = new WebSocket(`${wsBase}/ws/${taskId}`)
  return ws
}
