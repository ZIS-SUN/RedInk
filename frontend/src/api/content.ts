import { LLM_TIMEOUT, http } from './client'
import type { ContentResponse } from './types'

export async function generateContent(
  topic: string,
  outline: string,
  brandId?: string,
  seoKeywords?: string[]
): Promise<ContentResponse> {
  // 不使用品牌人设/搜索词时不携带对应键，保持向后兼容
  const payload: Record<string, unknown> = { topic, outline }
  if (brandId) {
    payload.brand_id = brandId
  }
  if (seoKeywords && seoKeywords.length > 0) {
    payload.seo_keywords = seoKeywords
  }

  const response = await http.post<ContentResponse>(
    '/content',
    payload,
    // 标题/文案/标签生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
