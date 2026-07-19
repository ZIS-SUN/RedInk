import { describe, expect, it } from 'vitest'
import { appendQueryParam, withCacheBuster } from '../url'

describe('appendQueryParam', () => {
  it('无 query 时用 ? 追加', () => {
    expect(appendQueryParam('/api/images/task_1/0.png', 'a', '1'))
      .toBe('/api/images/task_1/0.png?a=1')
  })

  it('已有 query 时用 & 追加（不会出现双问号）', () => {
    const result = appendQueryParam('/api/images/task_1/0.png?thumbnail=true', 't', '123')
    expect(result).toBe('/api/images/task_1/0.png?thumbnail=true&t=123')
    expect(result.split('?').length).toBe(2)
  })

  it('同名参数会被覆盖而不是重复追加', () => {
    const result = appendQueryParam('/a?t=1', 't', '2')
    expect(result).toBe('/a?t=2')
  })

  it('绝对 URL 保持绝对形式', () => {
    const result = appendQueryParam('https://example.com/img.png?x=1', 't', '9')
    expect(result).toBe('https://example.com/img.png?x=1&t=9')
  })
})

describe('withCacheBuster', () => {
  it('追加 t 时间戳参数', () => {
    const result = withCacheBuster('/api/images/task_1/0.png?thumbnail=true')
    expect(result).toMatch(/^\/api\/images\/task_1\/0\.png\?thumbnail=true&t=\d+$/)
  })
})
