import { LLM_TIMEOUT, http } from './client'
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
 * 单页 AI 润色：对大纲中某一页的文案按指令重写
 */
export async function polishPage(
  content: string,
  pageType: string,
  topic: string,
  instruction: PolishInstruction
): Promise<PolishPageResponse> {
  const response = await http.post<PolishPageResponse>(
    '/outline/polish',
    { content, page_type: pageType, topic, instruction },
    // 单页润色走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
