import { describe, expect, it, vi } from 'vitest'
import { SseParser, readSseResponse } from '../client'

describe('SseParser', () => {
  it('解析一条完整的事件消息', () => {
    const parser = new SseParser()
    const messages = parser.push('event: progress\ndata: {"index":0}\n\n')
    expect(messages).toEqual([{ event: 'progress', data: '{"index":0}' }])
  })

  it('未指定 event 字段时默认为 message', () => {
    const parser = new SseParser()
    const messages = parser.push('data: hello\n\n')
    expect(messages).toEqual([{ event: 'message', data: 'hello' }])
  })

  it('粘包：一个 chunk 里包含多条事件时全部拆出', () => {
    const parser = new SseParser()
    const messages = parser.push(
      'event: a\ndata: 1\n\nevent: b\ndata: 2\n\ndata: 3\n\n'
    )
    expect(messages).toEqual([
      { event: 'a', data: '1' },
      { event: 'b', data: '2' },
      { event: 'message', data: '3' }
    ])
  })

  it('分包：事件被拆成多个 chunk（甚至在行中间截断）也能正确拼装', () => {
    const parser = new SseParser()
    // 在字段名、数据中间任意位置截断
    expect(parser.push('ev')).toEqual([])
    expect(parser.push('ent: comp')).toEqual([])
    expect(parser.push('lete\ndata: {"ok"')).toEqual([])
    expect(parser.push(':true}\n')).toEqual([])
    // 收到空行分隔符才派发
    expect(parser.push('\n')).toEqual([
      { event: 'complete', data: '{"ok":true}' }
    ])
  })

  it('多行 data 按规范用换行符拼接', () => {
    const parser = new SseParser()
    const messages = parser.push('data: line1\ndata: line2\n\n')
    expect(messages).toEqual([{ event: 'message', data: 'line1\nline2' }])
  })

  it('兼容 \\r\\n 换行', () => {
    const parser = new SseParser()
    const messages = parser.push('event: x\r\ndata: y\r\n\r\n')
    expect(messages).toEqual([{ event: 'x', data: 'y' }])
  })

  it('忽略注释行与 id/retry 字段', () => {
    const parser = new SseParser()
    const messages = parser.push(
      ': keep-alive\nid: 7\nretry: 3000\ndata: payload\n\n'
    )
    expect(messages).toEqual([{ event: 'message', data: 'payload' }])
  })

  it('只有 event 没有 data 的空消息不派发，且不污染下一条消息', () => {
    const parser = new SseParser()
    expect(parser.push('event: ghost\n\n')).toEqual([])
    // 上一条的 event 类型已被重置
    expect(parser.push('data: real\n\n')).toEqual([
      { event: 'message', data: 'real' }
    ])
  })

  it('data 值可以包含冒号，且只去掉字段冒号后的第一个空格', () => {
    const parser = new SseParser()
    const messages = parser.push('data:  {"url":"http://a/b"}\n\n')
    // 第一个空格被剥掉，之后的内容原样保留
    expect(messages).toEqual([{ event: 'message', data: ' {"url":"http://a/b"}' }])
  })

  it('未以空行结尾的尾部数据留在缓冲区，等待后续 chunk', () => {
    const parser = new SseParser()
    expect(parser.push('data: pending\n')).toEqual([])
    expect(parser.push('\n')).toEqual([{ event: 'message', data: 'pending' }])
  })
})

/** 用字符串 chunk 序列构造一个可传给 readSseResponse 的假 Response */
function makeSseResponse(chunks: string[]): Response {
  const encoder = new TextEncoder()
  const body = new ReadableStream<Uint8Array>({
    start(controller) {
      for (const chunk of chunks) {
        controller.enqueue(encoder.encode(chunk))
      }
      controller.close()
    }
  })
  return { body } as unknown as Response
}

describe('readSseResponse', () => {
  it('按事件类型分发 JSON payload，并支持跨 chunk 的分包', async () => {
    const progress: unknown[] = []
    const finish: unknown[] = []

    const response = makeSseResponse([
      'event: progress\ndata: {"ind',
      'ex":0}\n\nevent: finish\ndata: {"success":true}\n\n'
    ])

    await readSseResponse(response, {
      progress: (data) => progress.push(data),
      finish: (data) => finish.push(data)
    })

    expect(progress).toEqual([{ index: 0 }])
    expect(finish).toEqual([{ success: true }])
  })

  it('流结束时未以空行收尾的最后一条消息也会被派发（flush）', async () => {
    const received: unknown[] = []
    // 注意结尾没有空行分隔符
    const response = makeSseResponse(['event: last\ndata: {"n":1}\n'])

    await readSseResponse(response, {
      last: (data) => received.push(data)
    })

    expect(received).toEqual([{ n: 1 }])
  })

  it('没有对应 handler 的事件被安静跳过', async () => {
    const received: unknown[] = []
    const response = makeSseResponse([
      'event: unknown\ndata: {}\n\nevent: known\ndata: {"v":2}\n\n'
    ])

    await readSseResponse(response, {
      known: (data) => received.push(data)
    })

    expect(received).toEqual([{ v: 2 }])
  })

  it('空闲超时：超过 idleTimeout 没有数据时抛错中断并取消底层流', async () => {
    // 用 mock reader 模拟 read 永远挂起且 cancel 不打断 read 的情况，
    // 确保超时分支确定性地走到 reject（原生流的 cancel 会先把 read 置为 done）
    const cancel = vi.fn().mockResolvedValue(undefined)
    const releaseLock = vi.fn()
    const reader = {
      read: () => new Promise<never>(() => {}),
      cancel,
      releaseLock
    }
    const response = { body: { getReader: () => reader } } as unknown as Response

    await expect(
      readSseResponse(response, {}, { idleTimeout: 30 })
    ).rejects.toThrow(/空闲/)
    expect(cancel).toHaveBeenCalled()
    expect(releaseLock).toHaveBeenCalled()
  })

  it('空闲超时保护：真实流悬挂时调用会在超时后结束，不会永远挂起', async () => {
    // 一个永远不产出数据也不结束的流；若超时保护失效，本用例会超时失败
    const body = new ReadableStream<Uint8Array>({
      pull: () => new Promise<never>(() => {})
    })
    const response = { body } as unknown as Response

    // 原生流下 cancel 会让挂起的 read 以 done 结束，调用以 resolve 收场；
    // 这里只断言「必须在空闲超时后返回」，无论 resolve 还是 reject
    await readSseResponse(response, {}, { idleTimeout: 30 }).catch(() => {})
  })

  it('signal 已中止时立即抛出取消错误', async () => {
    const controller = new AbortController()
    controller.abort()

    const response = makeSseResponse(['data: {}\n\n'])

    await expect(
      readSseResponse(response, {}, { signal: controller.signal })
    ).rejects.toThrow('请求已取消')
  })
})
