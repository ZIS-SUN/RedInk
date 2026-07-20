import {
  API_BASE_URL,
  LLM_TIMEOUT,
  http,
  isAbortError,
  readSseResponse
} from './client'
import type { OutlineResponse } from './types'
import type { AppError } from '../utils/errors'

/** 单页润色指令：后端做白名单映射，未知值按 polish 处理 */
export type PolishInstruction = 'polish' | 'shorten' | 'punchier'

export interface PolishPageResponse {
  success: boolean
  content?: string
  error?: AppError | string
  error_message?: string
}

export async function generateOutline(
  topic: string,
  images?: File[],
  brandId?: string
): Promise<OutlineResponse & { has_images?: boolean }> {
  if (images && images.length > 0) {
    const formData = new FormData()
    formData.append('topic', topic)
    if (brandId) {
      formData.append('brand_id', brandId)
    }
    images.forEach((file) => {
      formData.append('images', file)
    })

    const response = await http.post<OutlineResponse & { has_images?: boolean }>(
      '/outline',
      formData,
      {
        headers: {
          'Content-Type': 'multipart/form-data'
        },
        // 大纲生成走 LLM，耗时较长
        timeout: LLM_TIMEOUT
      }
    )
    return response.data
  }

  const response = await http.post<OutlineResponse>(
    '/outline',
    // 不使用品牌人设时不携带 brand_id 键，保持向后兼容
    brandId ? { topic, brand_id: brandId } : { topic },
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}

/**
 * 流式接口不可用的信号错误：
 * HTTP 错误响应（如后端不支持流式/版本过旧）、网络异常、流意外终止
 * 都会抛出该错误，调用方据此无感回退到非流式 generateOutline。
 */
export class OutlineStreamFallbackError extends Error {
  constructor(message: string, public cause?: unknown) {
    super(message)
    this.name = 'OutlineStreamFallbackError'
  }
}

/** 判断流式调用抛出的错误是否应回退到非流式接口（主动取消不回退） */
export function shouldFallbackToNonStream(error: unknown): boolean {
  return error instanceof OutlineStreamFallbackError && !isAbortError(error)
}

/** 增量拼接：忽略非字符串的 delta payload，保证拼接结果始终是字符串 */
export function appendOutlineDelta(current: string, delta: unknown): string {
  return typeof delta === 'string' ? current + delta : current
}

/**
 * 归并流式事件的最终结果：
 * - 收到 complete 事件 → 返回与非流式接口同构的成功响应
 * - 只收到 error 事件 → 返回结构化失败响应（不回退，非流式会遇到同样的上游错误）
 * - 两者都没有（流被截断）→ 抛 OutlineStreamFallbackError，由调用方回退
 */
export function resolveOutlineStreamResult(
  complete: (OutlineResponse & { has_images?: boolean }) | null,
  errorEvent: { error?: AppError | string; message?: string } | null
): OutlineResponse & { has_images?: boolean } {
  if (complete && complete.success && complete.pages) {
    return complete
  }
  if (errorEvent) {
    return {
      success: false,
      error: errorEvent.error,
      error_message: errorEvent.message
    }
  }
  throw new OutlineStreamFallbackError('流式响应未包含完成事件')
}

export interface OutlineStreamHandlers {
  /** 每收到一段增量时回调：fullText 为已拼接的全文，delta 为本次增量 */
  onDelta?: (fullText: string, delta: string) => void
}

/**
 * 流式生成大纲（SSE，仅支持无图路径）
 *
 * 事件协议：delta（文本增量）→ complete（完整文本 + 结构化大纲）
 * → error（结构化错误）→ finish。
 *
 * 返回值与 generateOutline 同构；流式接口不可用（HTTP 错误/网络异常/
 * 流意外终止）时抛 OutlineStreamFallbackError，调用方应回退非流式接口。
 */
export async function generateOutlineStream(
  topic: string,
  brandId?: string,
  handlers: OutlineStreamHandlers = {},
  options: { signal?: AbortSignal } = {}
): Promise<OutlineResponse & { has_images?: boolean }> {
  let response: Response
  try {
    response = await fetch(`${API_BASE_URL}/outline/stream`, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json'
      },
      // 不使用品牌人设时不携带 brand_id 键，保持与非流式接口一致
      body: JSON.stringify(brandId ? { topic, brand_id: brandId } : { topic }),
      signal: options.signal
    })
  } catch (err) {
    // 主动取消原样抛出，网络异常转为回退信号
    if (isAbortError(err)) throw err
    throw new OutlineStreamFallbackError('流式接口网络异常', err)
  }

  if (!response.ok) {
    // 包含后端返回 STREAMING_NOT_SUPPORTED（激活服务商不支持流式）等情况
    throw new OutlineStreamFallbackError(`流式接口不可用：HTTP ${response.status}`)
  }

  let fullText = ''
  let complete: (OutlineResponse & { has_images?: boolean }) | null = null
  let errorEvent: { error?: AppError | string; message?: string } | null = null

  try {
    await readSseResponse(response, {
      delta: (data) => {
        const delta = data?.text
        const next = appendOutlineDelta(fullText, delta)
        if (next !== fullText) {
          fullText = next
          handlers.onDelta?.(fullText, delta as string)
        }
      },
      complete: (data) => {
        complete = data
      },
      error: (data) => {
        errorEvent = data
      }
    }, { signal: options.signal })
  } catch (err) {
    if (isAbortError(err)) throw err
    // 服务端已给出结构化错误时按真实错误返回，否则视为断流回退
    if (errorEvent) return resolveOutlineStreamResult(null, errorEvent)
    throw new OutlineStreamFallbackError('流式连接中断', err)
  }

  return resolveOutlineStreamResult(complete, errorEvent)
}

/**
 * 单页 AI 润色：对大纲中某一页的文案按指令重写
 *
 * @param brandId 品牌档案 ID（可选），提供时后端约束润色结果保持人设语气、不引入禁用词
 */
export async function polishPage(
  content: string,
  pageType: string,
  topic: string,
  instruction: PolishInstruction,
  brandId?: string
): Promise<PolishPageResponse> {
  const response = await http.post<PolishPageResponse>(
    '/outline/polish',
    {
      content,
      page_type: pageType,
      topic,
      instruction,
      // 不使用品牌人设时不携带 brand_id 键，保持向后兼容
      ...(brandId ? { brand_id: brandId } : {})
    },
    // 单页润色走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
