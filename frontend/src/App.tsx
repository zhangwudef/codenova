import { useState, useCallback, useEffect } from 'react'
import {
  GitBranch,
  Settings,
  Loader2,
  Play,
  FolderTree,
  Sparkles,
  X,
  AlertCircle,
  CheckCircle,
  Monitor,
} from 'lucide-react'
import FileTree from './components/FileTree'
import CenterPanel from './components/CenterPanel'
import ChatPanel from './components/ChatPanel'
import ParseSteps from './components/ParseSteps'
import { ThemeInitializer } from './components/ThemeInitializer'
import { SettingsPanel } from './components/SettingsPanel'
import { useRepoStore } from './stores/repoStore'
import { useRepoHistoryStore } from './stores/themeStore'

// 解析进度指示器组件（使用步骤指示器，文档 3.4 节）
function ParseProgress({
  progress,
  step,
  stepId,
  isParsing,
  error,
  onRetry,
}: {
  progress: number
  step: string
  stepId: import('./api').WsStep | null
  isParsing: boolean
  error: string | null
  onRetry?: () => void
}) {
  if (!isParsing && !error && progress === 0) return null

  return (
    <div className="fixed bottom-4 right-4 w-96 bg-white rounded-xl border border-slate-200 shadow-lg overflow-hidden z-50">
      <div className="px-4 py-3 border-b border-slate-200 flex items-center justify-between">
        <div className="flex items-center gap-2">
          {error ? (
            <AlertCircle size={16} className="text-red-500" />
          ) : isParsing ? (
            <Loader2 size={16} className="text-brand-500 animate-spin" />
          ) : (
            <CheckCircle size={16} className="text-green-500" />
          )}
          <span className="text-sm font-medium text-slate-700">
            {error ? '解析失败' : isParsing ? '正在解析仓库' : '解析完成'}
          </span>
        </div>
      </div>

      <div className="p-4">
        <ParseSteps
          currentStep={stepId}
          progress={progress}
          error={error}
          onRetry={onRetry}
        />
        {!error && step && (
          <div className="mt-2 text-xs text-slate-500 text-center truncate">{step}</div>
        )}
      </div>
    </div>
  )
}

// 仓库输入模态框
function RepoInputModal({ 
  onSubmit, 
  onClose 
}: { 
  onSubmit: (url: string, branch?: string) => void
  onClose: () => void
}) {
  const [url, setUrl] = useState('https://github.com/octocat/Hello-World.git')
  const [branch, setBranch] = useState('')

  return (
    <div className="fixed inset-0 bg-black/50 flex items-center justify-center z-50 p-4">
      <div className="bg-white rounded-2xl shadow-xl w-full max-w-md overflow-hidden">
        <div className="px-6 py-4 border-b border-slate-200 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-slate-800">解析新仓库</h3>
          <button
            onClick={onClose}
            className="p-1 rounded hover:bg-slate-100 transition-colors"
          >
            <X size={20} className="text-slate-500" />
          </button>
        </div>
        
        <div className="p-6 space-y-4">
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              仓库地址
            </label>
            <input
              type="text"
              value={url}
              onChange={(e) => setUrl(e.target.value)}
              placeholder="https://github.com/user/repo.git"
              className="w-full rounded-lg border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
            />
          </div>
          
          <div>
            <label className="block text-sm font-medium text-slate-700 mb-1.5">
              分支（可选）
            </label>
            <input
              type="text"
              value={branch}
              onChange={(e) => setBranch(e.target.value)}
              placeholder="main / master / develop"
              className="w-full rounded-lg border border-slate-200 px-4 py-2.5 text-sm outline-none transition focus:border-brand-400 focus:ring-2 focus:ring-brand-100"
            />
          </div>
          
          <div className="bg-slate-50 rounded-lg p-3 text-xs text-slate-500">
            <p className="mb-1">💡 提示：</p>
            <ul className="list-disc list-inside space-y-1">
              <li>支持公开 GitHub 仓库</li>
              <li>解析时间取决于仓库大小</li>
              <li>解析后可在左侧浏览文件，在右侧提问</li>
            </ul>
          </div>
        </div>
        
        <div className="px-6 py-4 bg-slate-50 flex justify-end gap-3">
          <button
            onClick={onClose}
            className="px-4 py-2 rounded-lg border border-slate-200 text-sm text-slate-600 hover:bg-slate-100 transition-colors"
          >
            取消
          </button>
          <button
            onClick={() => {
              if (url.trim()) {
                onSubmit(url, branch || undefined)
                onClose()
              }
            }}
            className="px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
            disabled={!url.trim()}
          >
            开始解析
          </button>
        </div>
      </div>
    </div>
  )
}

// 主应用组件
export default function App() {
  const [showRepoModal, setShowRepoModal] = useState(false)
  const [showSettings, setShowSettings] = useState(false)
  const [sidebarWidth, setSidebarWidth] = useState(280) // 左侧面板宽度
  const [rightPanelWidth, setRightPanelWidth] = useState(380) // 右侧面板宽度

  const [isResizing, setIsResizing] = useState<'left' | 'right' | null>(null)

  // 响应式：窗口小于 1024px 时显示提示
  const [isNarrow, setIsNarrow] = useState(
    typeof window !== 'undefined' ? window.innerWidth < 1024 : false
  )
  useEffect(() => {
    const handleResize = () => setIsNarrow(window.innerWidth < 1024)
    window.addEventListener('resize', handleResize)
    return () => window.removeEventListener('resize', handleResize)
  }, [])

  const addRepoHistory = useRepoHistoryStore((s) => s.add)

  const repoUrl = useRepoStore(state => state.repoUrl)
  const repoName = useRepoStore(state => state.repoName)
  const fileTree = useRepoStore(state => state.fileTree)
  const parseProgress = useRepoStore(state => state.parseProgress)
  const parseStep = useRepoStore(state => state.parseStep)
  const parseStepId = useRepoStore(state => state.parseStepId)
  const isParsing = useRepoStore(state => state.isParsing)
  const parseError = useRepoStore(state => state.parseError)
  const parseResult = useRepoStore(state => state.parseResult)
  const parseRepoAsync = useRepoStore(state => state.parseRepoAsync)
  const parseRepo = useRepoStore(state => state.parseRepo)
  const resetState = useRepoStore(state => state.resetState)
  const selectFile = useRepoStore(state => state.selectFile)

  const [selectedPath, setSelectedPath] = useState<string | undefined>()

  const handleParseRepo = useCallback(async (url: string, branch?: string) => {
    // 同步解析优先（无需 Celery/Redis，适合 demo 与本地开发）
    // 如需异步解析（带 WebSocket 实时进度），确保 Redis + Celery worker 已启动
    await parseRepo(url, branch)
    // 记录到历史
    addRepoHistory(url, branch)
  }, [parseRepo, addRepoHistory])

  const handleSelectFile = useCallback((path: string) => {
    setSelectedPath(path)
  }, [])

  const handleJumpToSource = useCallback((filePath: string, lineStart: number, lineEnd: number) => {
    if (parseResult) {
      const fileInfo = parseResult.files.find(f => f.path === filePath)
      if (fileInfo) {
        selectFile(fileInfo)
        setSelectedPath(filePath)
      }
    }
    // 切换到代码预览 Tab
    const event = new CustomEvent('jump-to-code', { detail: { lineStart, lineEnd } })
    window.dispatchEvent(event)
  }, [parseResult, selectFile])

  // 拖拽调整面板宽度
  const handleMouseDown = (panel: 'left' | 'right') => (e: React.MouseEvent) => {
    e.preventDefault()
    setIsResizing(panel)

    const startX = e.clientX
    const startWidth = panel === 'left' ? sidebarWidth : rightPanelWidth

    const handleMouseMove = (moveEvent: MouseEvent) => {
      const delta = moveEvent.clientX - startX
      if (panel === 'left') {
        setSidebarWidth(Math.max(200, Math.min(500, startWidth + delta)))
      } else {
        setRightPanelWidth(Math.max(300, Math.min(600, startWidth - delta)))
      }
    }

    const handleMouseUp = () => {
      setIsResizing(null)
      document.removeEventListener('mousemove', handleMouseMove)
      document.removeEventListener('mouseup', handleMouseUp)
    }

    document.addEventListener('mousemove', handleMouseMove)
    document.addEventListener('mouseup', handleMouseUp)
  }

  return (
    <div className="h-screen w-screen flex flex-col bg-slate-100 dark:bg-zinc-950 overflow-hidden min-w-[1024px]">
      <ThemeInitializer />
      <SettingsPanel open={showSettings} onClose={() => setShowSettings(false)} />

      {/* 顶部导航栏 */}
      <header className="flex-shrink-0 h-14 bg-white dark:bg-zinc-900 border-b border-slate-200 dark:border-zinc-800 flex items-center justify-between px-4 shadow-sm">
        <div className="flex items-center gap-4">
          <div className="flex items-center gap-2">
            <div className="w-8 h-8 rounded-lg bg-gradient-to-br from-brand-500 to-indigo-500 flex items-center justify-center">
              <Sparkles size={18} className="text-white" />
            </div>
            <span className="text-lg font-bold bg-gradient-to-r from-brand-600 to-indigo-500 bg-clip-text text-transparent">
              CodeNova
            </span>
          </div>

          {repoUrl && (
            <div className="flex items-center gap-2 px-3 py-1 rounded-full bg-slate-100 dark:bg-zinc-800">
              <GitBranch size={14} className="text-slate-500 dark:text-zinc-400" />
              <span className="text-sm font-medium text-slate-700 dark:text-zinc-200">{repoName}</span>
              <button
                onClick={resetState}
                className="ml-1 p-0.5 rounded hover:bg-red-100 dark:hover:bg-red-900/30 hover:text-red-500 transition-colors"
                title="移除仓库"
              >
                <X size={12} />
              </button>
            </div>
          )}
        </div>

        <div className="flex items-center gap-2">
          <button
            onClick={() => setShowRepoModal(true)}
            className="flex items-center gap-2 px-4 py-2 rounded-lg bg-brand-600 text-white text-sm font-medium hover:bg-brand-700 transition-colors"
          >
            <Play size={14} />
            {repoUrl ? '解析新仓库' : '解析仓库'}
          </button>

          <button
            onClick={() => setShowSettings(true)}
            className="p-2 rounded-lg hover:bg-slate-100 dark:hover:bg-zinc-800 transition-colors"
            title="设置"
          >
            <Settings size={20} className="text-slate-500 dark:text-zinc-400" />
          </button>
        </div>
      </header>

      {/* 三栏主体布局 */}
      <div className="flex-1 flex overflow-hidden">
        {/* 左侧面板 - 文件树 */}
        <aside
          className="flex-shrink-0 bg-white dark:bg-zinc-900 border-r border-slate-200 dark:border-zinc-800 flex flex-col overflow-hidden"
          style={{ width: `${sidebarWidth}px` }}
        >
          <div className="px-4 py-3 border-b border-slate-200 dark:border-zinc-800 flex items-center gap-2">
            <FolderTree size={18} className="text-brand-500" />
            <span className="text-sm font-semibold text-slate-700 dark:text-zinc-200">项目文件</span>
            {parseResult && (
              <span className="ml-auto text-xs text-slate-500 dark:text-zinc-400 bg-slate-100 dark:bg-zinc-800 px-2 py-0.5 rounded">
                {parseResult.parsed_files} 文件
              </span>
            )}
          </div>
          <div className="flex-1 overflow-hidden">
            <FileTree
              nodes={fileTree}
              onSelectFile={handleSelectFile}
              selectedPath={selectedPath}
            />
          </div>
        </aside>

        {/* 左侧拖拽条 */}
        <div
          className={`w-1 cursor-col-resize hover:bg-brand-400 transition-colors ${
            isResizing === 'left' ? 'bg-brand-400' : 'bg-transparent'
          }`}
          onMouseDown={handleMouseDown('left')}
        />

        {/* 中间面板 - 代码预览/可视化 */}
        <main className="flex-1 flex flex-col overflow-hidden min-w-0">
          <CenterPanel onJumpToLine={handleJumpToSource} />
        </main>

        {/* 右侧拖拽条 */}
        <div
          className={`w-1 cursor-col-resize hover:bg-brand-400 transition-colors ${
            isResizing === 'right' ? 'bg-brand-400' : 'bg-transparent'
          }`}
          onMouseDown={handleMouseDown('right')}
        />

        {/* 右侧面板 - 问答 */}
        <aside
          className="flex-shrink-0 bg-white dark:bg-zinc-900 border-l border-slate-200 dark:border-zinc-800 flex flex-col overflow-hidden"
          style={{ width: `${rightPanelWidth}px` }}
        >
          <ChatPanel onJumpToSource={handleJumpToSource} />
        </aside>
      </div>

      {/* 空状态提示 */}
      {!repoUrl && !isParsing && !parseError && (
        <div className="absolute inset-0 flex items-center justify-center bg-white/80 backdrop-blur-sm pointer-events-none">
          <div className="text-center">
            <div className="w-20 h-20 mx-auto mb-4 rounded-2xl bg-gradient-to-br from-brand-100 to-indigo-100 flex items-center justify-center">
              <GitBranch size={40} className="text-brand-500" />
            </div>
            <h2 className="text-xl font-semibold text-slate-700 mb-2">开始使用 CodeNova</h2>
            <p className="text-sm text-slate-500 mb-4 max-w-sm">
              点击"解析仓库"按钮，输入 GitHub 仓库地址，即可开始智能代码分析
            </p>
            <button
              onClick={() => setShowRepoModal(true)}
              className="pointer-events-auto inline-flex items-center gap-2 px-6 py-3 rounded-xl bg-brand-600 text-white font-medium hover:bg-brand-700 transition-colors shadow-lg shadow-brand-500/25"
            >
              <Play size={18} />
              解析仓库
            </button>
          </div>
        </div>
      )}

      {/* 解析进度提示 */}
      <ParseProgress
        progress={parseProgress}
        step={parseStep}
        stepId={parseStepId}
        isParsing={isParsing}
        error={parseError}
        onRetry={() => repoUrl && handleParseRepo(repoUrl)}
      />

      {/* 仓库输入模态框 */}
      {showRepoModal && (
        <RepoInputModal
          onSubmit={handleParseRepo}
          onClose={() => setShowRepoModal(false)}
        />
      )}

      {/* 窄屏提示（响应式，文档 3.5 节） */}
      {isNarrow && (
        <div className="fixed inset-0 bg-slate-900/95 flex items-center justify-center z-[100] p-6">
          <div className="text-center text-white max-w-sm">
            <div className="w-16 h-16 mx-auto mb-4 rounded-2xl bg-brand-500/20 flex items-center justify-center">
              <Monitor size={32} className="text-brand-300" />
            </div>
            <h2 className="text-xl font-semibold mb-2">屏幕宽度不足</h2>
            <p className="text-sm text-slate-300 mb-4">
              CodeNova 三栏布局需要至少 1024px 宽度以获得最佳体验。
              请扩大浏览器窗口或在桌面端访问。
            </p>
            <p className="text-xs text-slate-500">
              当前宽度: {typeof window !== 'undefined' ? window.innerWidth : 0}px
            </p>
          </div>
        </div>
      )}
    </div>
  )
}