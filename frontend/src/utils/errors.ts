import axios from 'axios'

export interface AppError {
  type: string
  code: string
  title: string
  detail: string
  suggestion: string
  status: number
  retryable: boolean
  diagnostics?: Record<string, unknown>
}

export type ErrorLike = AppError | string | Error | unknown

export function normalizeApiError(error: ErrorLike, fallbackTitle = '操作失败'): AppError {
  if (isAppError(error)) return error

  if (axios.isAxiosError(error)) {
    const data = error.response?.data
    if (isAppError(data?.error)) return data.error
    if (typeof data?.error === 'string') {
      return legacyMessageToError(data.error, data.error_message || fallbackTitle, error.response?.status)
    }
    if (typeof data?.error_message === 'string') {
      return legacyMessageToError(data.error_message, fallbackTitle, error.response?.status)
    }
    if (!error.response) {
      return legacyMessageToError(
        error.message || '网络连接失败',
        '网络连接失败',
        0,
        '请确认后端服务已启动，并检查浏览器网络连接。'
      )
    }
    return legacyMessageToError(error.message, fallbackTitle, error.response.status)
  }

  const maybeData = error as {
    error?: unknown
    error_message?: unknown
    message?: unknown
    status?: number
  } | null | undefined
  if (isAppError(maybeData?.error)) return maybeData.error
  if (typeof maybeData?.error === 'string') {
    const fallback = typeof maybeData.error_message === 'string' ? maybeData.error_message : fallbackTitle
    return legacyMessageToError(maybeData.error, fallback, maybeData.status)
  }
  if (typeof maybeData?.message === 'string') {
    return legacyMessageToError(maybeData.message, fallbackTitle, maybeData.status)
  }
  if (typeof error === 'string') {
    return legacyMessageToError(error, fallbackTitle)
  }

  return legacyMessageToError('请稍后重试；如果持续失败，请复制诊断信息反馈。', fallbackTitle)
}

/** 错误消息中 detail 首行的展示长度上限（避免上游原始错误撑爆提示框） */
const DETAIL_PREVIEW_MAX_LENGTH = 120

export function formatErrorMessage(error: ErrorLike, fallbackTitle = '操作失败'): string {
  const appError = normalizeApiError(error, fallbackTitle)
  const main = `${appError.title}：${appError.suggestion || appError.detail}`
  // 在「标题：建议」之外补显 detail 首行——只显示 title+suggestion 会把
  // 真实原因藏住（如内容安全拦截的具体文案），用户无从判断该改什么
  const detailLine = firstMeaningfulLine(appError.detail)
  if (!detailLine || main.includes(detailLine)) return main
  return `${main}（原因：${truncateText(detailLine, DETAIL_PREVIEW_MAX_LENGTH)}）`
}

function firstMeaningfulLine(value: string): string {
  if (!value) return ''
  return value.split('\n').map(line => line.trim()).find(Boolean) || ''
}

function truncateText(value: string, limit: number): string {
  if (value.length <= limit) return value
  return `${value.slice(0, limit - 1)}…`
}

export function diagnosticsText(error: AppError): string {
  const payload = {
    code: error.code,
    title: error.title,
    detail: error.detail,
    suggestion: error.suggestion,
    status: error.status,
    retryable: error.retryable,
    diagnostics: error.diagnostics || {}
  }
  return JSON.stringify(payload, null, 2)
}

function isAppError(value: unknown): value is AppError {
  if (!value || typeof value !== 'object') return false
  const candidate = value as Record<string, unknown>
  return typeof candidate.code === 'string'
    && typeof candidate.title === 'string'
    && typeof candidate.detail === 'string'
}

function legacyMessageToError(
  message: string,
  fallbackTitle = '操作失败',
  status = 500,
  suggestion?: string
): AppError {
  const clean = message || '发生未知错误'
  const firstLine = clean.split('\n').map(line => line.trim()).find(Boolean) || fallbackTitle

  return {
    type: `https://redink.app/errors/${inferCode(clean).toLowerCase().replace(/_/g, '-')}`,
    code: inferCode(clean),
    title: inferTitle(clean, fallbackTitle),
    detail: firstLine,
    suggestion: suggestion || inferSuggestion(clean),
    status: status || 500,
    retryable: inferRetryable(clean),
    diagnostics: {
      raw: clean
    }
  }
}

function inferCode(message: string): string {
  const text = message.toLowerCase()
  if (text.includes('proxyerror') || (text.includes('connection refused') && text.includes('127.0.0.1'))) return 'PROXY_UNAVAILABLE'
  if (text.includes('ssleoferror') || text.includes('unexpected_eof') || text.includes('198.18.')) return 'NETWORK_FAKE_IP_TLS'
  if (message.includes('不支持 /v1/chat/completions')) return 'MODEL_ENDPOINT_MISMATCH'
  if (text.includes('405') || text.includes('method not allowed') || text.includes('not allowed')) return 'ENDPOINT_METHOD_MISMATCH'
  if (text.includes('401') || text.includes('403') || text.includes('unauthorized') || text.includes('forbidden')) return 'AUTH_OR_PERMISSION'
  if (text.includes('429') || text.includes('rate') || message.includes('配额') || message.includes('限流')) return 'RATE_LIMITED'
  if (text.includes('timeout') || message.includes('超时')) return 'NETWORK_TIMEOUT'
  if (message.includes('不存在') || text.includes('not found')) return 'RESOURCE_NOT_FOUND'
  return 'UNKNOWN_ERROR'
}

function inferTitle(message: string, fallbackTitle: string): string {
  const code = inferCode(message)
  const titles: Record<string, string> = {
    PROXY_UNAVAILABLE: '本机代理不可用',
    NETWORK_FAKE_IP_TLS: '网络代理连接异常',
    MODEL_ENDPOINT_MISMATCH: '模型与接口不匹配',
    ENDPOINT_METHOD_MISMATCH: '接口路径或请求方法不匹配',
    AUTH_OR_PERMISSION: 'API Key 或权限不可用',
    RATE_LIMITED: '上游限流或配额不足',
    NETWORK_TIMEOUT: '网络请求超时',
    RESOURCE_NOT_FOUND: '资源不存在',
    UNKNOWN_ERROR: fallbackTitle
  }
  return titles[code] || fallbackTitle
}

function inferSuggestion(message: string): string {
  const code = inferCode(message)
  const suggestions: Record<string, string> = {
    PROXY_UNAVAILABLE: '请确认代理客户端已开启，且 HTTP/HTTPS 代理端口正在监听。',
    NETWORK_FAKE_IP_TLS: '请确认代理客户端已开启，或关闭 Fake-IP DNS 后重试。',
    MODEL_ENDPOINT_MISMATCH: '请在设置中换成支持当前接口的模型，或调整服务商 endpoint_type。',
    ENDPOINT_METHOD_MISMATCH: '请确认该服务商支持 OpenAI 兼容接口，并检查 Base URL、/v1 路径和 endpoint_type。',
    AUTH_OR_PERMISSION: '请检查 API Key、模型访问权限、账户余额和服务商配置。',
    RATE_LIMITED: '请稍后重试，或降低并发/检查账户配额。',
    NETWORK_TIMEOUT: '请检查网络、代理和服务商状态后重试。',
    RESOURCE_NOT_FOUND: '请返回列表刷新后重试。',
    UNKNOWN_ERROR: '请稍后重试；如果持续失败，请复制诊断信息反馈。'
  }
  return suggestions[code] || suggestions.UNKNOWN_ERROR
}

function inferRetryable(message: string): boolean {
  const code = inferCode(message)
  return ['PROXY_UNAVAILABLE', 'NETWORK_FAKE_IP_TLS', 'RATE_LIMITED', 'NETWORK_TIMEOUT', 'UNKNOWN_ERROR'].includes(code)
}
