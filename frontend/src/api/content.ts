import { LLM_TIMEOUT, http } from './client'
import type { ContentResponse } from './types'

export async function generateContent(
  topic: string,
  outline: string,
  brandId?: string
): Promise<ContentResponse> {
  const response = await http.post<ContentResponse>(
    '/content',
    // 不使用品牌人设时不携带 brand_id 键，保持向后兼容
    brandId ? { topic, outline, brand_id: brandId } : { topic, outline },
    // 标题/文案/标签生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
