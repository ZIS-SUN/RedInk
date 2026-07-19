import { LLM_TIMEOUT, http } from './client'
import type { OutlineResponse } from './types'

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
