import { create } from 'zustand'
import { api, type FileInfo, type ParsingResultSummary, type CodeChunk, type GraphData, type WsMessage, type WsStep } from '../api'

export interface FileNode {
  path: string
  name: string
  type: 'file' | 'folder'
  language?: string
  children?: FileNode[]
  symbolCount?: number
  totalLines?: number
  isExpanded?: boolean
}

export interface RepoState {
  // 仓库信息
  repoUrl: string
  branch: string
  repoName: string
  
  // 解析状态
  isParsing: boolean
  parseProgress: number
  parseStep: string
  parseError: string | null
  parseResult: ParsingResultSummary | null
  parseStepId: WsStep | null
  taskId: string | null

  // 文件树
  fileTree: FileNode[]
  selectedFile: FileInfo | null
  selectedChunk: CodeChunk | null
  searchQuery: string

  // 依赖图数据
  dependencyGraph: GraphData | null
  isFetchingGraph: boolean
  graphError: string | null

  // 操作方法
  setRepoInfo: (url: string, branch?: string) => void
  startParsing: (url: string, branch?: string) => Promise<void>
  setParseProgress: (progress: number, step: string) => void
  setParseError: (error: string | null) => void
  parseRepo: (url: string, branch?: string) => Promise<void>
  parseRepoAsync: (url: string, branch?: string) => Promise<void>
  fetchDependencyGraph: (url: string, branch?: string) => Promise<void>
  selectFile: (file: FileInfo | null) => void
  selectChunk: (chunk: CodeChunk | null) => void
  setSearchQuery: (query: string) => void
  setDependencyGraph: (graph: GraphData | null) => void
  resetState: () => void
}

export const useRepoStore = create<RepoState>((set, get) => ({
  // 初始状态
  repoUrl: '',
  branch: '',
  repoName: '',
  isParsing: false,
  parseProgress: 0,
  parseStep: '',
  parseError: null,
  parseResult: null,
  parseStepId: null,
  taskId: null,
  fileTree: [],
  selectedFile: null,
  selectedChunk: null,
  searchQuery: '',
  dependencyGraph: null,
  isFetchingGraph: false,
  graphError: null,

  // 设置仓库信息
  setRepoInfo: (url: string, branch?: string) => {
    const repoName = url.split('/').pop()?.replace('.git', '') || ''
    set({ repoUrl: url, branch: branch || '', repoName })
  },

  // 开始解析（设置状态）
  startParsing: async (url: string, branch?: string) => {
    const repoName = url.split('/').pop()?.replace('.git', '') || ''
    set({
      repoUrl: url,
      branch: branch || '',
      repoName,
      isParsing: true,
      parseProgress: 0,
      parseStep: '准备开始...',
      parseError: null,
      parseResult: null,
      fileTree: [],
      selectedFile: null,
      selectedChunk: null,
    })
  },

  // 更新解析进度
  setParseProgress: (progress: number, step: string) => {
    set({ parseProgress: progress, parseStep: step })
  },

  // 设置错误
  setParseError: (error: string | null) => {
    set({ parseError: error, isParsing: false })
  },

  // 解析仓库
  parseRepo: async (url: string, branch?: string) => {
    const state = get()
    await state.startParsing(url, branch)

    try {
      set({ parseStep: '正在克隆仓库...', parseProgress: 20 })
      await new Promise(resolve => setTimeout(resolve, 500))

      set({ parseStep: '正在解析文件结构...', parseProgress: 40 })
      const result = await api.parseRepo(url, branch)

      set({ parseStep: '正在构建代码索引...', parseProgress: 60 })

      set({ parseStep: '正在生成依赖图...', parseProgress: 80 })

      // 构建文件树
      const fileTree = buildFileTree(result.files)

      set({
        parseResult: result,
        fileTree,
        isParsing: false,
        parseProgress: 100,
        parseStep: '解析完成',
      })

      // 解析完成后异步拉取依赖图（不阻塞主流程）
      get().fetchDependencyGraph(url, branch).catch(() => {
        // 依赖图失败不影响主流程，错误已写入 graphError
      })
    } catch (e) {
      set({
        parseError: (e as Error).message,
        isParsing: false,
      })
    }
  },

  // 异步解析仓库（Celery + WebSocket 实时进度，文档 3.4 节）
  parseRepoAsync: async (url: string, branch?: string) => {
    const state = get()
    await state.startParsing(url, branch)
    set({ parseStepId: 'init', taskId: null })

    try {
      // 1. 提交异步任务
      set({ parseStep: '提交解析任务...', parseProgress: 5 })
      const resp = await api.parseRepoAsync(url, branch)
      set({ taskId: resp.task_id })

      // 2. 建立 WebSocket 订阅实时进度
      await new Promise<void>((resolve, reject) => {
        const wsBase = import.meta.env.VITE_WS_BASE_URL || 'ws://localhost:8000/api/v1'
        const ws = new WebSocket(`${wsBase}/ws/${resp.task_id}`)

        ws.onmessage = (event) => {
          try {
            const msg: WsMessage = JSON.parse(event.data)
            if (msg.type === 'progress') {
              set({
                parseProgress: msg.progress ?? 0,
                parseStep: msg.message ?? '',
                parseStepId: msg.step ?? null,
              })
            } else if (msg.type === 'status') {
              if (msg.status === 'completed') {
                set({
                  parseProgress: 100,
                  parseStep: msg.message ?? '解析完成',
                  parseStepId: 'complete',
                  isParsing: false,
                })
                ws.close()
                resolve()
              } else if (msg.status === 'error') {
                set({
                  parseError: msg.message ?? msg.error ?? '解析失败',
                  isParsing: false,
                })
                ws.close()
                reject(new Error(msg.message ?? '解析失败'))
              }
            }
          } catch (parseErr) {
            // 忽略非 JSON 消息
          }
        }

        ws.onerror = () => {
          reject(new Error('WebSocket 连接失败'))
        }

        ws.onclose = () => {
          // 如果还未 resolve，说明任务未完成就关闭了
          if (get().isParsing) {
            // 兜底：通过 REST 查询最终状态
            api.getAsyncTaskStatus(resp.task_id).then((status) => {
              if (status.state === 'SUCCESS' && status.result) {
                set({
                  parseProgress: 100,
                  parseStep: '解析完成',
                  parseStepId: 'complete',
                  isParsing: false,
                })
                resolve()
              } else if (status.state === 'FAILURE') {
                set({
                  parseError: status.error ?? '解析失败',
                  isParsing: false,
                })
                reject(new Error(status.error ?? '解析失败'))
              }
            }).catch(reject)
          }
        }
      })

      // 3. 完成后构建文件树（从同步接口补取摘要用于文件树展示）
      try {
        const summary = await api.parseRepo(url, branch)
        const fileTree = buildFileTree(summary.files)
        set({ parseResult: summary, fileTree })
      } catch {
        // 文件树构建失败不阻塞，依赖图仍可拉取
      }

      // 4. 拉取依赖图
      get().fetchDependencyGraph(url, branch).catch(() => {})
    } catch (e) {
      // 异步解析失败（如 Celery/Redis 不可用），回退到同步解析
      console.warn('[CodeNova] 异步解析失败，回退同步解析', e)
      try {
        set({ parseError: null, isParsing: true, parseStep: '正在同步解析仓库...', parseProgress: 30, parseStepId: 'parse' })
        const result = await api.parseRepo(url, branch)
        const fileTree = buildFileTree(result.files)
        set({
          parseResult: result,
          fileTree,
          isParsing: false,
          parseProgress: 100,
          parseStep: '解析完成',
          parseStepId: 'complete',
        })
        // 同步解析完成后异步拉取依赖图
        get().fetchDependencyGraph(url, branch).catch(() => {})
      } catch (syncErr) {
        set({
          parseError: (syncErr as Error).message,
          isParsing: false,
        })
      }
    }
  },

  // 拉取依赖图（文档 3.2 节）
  fetchDependencyGraph: async (url: string, branch?: string) => {
    set({ isFetchingGraph: true, graphError: null })
    try {
      const graph = await api.getDependencyGraph(url, branch)
      set({ dependencyGraph: graph, isFetchingGraph: false })
    } catch (e) {
      set({
        graphError: (e as Error).message,
        isFetchingGraph: false,
      })
    }
  },

  // 选择文件
  selectFile: (file: FileInfo | null) => {
    set({ selectedFile: file, selectedChunk: null })
  },

  // 选择代码块
  selectChunk: (chunk: CodeChunk | null) => {
    set({ selectedChunk: chunk })
  },

  // 设置搜索查询
  setSearchQuery: (query: string) => {
    set({ searchQuery: query })
  },

  // 设置依赖图
  setDependencyGraph: (graph: GraphData | null) => {
    set({ dependencyGraph: graph })
  },

  // 重置状态
  resetState: () => {
    set({
      repoUrl: '',
      branch: '',
      repoName: '',
      isParsing: false,
      parseProgress: 0,
      parseStep: '',
      parseError: null,
      parseResult: null,
      fileTree: [],
      selectedFile: null,
      selectedChunk: null,
      searchQuery: '',
      dependencyGraph: null,
      isFetchingGraph: false,
      graphError: null,
      parseStepId: null,
      taskId: null,
    })
  },
}))

// 构建文件树
function buildFileTree(files: FileInfo[]): FileNode[] {
  const root: FileNode[] = []
  const folderMap = new Map<string, FileNode>()

  for (const file of files) {
    const parts = file.path.split('/')
    let currentPath = ''
    let parentChildren = root

    for (let i = 0; i < parts.length; i++) {
      const part = parts[i]
      const isLast = i === parts.length - 1
      currentPath = currentPath ? `${currentPath}/${part}` : part

      if (isLast) {
        // 这是一个文件
        const fileNode: FileNode = {
          path: file.path,
          name: part,
          type: 'file',
          language: file.language,
          symbolCount: file.symbol_count,
          totalLines: file.total_lines,
        }
        parentChildren.push(fileNode)
      } else {
        // 这是一个文件夹
        if (!folderMap.has(currentPath)) {
          const folderNode: FileNode = {
            path: currentPath,
            name: part,
            type: 'folder',
            children: [],
            isExpanded: false,
          }
          folderMap.set(currentPath, folderNode)
          parentChildren.push(folderNode)
        }
        parentChildren = folderMap.get(currentPath)!.children!
      }
    }
  }

  // 排序：文件夹在前，文件在后
  const sortNodes = (nodes: FileNode[]): FileNode[] => {
    return nodes.sort((a, b) => {
      if (a.type !== b.type) return a.type === 'folder' ? -1 : 1
      return a.name.localeCompare(b.name)
    }).map(node => {
      if (node.children) {
        return { ...node, children: sortNodes(node.children) }
      }
      return node
    })
  }

  return sortNodes(root)
}