import axios, { type AxiosInstance } from 'axios'
import { normalizeApiError, type AppError } from '../utils/errors'

export const API_BASE_URL = '/api'

/** 普通接口的默认超时 */
export const DEFAULT_TIMEOUT = 15_000

/**
 * LLM 类接口（大纲/文案/连通性测试/单张图片重绘）的超时。
 *
 * 对齐关系：后端上游单次请求预算为 300 秒（utils/text_client.py 与各
 * generators 统一 timeout=300s），前端超时必须覆盖后端单次最坏时长并留余量
 * （300s + 30s）。若前端先超时，后端线程仍在继续调用付费上游：
 * 120-300 秒之间完成的调用会被误判失败丢弃（单张重绘的结果甚至已写入
 * 历史），用户看到假失败后重试等于重复扣费。
 */
export const LLM_TIMEOUT = 330_000

/**
 * SSE 流的空闲超时：超过该时间没有收到任何字节则认为断流。
 *
 * 后端图片生成流在阻塞生成期间每 15 秒下发一次 heartbeat 事件保活
 * （backend/services/image.py HEARTBEAT_INTERVAL_SECONDS），正常慢生成
 * 不会再触发空闲熔断；这里放宽到 120 秒作为双保险，仅在后端进程挂死或
 * 网络真正悬挂时才断流。
 */
export const SSE_IDLE_TIMEOUT = 120_000

// ==================== 部署级访问令牌（REDINK_ACCESS_TOKEN） ====================

/** 访问令牌在 localStorage 中的存储键 */
export const ACCESS_TOKEN_STORAGE_KEY = 'redink:access-token'

/**
 * 部署级令牌 401 的统一用户提示。
 * 后端原文建议「在请求头携带 Authorization …」是给 API 调用方看的，
 * 页面用户需要的是「到哪里填」。
 */
export const ACCESS_TOKEN_UNAUTHORIZED_MESSAGE =
  '访问令牌缺失或不正确，请到 系统设置 → 访问安全 填写'

/** localStorage 的最小接口，便于测试注入（与 utils/localBackup.ts 的约定一致） */
export interface TokenStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

function defaultTokenStorage(): TokenStorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/** 读取已保存的访问令牌；未保存或存储不可用时返回空字符串 */
export function getAccessToken(
  storage: TokenStorageLike | null = defaultTokenStorage()
): string {
  if (!storage) return ''
  try {
    return (storage.getItem(ACCESS_TOKEN_STORAGE_KEY) || '').trim()
  } catch {
    return ''
  }
}

/** 保存访问令牌（自动去除首尾空白；空白串等价于清除） */
export function setAccessToken(
  token: string,
  storage: TokenStorageLike | null = defaultTokenStorage()
): void {
  const clean = (token || '').trim()
  if (!clean) {
    clearAccessToken(storage)
    return
  }
  if (!storage) return
  try {
    storage.setItem(ACCESS_TOKEN_STORAGE_KEY, clean)
  } catch {
    // 隐私模式/配额满等写入失败时静默：令牌只是无法持久化，不阻断页面
  }
}

/** 清除已保存的访问令牌 */
export function clearAccessToken(
  storage: TokenStorageLike | null = defaultTokenStorage()
): void {
  if (!storage) return
  try {
    storage.removeItem(ACCESS_TOKEN_STORAGE_KEY)
  } catch {
    // 同上，静默失败
  }
}

/**
 * 生成鉴权请求头：已保存令牌时返回 { 'X-Access-Token': token }，否则返回空对象。
 * 后端同时接受 Authorization: Bearer 与 X-Access-Token（backend/app.py），
 * 这里选用 X-Access-Token，避免与上游服务商的 Authorization 语义混淆。
 */
export function getAuthHeaders(
  storage: TokenStorageLike | null = defaultTokenStorage()
): Record<string, string> {
  const token = getAccessToken(storage)
  return token ? { 'X-Access-Token': token } : {}
}

/**
 * 把部署级令牌鉴权的 401 响应体（code=UNAUTHORIZED，见 backend/app.py
 * _register_access_token_auth）塑形为面向页面用户的标准错误结构，
 * normalizeApiError / ErrorCard 可直接消费。
 *
 * 仅处理部署级 401：上游 AI 服务商的 401/403 是 AUTH_OR_PERMISSION
 * （API Key 配置问题），原样保留不塑形。
 */
export function reshapeUnauthorizedPayload(data: unknown): unknown {
  const payload = data as { error?: { code?: string; detail?: string } } | null | undefined
  if (payload?.error?.code !== 'UNAUTHORIZED') return data

  const error: AppError = {
    type: 'https://redink.app/errors/unauthorized',
    code: 'UNAUTHORIZED',
    title: '访问未授权',
    detail: ACCESS_TOKEN_UNAUTHORIZED_MESSAGE,
    suggestion: getAccessToken()
      ? '当前填写的令牌与服务端不一致，请到 系统设置 → 访问安全 更新为与服务端 REDINK_ACCESS_TOKEN 相同的值。'
      : '请到 系统设置 → 访问安全 填写与服务端 REDINK_ACCESS_TOKEN 相同的访问令牌。',
    status: 401,
    retryable: false,
    diagnostics: { raw: payload.error.detail || '缺少或无效的访问令牌' }
  }
  return {
    success: false,
    error,
    error_message: `${error.title}：${error.detail}`
  }
}

/**
 * 统一的 axios 实例：
 * - 统一 baseURL 和默认超时
 * - 请求拦截器注入访问令牌请求头（未设置令牌时零行为变化）
 * - 响应拦截器里把错误归一化为 AppError，挂到 error.appError 上，
 *   调用方可以直接读取，也可以继续走 normalizeApiError（幂等）
 */
export const http: AxiosInstance = axios.create({
  baseURL: API_BASE_URL,
  timeout: DEFAULT_TIMEOUT
})

// 每次请求时重新读取令牌（设置页保存后立即生效，无需刷新页面）；
// 未设置令牌时 getAuthHeaders() 返回空对象，不添加任何请求头
http.interceptors.request.use(config => {
  for (const [key, value] of Object.entries(getAuthHeaders())) {
    config.headers.set(key, value)
  }
  return config
})

http.interceptors.response.use(
  response => response,
  (error: unknown) => {
    // 部署级令牌 401：先把响应体塑形为用户可行动的提示，再走统一归一化
    if (axios.isAxiosError(error) && error.response?.status === 401) {
      error.response.data = reshapeUnauthorizedPayload(error.response.data)
    }
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
    // 部署级令牌 401 同样塑形（SSE fetch 不经过 axios 拦截器）
    return reshapeUnauthorizedPayload(await response.json())
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
