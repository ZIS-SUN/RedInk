import axios, { type AxiosInstance } from 'axios'
import { normalizeApiError, type AppError } from '../utils/errors'

export const API_BASE_URL = '/api'

/** 普通接口的默认超时 */
export const DEFAULT_TIMEOUT = 15_000

/** LLM 类接口（大纲/文案/连通性测试）的超时，生成耗时较长 */
export const LLM_TIMEOUT = 120_000

/** SSE 流的空闲超时：超过该时间没有收到任何字节则认为断流 */
export const SSE_IDLE_TIMEOUT = 90_000

/**
 * 统一的 axios 实例：
 * - 统一 baseURL 和默认超时
 * - 响应拦截器里把错误归一化为 AppError，挂到 error.appError 上，
 *   调用方可以直接读取，也可以继续走 normalizeApiError（幂等）
 */
export const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT
})

http.interceptors.response.use(
  response => response,
  (error: unknown) => {
    const appError = normalizeApiError(error)
    if (error && typeof error === 'object') {
      ;(error as { appError?: AppError }).appError = appError
    }
    return Promise.reject(error)
  }
)

export function getApiErrorPayload(error: unknown, fallback: string): {
  error: AppError | string
  error_message: string
} {
  const appError = (error as { appError?: AppError } | null)?.appError
    || normalizeApiError(error, fallback)
  return {
    error: appError,
    error_message: appError.detail || fallback
  }
}

export async function readErrorResponse(response: Response, fallback: string) {
  try {
    return await response.json()
  } catch {
    return new Error(fallback)
  }
}

interface SseMessage {
  event: string
  data: string
}

/**
 * SSE 逐行解析状态机
 * 按规范处理：多行 data 拼接、注释行（: 开头）忽略、event/id/retry 字段、\r\n 兼容
 */
export class SseParser {
  private buffer = ''
  private eventType = ''
  private dataLines: string[] = []

  /** 喂入一段文本，返回解析出的完整消息列表 */
  push(chunk: string): SseMessage[] {
    this.buffer += chunk
    const messages: SseMessage[] = []

    let newlineIndex: number
    while ((newlineIndex = this.buffer.indexOf('\n')) !== -1) {
      let line = this.buffer.slice(0, newlineIndex)
      this.buffer = this.buffer.slice(newlineIndex + 1)
      if (line.endsWith('\r')) line = line.slice(0, -1)

      const message = this.processLine(line)
      if (message) messages.push(message)
    }

    return messages
  }

  private processLine(line: string): SseMessage | null {
    // 空行 = 消息分隔符，派发已累积的事件
    if (line === '') {
      if (this.dataLines.length === 0) {
        this.eventType = ''
        return null
      }
      const message: SseMessage = {
        event: this.eventType || 'message',
        data: this.dataLines.join('\n')
      }
      this.eventType = ''
      this.dataLines = []
      return message
    }

    // 注释行，忽略
    if (line.startsWith(':')) return null

    const colonIndex = line.indexOf(':')
    const field = colonIndex === -1 ? line : line.slice(0, colonIndex)
    let value = colonIndex === -1 ? '' : line.slice(colonIndex + 1)
    if (value.startsWith(' ')) value = value.slice(1)

    switch (field) {
      case 'event':
        this.eventType = value
        break
      case 'data':
        this.dataLines.push(value)
        break
      // id / retry 字段合法但当前用不到，静默忽略
      default:
        break
    }
    return null
  }
}

export interface ReadSseOptions {
  /** 空闲超时（毫秒）：超过该时间没有收到任何数据则中断，默认 SSE_IDLE_TIMEOUT */
  idleTimeout?: number
  /** 取消信号：中止时停止读取（fetch 传入同一 signal 时 read 会自行抛 AbortError） */
  signal?: AbortSignal
}

/**
 * 读取 SSE 响应流并按事件类型分发
 * - 逐行状态机解析（支持多行 data、注释、\r\n）
 * - 空闲超时保护：网络悬挂时不会永远卡住
 */
export async function readSseResponse(
  response: Response,
  // 各事件的 payload 类型不同，由调用方的回调签名收敛
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  handlers: Record<string, (data: any) => void>,
  options: ReadSseOptions = {}
) {
  const reader = response.body?.getReader()
  if (!reader) {
    throw new Error('无法读取响应流')
  }

  const idleTimeout = options.idleTimeout ?? SSE_IDLE_TIMEOUT
  const decoder = new TextDecoder()
  const parser = new SseParser()

  const dispatch = (messages: SseMessage[]) => {
    for (const message of messages) {
      const handler = handlers[message.event]
      if (!handler) continue
      try {
        const data = JSON.parse(message.data)
        handler(data)
      } catch (e) {
        console.error('解析 SSE 数据失败:', e)
      }
    }
  }

  try {
    while (true) {
      if (options.signal?.aborted) {
        throw createAbortError()
      }

      const result = await readWithIdleTimeout(reader, idleTimeout)
      if (result.done) break

      dispatch(parser.push(decoder.decode(result.value, { stream: true })))
    }
    // flush 解码器缓冲和最后一条可能未以空行结尾的消息
    dispatch(parser.push(decoder.decode()))
    dispatch(parser.push('\n\n'))
  } finally {
    reader.releaseLock()
  }
}

async function readWithIdleTimeout(
  reader: ReadableStreamDefaultReader<Uint8Array>,
  idleTimeout: number
): Promise<ReadableStreamReadResult<Uint8Array>> {
  let timer: ReturnType<typeof setTimeout> | undefined
  const timeoutPromise = new Promise<never>((_, reject) => {
    timer = setTimeout(() => {
      // 取消底层流，让挂起的 read 尽快结束
      reader.cancel().catch(() => {})
      reject(new Error(`连接空闲超过 ${Math.round(idleTimeout / 1000)} 秒，已中断，请检查网络后重试`))
    }, idleTimeout)
  })

  try {
    return await Promise.race([reader.read(), timeoutPromise])
  } finally {
    if (timer !== undefined) clearTimeout(timer)
  }
}

export function createAbortError(): Error {
  const error = new Error('请求已取消')
  error.name = 'AbortError'
  return error
}

/** 判断错误是否为主动取消（AbortController.abort 触发） */
export function isAbortError(error: unknown): boolean {
  return error instanceof Error
    && (error.name === 'AbortError' || error.message === '请求已取消')
}
