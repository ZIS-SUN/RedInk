import { describe, expect, it } from 'vitest'
import {
  diagnosticsText,
  formatErrorMessage,
  normalizeApiError,
  type AppError
} from '../errors'

const appError: AppError = {
  type: 'https://redink.app/errors/rate-limited',
  code: 'RATE_LIMITED',
  title: '上游限流或配额不足',
  detail: '429 Too Many Requests',
  suggestion: '请稍后重试',
  status: 429,
  retryable: true
}

describe('normalizeApiError', () => {
  it('已是 AppError 时原样返回', () => {
    expect(normalizeApiError(appError)).toBe(appError)
  })

  it('字符串错误会被转成 AppError 并推断错误码', () => {
    const result = normalizeApiError('Request timeout after 30s')
    expect(result.code).toBe('NETWORK_TIMEOUT')
    expect(result.retryable).toBe(true)
    expect(result.diagnostics?.raw).toBe('Request timeout after 30s')
  })

  it('包含 401 的错误信息推断为鉴权错误且不可重试', () => {
    const result = normalizeApiError('HTTP 401 Unauthorized')
    expect(result.code).toBe('AUTH_OR_PERMISSION')
    expect(result.retryable).toBe(false)
  })

  it('未知错误使用 fallbackTitle 兜底', () => {
    const result = normalizeApiError(null, '图片生成失败')
    expect(result.title).toBe('图片生成失败')
    expect(result.code).toBe('UNKNOWN_ERROR')
  })

  it('带 error 字段的对象（后端 SSE error 事件）可以被归一化', () => {
    const result = normalizeApiError({ error: appError })
    expect(result).toBe(appError)
  })

  it('Error 实例通过 message 归一化', () => {
    const result = normalizeApiError(new Error('资源不存在'))
    expect(result.code).toBe('RESOURCE_NOT_FOUND')
  })
})

describe('formatErrorMessage', () => {
  it('格式为 标题：建议', () => {
    expect(formatErrorMessage(appError)).toBe('上游限流或配额不足：请稍后重试')
  })

  it('没有 suggestion 时使用 detail', () => {
    const noSuggestion = { ...appError, suggestion: '' }
    expect(formatErrorMessage(noSuggestion)).toBe('上游限流或配额不足：429 Too Many Requests')
  })
})

describe('diagnosticsText', () => {
  it('输出可解析的 JSON 且包含关键信息', () => {
    const text = diagnosticsText(appError)
    const parsed = JSON.parse(text)
    expect(parsed.code).toBe('RATE_LIMITED')
    expect(parsed.status).toBe(429)
    expect(parsed.retryable).toBe(true)
  })
})
