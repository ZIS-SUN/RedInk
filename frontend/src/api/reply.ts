import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 回复语气 */
export type ReplyTone = '热情' | '专业' | '幽默' | '温暖'

/** 单条评论及其神回复建议 */
export interface ReplyItem {
  /** 原评论文本 */
  comment: string
  /** 回复建议（2-3 条） */
  suggestions: string[]
}

export interface ReplyResponse {
  success: boolean
  replies?: ReplyItem[]
  /** 置顶引导评论，未要求生成时为空字符串 */
  pinned_comment?: string
  error?: AppError | string
  error_message?: string
}

export interface ReplyGenerateParams {
  /** 粉丝评论列表（每项一条） */
  comments: string[]
  /** 回复语气 */
  tone: ReplyTone
  /** 是否同时生成一条置顶引导评论 */
  includePinned?: boolean
  /** 品牌档案 ID（可选），提供时后端以博主人设口吻生成回复 */
  brandId?: string
}

export async function generateReplies(
  params: ReplyGenerateParams
): Promise<ReplyResponse> {
  const response = await http.post<ReplyResponse>(
    '/reply',
    {
      comments: params.comments,
      tone: params.tone,
      include_pinned: params.includePinned ?? false,
      ...(params.brandId ? { brand_id: params.brandId } : {})
    },
    // 神回复生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
