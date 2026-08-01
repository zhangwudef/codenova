/**
 * 错误信息友好化工具
 * 将技术化异常转换为用户可理解的提示
 */

export type ErrorCategory =
  | 'network'        // 网络连接问题
  | 'auth'           // 鉴权失败
  | 'rate_limit'     // 频率限制
  | 'repo_not_found' // 仓库不存在
  | 'repo_too_large' // 仓库过大
  | 'parse_error'    // 解析失败
  | 'index_error'    // 索引失败
  | 'llm_error'      // LLM 服务异常
  | 'server_error'   // 服务器内部错误
  | 'unknown'        // 未知错误

export interface FriendlyError {
  category: ErrorCategory
  title: string       // 一句话标题
  message: string     // 友好说明
  suggestion?: string // 建议操作
  original?: string   // 原始错误信息（开发者用）
}

const ERROR_PATTERNS: Array<{ pattern: RegExp; category: ErrorCategory; title: string; message: string; suggestion?: string }> = [
  {
    pattern: /Failed to fetch|NetworkError|ERR_NETWORK|ERR_CONNECTION_REFUSED|fetch.*failed/i,
    category: 'network',
    title: '网络连接失败',
    message: '无法连接到后端服务，请检查后端是否启动。',
    suggestion: '运行 docker compose -f docker-compose.demo.yml up -d 启动服务，或刷新页面重试。',
  },
  {
    pattern: /401|Unauthorized|Invalid API key|Missing API key/i,
    category: 'auth',
    title: '鉴权失败',
    message: 'API Key 无效或未提供。',
    suggestion: '点击右上角设置图标，输入正确的 API Key。',
  },
  {
    pattern: /429|Too Many Requests|rate limit|RateLimit/i,
    category: 'rate_limit',
    title: '请求过于频繁',
    message: '已触发速率限制，请稍后再试。',
    suggestion: '等待 1-2 分钟后重试，或减少并发请求。',
  },
  {
    pattern: /404|Not Found|repository.*not.*found|repo.*not.*found/i,
    category: 'repo_not_found',
    title: '仓库不存在',
    message: '指定的 GitHub 仓库未找到。',
    suggestion: '检查 URL 是否正确，确认仓库为公开可见。',
  },
  {
    pattern: /422|Unprocessable|clone.*fail|git clone.*fail/i,
    category: 'repo_not_found',
    title: '仓库克隆失败',
    message: '无法克隆该仓库。',
    suggestion: '确认 URL 格式为 https://github.com/<owner>/<repo>，且仓库可访问。',
  },
  {
    pattern: /max.*files|too.*large|OOM|out of memory|文件数超过/i,
    category: 'repo_too_large',
    title: '仓库过大',
    message: '仓库文件数超过限制。',
    suggestion: '减小 max_files 参数，或选择较小的仓库。',
  },
  {
    pattern: /parse.*fail|解析失败|语法错误|SyntaxError/i,
    category: 'parse_error',
    title: '解析失败',
    message: '代码解析时遇到错误。',
    suggestion: '查看后端日志了解详情，部分文件解析失败不影响整体流程。',
  },
  {
    pattern: /index.*fail|索引失败|QdrantError|qdrant.*error/i,
    category: 'index_error',
    title: '索引构建失败',
    message: '向量化或索引入库失败。',
    suggestion: '确认 Qdrant 服务已启动（端口 6333）。',
  },
  {
    pattern: /OpenAI|LLM|openai.*error|model.*not.*found|insufficient_quota/i,
    category: 'llm_error',
    title: 'LLM 服务异常',
    message: '调用 LLM 时出错。',
    suggestion: '检查 OPENAI_API_KEY 是否有效、账户额度是否充足。',
  },
  {
    pattern: /500|502|503|504|Internal Server Error|Bad Gateway|Service Unavailable/i,
    category: 'server_error',
    title: '服务器内部错误',
    message: '后端服务出现异常。',
    suggestion: '查看后端日志，或联系开发者反馈问题。',
  },
]

export function friendlyError(error: unknown): FriendlyError {
  const original = error instanceof Error ? error.message : String(error)

  for (const rule of ERROR_PATTERNS) {
    if (rule.pattern.test(original)) {
      return {
        category: rule.category,
        title: rule.title,
        message: rule.message,
        suggestion: rule.suggestion,
        original,
      }
    }
  }

  return {
    category: 'unknown',
    title: '发生未知错误',
    message: original || '操作未完成，请重试。',
    suggestion: '如问题持续，请通过 GitHub Issue 反馈。',
    original,
  }
}

/** 友好的错误展示组件 props */
export function errorToastProps(error: unknown) {
  const fe = friendlyError(error)
  return {
    title: fe.title,
    description: fe.suggestion ? `${fe.message}\n${fe.suggestion}` : fe.message,
    variant: 'destructive' as const,
  }
}
