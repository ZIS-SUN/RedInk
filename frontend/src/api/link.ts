import { LLM_TIMEOUT, http } from './client'
import type { Page } from './types'
import type { AppError } from '../utils/errors'

/** 链接/长文转大纲的请求参数：url 与 text 二选一，优先 url */
export interface LinkToOutlineParams {
  url?: string
  text?: string
  /** 品牌档案 ID（可选），提供时后端按品牌人设约束生成大纲（与主流程 /outline 一致） */
  brandId?: string
}

/** 链接/长文转大纲的响应，pages 结构与现有大纲流程完全一致 */
export interface LinkOutlineResponse {
  success: boolean
  topic?: string
  outline?: string
  pages?: Page[]
  error?: AppError | string
  error_message?: string
}

/**
 * 链接/长文 → 图文大纲
 * 后端会抓取网页正文（或直接使用传入的长文本），再调用 AI 提炼成多页大纲
 */
export async function linkToOutline(
  params: LinkToOutlineParams
): Promise<LinkOutlineResponse> {
  const body: Record<string, string> = {}
  if (params.url) body.url = params.url
  if (params.text) body.text = params.text
  // 不使用品牌人设时不携带 brand_id 键，保持向后兼容
  if (params.brandId) body.brand_id = params.brandId

  const response = await http.post<LinkOutlineResponse>(
    '/link/outline',
    body,
    // 抓取 + LLM 提炼，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
