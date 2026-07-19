import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 单个封面方向 */
export interface CoverDirection {
  /** 封面主标题文案 */
  title: string
  /** 副标题/点缀词 */
  subtitle: string
  /** 视觉概念描述（构图/配色/元素） */
  visual_concept: string
  /** 风格倾向 */
  style: string
  /** 预估点击力评分 0-100 */
  score: number
  /** 为什么这个方向可能更吸引点击 */
  reason: string
}

/** 封面方向生成接口响应 */
export interface CoverResponse {
  success: boolean
  directions?: CoverDirection[]
  error?: AppError | string
  error_message?: string
}

/**
 * 生成封面 A/B 方向（3-4 个差异化方向，用于并排对比）
 * @param topic 主题（必填）
 * @param content 补充内容/背景（可选）
 */
export async function generateCoverDirections(
  topic: string,
  content?: string
): Promise<CoverResponse> {
  const response = await http.post<CoverResponse>(
    '/cover',
    content ? { topic, content } : { topic },
    // 封面方向生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
