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
  it('格式为 标题：建议，并补显 detail 首行（真实原因不被藏住）', () => {
    expect(formatErrorMessage(appError)).toBe(
      '上游限流或配额不足：请稍后重试（原因：429 Too Many Requests）'
    )
  })

  it('没有 suggestion 时使用 detail，不重复展示', () => {
    const noSuggestion = { ...appError, suggestion: '' }
    expect(formatErrorMessage(noSuggestion)).toBe('上游限流或配额不足：429 Too Many Requests')
  })

  it('detail 与 suggestion 相同时不重复展示', () => {
    const duplicated = { ...appError, detail: '请稍后重试' }
    expect(formatErrorMessage(duplicated)).toBe('上游限流或配额不足：请稍后重试')
  })

  it('多行 detail 只取首个非空行', () => {
    const blocked: AppError = {
      ...appError,
      code: 'CONTENT_BLOCKED',
      title: '内容被安全审核拦截',
      detail: '\n  🛡️ 内容被安全过滤器拦截\n【说明】您的提示词触发了安全过滤机制。',
      suggestion: '请修改该页文案后重试（更换敏感表述）。',
      retryable: false
    }
    expect(formatErrorMessage(blocked)).toBe(
      '内容被安全审核拦截：请修改该页文案后重试（更换敏感表述）。' +
      '（原因：🛡️ 内容被安全过滤器拦截）'
    )
  })

  it('detail 首行超长时截断，避免撑爆提示框', () => {
    const longDetail = { ...appError, detail: 'x'.repeat(300) }
    const message = formatErrorMessage(longDetail)
    expect(message).toContain('（原因：')
    expect(message.length).toBeLessThan(200)
    expect(message.endsWith('…）')).toBe(true)
  })

  it('detail 为空时保持 标题：建议', () => {
    const noDetail = { ...appError, detail: '' }
    expect(formatErrorMessage(noDetail)).toBe('上游限流或配额不足：请稍后重试')
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
