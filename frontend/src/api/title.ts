import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 单个爆款候选标题 */
export interface TitleCandidate {
  /** 标题文本 */
  text: string
  /** 吸引力评分 0-100 */
  score: number
  /** 命中的爆款要素标签，如：数字 / 悬念 / 身份认同 / 紧迫感 */
  elements: string[]
  /** 命中的品牌禁用词（仅在使用了设置禁用词的品牌人设时返回） */
  banned_word_hits?: string[]
}

export interface TitleResponse {
  success: boolean
  titles?: TitleCandidate[]
  error?: AppError | string
  error_message?: string
}

export interface GenerateTitlesParams {
  /** 主题或文案草稿 */
  topic: string
  /** 目标平台，如：小红书、抖音 */
  platform: string
  /** 风格倾向，如：悬念型、数字型 */
  style: string
  /** 品牌档案 ID（可选），提供时后端按品牌人设约束生成 */
  brandId?: string
}

export async function generateTitles(
  params: GenerateTitlesParams
): Promise<TitleResponse> {
  const { brandId, ...rest } = params
  const response = await http.post<TitleResponse>(
    '/title',
    {
      ...rest,
      ...(brandId ? { brand_id: brandId } : {})
    },
    // 爆款标题生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
