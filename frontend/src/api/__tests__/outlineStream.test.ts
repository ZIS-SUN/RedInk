import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  OUTLINE_STREAM_INTERRUPTED_MESSAGE,
  OutlineStreamFallbackError,
  appendOutlineDelta,
  generateOutlineStream,
  resolveOutlineStreamResult,
  shouldFallbackToNonStream
} from '../outline'
import { createAbortError } from '../client'
import type { OutlineResponse, Page } from '../types'

// ==================== 纯函数：增量拼接 ====================

describe('appendOutlineDelta', () => {
  it('拼接字符串增量', () => {
    expect(appendOutlineDelta('', '标题：')).toBe('标题：')
    expect(appendOutlineDelta('标题：', '秋日穿搭')).toBe('标题：秋日穿搭')
  })

  it('忽略非字符串的 delta payload', () => {
    expect(appendOutlineDelta('已有', undefined)).toBe('已有')
    expect(appendOutlineDelta('已有', null)).toBe('已有')
    expect(appendOutlineDelta('已有', 123)).toBe('已有')
    expect(appendOutlineDelta('已有', { text: 'x' })).toBe('已有')
  })
})

// ==================== 纯函数：回退判定 ====================

describe('shouldFallbackToNonStream', () => {
  it('流式不可用信号错误 → 回退', () => {
    expect(shouldFallbackToNonStream(new OutlineStreamFallbackError('HTTP 404'))).toBe(true)
  })

  it('主动取消不回退', () => {
    expect(shouldFallbackToNonStream(createAbortError())).toBe(false)
  })

  it('其他普通错误不回退（交给上层展示）', () => {
    expect(shouldFallbackToNonStream(new Error('boom'))).toBe(false)
    expect(shouldFallbackToNonStream('字符串错误')).toBe(false)
    expect(shouldFallbackToNonStream(undefined)).toBe(false)
  })
})

// ==================== 纯函数：流式结果归并 ====================

const PAGES: Page[] = [{ index: 0, type: 'cover', content: '[封面]\n标题：测试' }]

describe('resolveOutlineStreamResult', () => {
  it('有 complete 事件时返回成功结果', () => {
    const complete: OutlineResponse & { has_images?: boolean } = {
      success: true,
      outline: '[封面]\n标题：测试',
      pages: PAGES,
      has_images: false
    }
    expect(resolveOutlineStreamResult(complete, null)).toBe(complete)
  })

  it('只有 error 事件时返回结构化失败结果', () => {
    const result = resolveOutlineStreamResult(null, {
      error: { code: 'RATE_LIMITED' } as never,
      message: '上游限流'
    })
    expect(result.success).toBe(false)
    expect(result.error_message).toBe('上游限流')
  })

  it('complete 不完整（无 pages）且无 error 时抛回退错误', () => {
    expect(() => resolveOutlineStreamResult({ success: true }, null))
      .toThrow(OutlineStreamFallbackError)
  })

  it('两者都没有（流被截断）时抛回退错误', () => {
    expect(() => resolveOutlineStreamResult(null, null))
      .toThrow(OutlineStreamFallbackError)
  })

  it('已收到 delta 后截断 → 抛普通错误而不是回退信号（避免双倍 token）', () => {
    let caught: unknown
    try {
      resolveOutlineStreamResult(null, null, { receivedDelta: true })
    } catch (err) {
      caught = err
    }
    expect(caught).toBeInstanceOf(Error)
    expect(caught).not.toBeInstanceOf(OutlineStreamFallbackError)
    expect((caught as Error).message).toBe(OUTLINE_STREAM_INTERRUPTED_MESSAGE)
    expect(shouldFallbackToNonStream(caught)).toBe(false)
  })

  it('已收到 delta 但服务端给出结构化 error 时仍按真实错误返回', () => {
    const result = resolveOutlineStreamResult(
      null,
      { message: '上游限流' },
      { receivedDelta: true }
    )
    expect(result.success).toBe(false)
    expect(result.error_message).toBe('上游限流')
  })
})

// ==================== 集成：generateOutlineStream ====================

/** 用字符串 chunk 序列构造一个 SSE fetch Response */
function makeSseFetchResponse(chunks: string[], ok = true, status = 200): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    }
  })
  return { ok, status, body } as unknown as Response
}

/** 构造一个发送若干 chunk 后以网络错误中断的 SSE Response
 *（用 pull 逐块下发，保证 chunk 先被消费到再中断——start 里直接 error 会丢弃队列） */
function makeErroringSseResponse(chunks: string[], error: Error): Response {
  const encoder = new TextEncoder()
  let index = 0
  const body = new ReadableStream<Uint8Array>({
    pull(controller) {
      if (index < chunks.length) {
        controller.enqueue(encoder.encode(chunks[index]))
        index += 1
      } else {
        controller.error(error)
      }
    }
  })
  return { ok: true, status: 200, body } as unknown as Response
}

function sse(event: string, data: unknown): string {
  return `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('generateOutlineStream', () => {
  it('delta → complete → finish：回调增量并返回完成结果', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeSseFetchResponse([
      sse('delta', { text: '[封面]\n' }),
      sse('delta', { text: '标题：测试' }),
      sse('complete', {
        success: true,
        outline: '[封面]\n标题：测试',
        pages: PAGES,
        has_images: false
      }),
      sse('finish', { success: true })
    ])))

    const received: string[] = []
    const result = await generateOutlineStream('测试主题', undefined, {
      onDelta: (fullText) => received.push(fullText)
    })

    expect(received).toEqual(['[封面]\n', '[封面]\n标题：测试'])
    expect(result.success).toBe(true)
    expect(result.outline).toBe('[封面]\n标题：测试')
    expect(result.pages).toEqual(PAGES)
  })

  it('携带 brand_id 时包含在请求体中，不携带时省略该键', async () => {
    // 每次调用构造新的 Response（流只能被消费一次）
    const fetchMock = vi.fn().mockImplementation(async () => makeSseFetchResponse([
      sse('complete', { success: true, outline: 'x', pages: PAGES }),
      sse('finish', { success: true })
    ]))
    vi.stubGlobal('fetch', fetchMock)

    await generateOutlineStream('主题', 'brand-1')
    expect(JSON.parse(fetchMock.mock.calls[0][1].body)).toEqual({
      topic: '主题',
      brand_id: 'brand-1'
    })

    await generateOutlineStream('主题')
    expect(JSON.parse(fetchMock.mock.calls[1][1].body)).toEqual({ topic: '主题' })
  })

  it('服务端 error 事件 → 返回结构化失败结果（不回退）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeSseFetchResponse([
      sse('delta', { text: '第一段' }),
      sse('error', {
        success: false,
        error: { code: 'RATE_LIMITED', title: '上游限流', detail: 'x' },
        message: '上游限流：请稍后重试'
      }),
      sse('finish', { success: false })
    ])))

    const result = await generateOutlineStream('主题')
    expect(result.success).toBe(false)
    expect(result.error_message).toBe('上游限流：请稍后重试')
  })

  it('HTTP 非 2xx（如后端不支持流式）→ 抛回退错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeSseFetchResponse([], false, 400)
    ))

    await expect(generateOutlineStream('主题'))
      .rejects.toThrow(OutlineStreamFallbackError)
  })

  it('网络异常 → 抛回退错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(new TypeError('Failed to fetch')))

    await expect(generateOutlineStream('主题'))
      .rejects.toThrow(OutlineStreamFallbackError)
  })

  it('流被截断且一个 delta 都没收到 → 抛回退错误（可安全自动回退非流式）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeSseFetchResponse([])))

    await expect(generateOutlineStream('主题'))
      .rejects.toThrow(OutlineStreamFallbackError)
  })

  it('已收到部分 delta 后流被截断 → 抛普通错误（不静默回退重付费）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(makeSseFetchResponse([
      sse('delta', { text: '只有增量' })
    ])))

    const caught = await generateOutlineStream('主题').then(
      () => { throw new Error('应当抛错') },
      (err: unknown) => err
    )
    expect(caught).toBeInstanceOf(Error)
    expect(caught).not.toBeInstanceOf(OutlineStreamFallbackError)
    expect((caught as Error).message).toBe(OUTLINE_STREAM_INTERRUPTED_MESSAGE)
    // 上层 shouldFallbackToNonStream 判定不回退 → 错误会被展示而不是重付费
    expect(shouldFallbackToNonStream(caught)).toBe(false)
  })

  it('读流网络异常且未收到任何 delta → 抛回退错误', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeErroringSseResponse([], new TypeError('network error'))
    ))

    await expect(generateOutlineStream('主题'))
      .rejects.toThrow(OutlineStreamFallbackError)
  })

  it('读流网络异常但已收到部分 delta → 抛普通错误（不静默回退）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockResolvedValue(
      makeErroringSseResponse(
        [sse('delta', { text: '已产出的部分内容' })],
        new TypeError('network error')
      )
    ))

    const received: string[] = []
    const caught = await generateOutlineStream('主题', undefined, {
      onDelta: (fullText) => received.push(fullText)
    }).then(
      () => { throw new Error('应当抛错') },
      (err: unknown) => err
    )
    expect(received).toEqual(['已产出的部分内容'])
    expect(caught).not.toBeInstanceOf(OutlineStreamFallbackError)
    expect((caught as Error).message).toBe(OUTLINE_STREAM_INTERRUPTED_MESSAGE)
    expect(shouldFallbackToNonStream(caught)).toBe(false)
  })

  it('主动取消 → 原样抛出取消错误（不转为回退信号）', async () => {
    vi.stubGlobal('fetch', vi.fn().mockRejectedValue(createAbortError()))

    const controller = new AbortController()
    controller.abort()
    await expect(
      generateOutlineStream('主题', undefined, {}, { signal: controller.signal })
    ).rejects.toSatisfy((err: unknown) => !shouldFallbackToNonStream(err))
  })
})
