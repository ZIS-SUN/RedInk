import {
  API_BASE_URL,
  LLM_TIMEOUT,
  getAuthHeaders,
  http,
  readErrorResponse,
  readSseResponse
} from './client'
import type {
  FinishEvent,
  Page,
  ProgressEvent,
  TaskState
} from './types'
import type { AppError } from '../utils/errors'

/** 参考图上传前压缩：最长边像素上限 */
const REFERENCE_IMAGE_MAX_DIMENSION = 1600
/** 参考图上传前压缩：JPEG 质量 */
const REFERENCE_IMAGE_QUALITY = 0.85

/**
 * 归一化调用方传入的 style_prompt：
 * 空字符串/未传入均视为「无风格」，不发送该字段。
 * （API 层不反向依赖 store，本次生成的风格由调用方从 generator store 显式取出传入）
 */
function normalizeStylePrompt(value?: string): string | undefined {
  return value || undefined
}

export function getImageUrl(taskId: string, filename: string, thumbnail: boolean = true): string {
  const thumbParam = thumbnail ? '?thumbnail=true' : '?thumbnail=false'
  return `${API_BASE_URL}/images/${taskId}/${filename}${thumbParam}`
}

/**
 * 查询后端任务状态（用于刷新后按 taskId 恢复，而不是重开新任务）
 * 任务不存在（如后端已重启）时返回 success: false
 */
export async function getTaskState(taskId: string): Promise<{
  success: boolean
  state?: TaskState
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get(`/task/${encodeURIComponent(taskId)}`)
    return response.data
  } catch {
    return { success: false }
  }
}

export async function regenerateImage(
  taskId: string,
  page: Page,
  useReference: boolean = true,
  context?: {
    fullOutline?: string
    userTopic?: string
    recordId?: string | null
    stylePrompt?: string
  }
): Promise<{ success: boolean; index: number; image_url?: string; error?: AppError | string; error_message?: string }> {
  const response = await http.post(
    '/regenerate',
    {
      task_id: taskId,
      page,
      use_reference: useReference,
      full_outline: context?.fullOutline,
      user_topic: context?.userTopic,
      record_id: context?.recordId || undefined,
      style_prompt: normalizeStylePrompt(context?.stylePrompt)
    },
    // 单张图片重绘走 LLM/绘图模型，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}

export async function retryFailedImages(
  taskId: string,
  pages: Page[],
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (event: ProgressEvent) => void,
  onFinish: (event: { success: boolean; total: number; completed: number; failed: number }) => void,
  onStreamError: (error: unknown) => void,
  recordId?: string | null,
  options?: { signal?: AbortSignal; stylePrompt?: string }
) {
  try {
    const response = await fetch(`${API_BASE_URL}/retry-failed`, {
      method: 'POST',
      // SSE 流式请求不走 axios 拦截器，需在此合并访问令牌请求头
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        task_id: taskId,
        pages,
        record_id: recordId || undefined,
        style_prompt: normalizeStylePrompt(options?.stylePrompt)
      }),
      signal: options?.signal
    })

    if (!response.ok) {
      throw await readErrorResponse(response, `请求失败：HTTP ${response.status}`)
    }

    await readSseResponse(response, {
      retry_start: (data) => onProgress({ index: -1, status: 'generating', message: data.message }),
      complete: onComplete,
      error: onError,
      retry_finish: onFinish
    }, { signal: options?.signal })
  } catch (error) {
    onStreamError(error)
  }
}

export async function generateImagesPost(
  pages: Page[],
  taskId: string | null,
  fullOutline: string,
  onProgress: (event: ProgressEvent) => void,
  onComplete: (event: ProgressEvent) => void,
  onError: (event: ProgressEvent) => void,
  onFinish: (event: FinishEvent) => void,
  onStreamError: (error: unknown) => void,
  userImages?: File[],
  userTopic?: string,
  recordId?: string | null,
  force: boolean = false,
  options?: { signal?: AbortSignal; stylePrompt?: string }
) {
  try {
    const userImagesBase64 = userImages && userImages.length > 0
      ? await Promise.all(userImages.map(compressImageToDataUrl))
      : []

    const response = await fetch(`${API_BASE_URL}/generate`, {
      method: 'POST',
      // SSE 流式请求不走 axios 拦截器，需在此合并访问令牌请求头
      headers: {
        'Content-Type': 'application/json',
        ...getAuthHeaders()
      },
      body: JSON.stringify({
        pages,
        task_id: taskId,
        full_outline: fullOutline,
        user_images: userImagesBase64.length > 0 ? userImagesBase64 : undefined,
        user_topic: userTopic || '',
        record_id: recordId || undefined,
        force,
        style_prompt: normalizeStylePrompt(options?.stylePrompt)
      }),
      signal: options?.signal
    })

    if (!response.ok) {
      throw await readErrorResponse(response, `请求失败：HTTP ${response.status}`)
    }

    await readSseResponse(response, {
      progress: onProgress,
      complete: onComplete,
      error: onError,
      finish: onFinish
    }, { signal: options?.signal })
  } catch (error) {
    onStreamError(error)
  }
}

/**
 * 参考图上传前先用 canvas 压缩再 base64 编码，
 * 避免多张原图 readAsDataURL 直接塞进 JSON body 导致请求体过大
 */
async function compressImageToDataUrl(file: File): Promise<string> {
  try {
    const bitmap = await createImageBitmap(file)
    try {
      const scale = Math.min(
        1,
        REFERENCE_IMAGE_MAX_DIMENSION / Math.max(bitmap.width, bitmap.height)
      )
      const width = Math.max(1, Math.round(bitmap.width * scale))
      const height = Math.max(1, Math.round(bitmap.height * scale))

      const canvas = document.createElement('canvas')
      canvas.width = width
      canvas.height = height
      const ctx = canvas.getContext('2d')
      if (!ctx) throw new Error('无法创建 canvas 上下文')

      ctx.drawImage(bitmap, 0, 0, width, height)
      return canvas.toDataURL('image/jpeg', REFERENCE_IMAGE_QUALITY)
    } finally {
      bitmap.close()
    }
  } catch {
    // 解码/压缩失败（如不支持的格式）时退回原图编码
    return readFileAsDataUrl(file)
  }
}

function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise<string>((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(reader.result as string)
    reader.onerror = reject
    reader.readAsDataURL(file)
  })
}
