import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 单条 AI 选题灵感 */
export interface TopicIdea {
  /** 选题标题，可直接用于创作 */
  title: string
  /** 切入角度：为什么这个选题可能火 */
  angle: string
  /** 适合的内容形式，如：图文 / 口播 / 清单 / 教程 */
  format: string
  /** 预估热度 0-100（AI 主观预估，非实时数据） */
  heat: number
  /** 关联话题标签（不含 # 号） */
  tags: string[]
}

export interface TopicResponse {
  success: boolean
  topics?: TopicIdea[]
  error?: AppError | string
  error_message?: string
}

export interface GenerateTopicsParams {
  /** 领域/赛道，如：健身减脂、职场干货、亲子育儿 */
  niche: string
  /** 目标平台，如：小红书、抖音 */
  platform: string
}

export async function generateTopics(
  params: GenerateTopicsParams
): Promise<TopicResponse> {
  const response = await http.post<TopicResponse>(
    '/topic',
    params,
    // 选题灵感生成走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
