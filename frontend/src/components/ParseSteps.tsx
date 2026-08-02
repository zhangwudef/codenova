import { Check, Loader2, Download, Search, Scissors, Database, CheckCircle2, AlertCircle, RotateCcw } from 'lucide-react'
import type { WsStep } from '../api'

interface ParseStepsProps {
  currentStep: WsStep | null
  progress: number
  error: string | null
  onRetry?: () => void
}

// 步骤定义（文档 3.4 节：克隆→解析→切分→向量化→入库）
const STEPS: { id: WsStep; label: string; icon: typeof Download }[] = [
  { id: 'clone', label: '克隆仓库', icon: Download },
  { id: 'parse', label: 'AST 解析', icon: Search },
  { id: 'split', label: '代码切分', icon: Scissors },
  { id: 'vectorize', label: '向量化入库', icon: Database },
  { id: 'complete', label: '完成', icon: CheckCircle2 },
]

export default function ParseSteps({ currentStep, progress, error, onRetry }: ParseStepsProps) {
  const currentIndex = currentStep ? STEPS.findIndex(s => s.id === currentStep) : -1
  const isError = !!error

  return (
    <div className="flex flex-col gap-3 p-4 bg-white rounded-lg border border-slate-200">
      {/* 进度条 */}
      <div className="flex items-center gap-3">
        <div className="flex-1 h-2 bg-slate-100 rounded-full overflow-hidden">
          <div
            className={`h-full transition-all duration-300 ${
              isError ? 'bg-red-400' : 'bg-brand-500'
            }`}
            style={{ width: `${Math.min(100, Math.max(0, progress))}%` }}
          />
        </div>
        <span className="text-xs font-medium text-slate-600 w-10 text-right">
          {Math.round(progress)}%
        </span>
      </div>

      {/* 步骤指示器 */}
      <div className="flex items-center justify-between">
        {STEPS.map((step, i) => {
          const Icon = step.icon
          const isDone = !isError && currentIndex > i
          const isActive = !isError && currentIndex === i
          const isFailed = isError && currentIndex === i

          return (
            <div key={step.id} className="flex items-center flex-1 last:flex-none">
              <div className="flex flex-col items-center gap-1">
                <div
                  className={`w-8 h-8 rounded-full flex items-center justify-center transition-colors ${
                    isDone
                      ? 'bg-emerald-500 text-white'
                      : isActive
                        ? 'bg-brand-500 text-white'
                        : isFailed
                          ? 'bg-red-500 text-white'
                          : 'bg-slate-100 text-slate-400'
                  }`}
                >
                  {isDone ? (
                    <Check size={16} />
                  ) : isActive ? (
                    <Loader2 size={16} className="animate-spin" />
                  ) : (
                    <Icon size={16} />
                  )}
                </div>
                <span
                  className={`text-[10px] font-medium whitespace-nowrap ${
                    isDone || isActive ? 'text-slate-700' : isFailed ? 'text-red-600' : 'text-slate-400'
                  }`}
                >
                  {step.label}
                </span>
              </div>
              {/* 连接线 */}
              {i < STEPS.length - 1 && (
                <div
                  className={`flex-1 h-0.5 mx-2 transition-colors ${
                    isDone ? 'bg-emerald-400' : 'bg-slate-200'
                  }`}
                />
              )}
            </div>
          )
        })}
      </div>

      {/* 当前步骤描述 */}
      {currentStep && !isError && (
        <div className="text-xs text-slate-500 text-center">
          {STEPS[currentIndex]?.label} 进行中...
        </div>
      )}

      {/* 错误提示与重试 */}
      {isError && (
        <div className="flex items-center justify-center gap-3 mt-1">
          <div className="flex items-center gap-1.5 text-xs text-red-600">
            <AlertCircle size={14} />
            <span className="truncate max-w-md">{error}</span>
          </div>
          {onRetry && (
            <button
              onClick={onRetry}
              className="flex items-center gap-1 px-2 py-1 text-xs font-medium text-white bg-brand-600 rounded hover:bg-brand-700 transition-colors"
            >
              <RotateCcw size={12} />
              重试
            </button>
          )}
        </div>
      )}
    </div>
  )
}
