import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 单条选题（结构对齐选题灵感服务的 TopicIdea schema） */
export interface InsightTopicIdea {
  /** 选题标题，可直接用于创作 */
  title: string
  /** 切入角度：为什么这个选题能接住痛点、可能火 */
  angle: string
  /** 适合的内容形式，如：图文 / 口播 / 清单 / 教程 */
  format: string
  /** 预估热度 0-100（AI 主观预估，非实时数据） */
  heat: number
  /** 关联话题标签（不含 # 号） */
  tags: string[]
}

/** 从评论中聚类出的单个痛点主题 */
export interface PainPoint {
  /** 痛点主题 */
  theme: string
  /** 痛点说明：评论背后的真实诉求与情绪 */
  summary: string
  /** 出现频次估计（相关评论条数，AI 估计值） */
  frequency: number
  /** 代表性原评论摘录 */
  evidence: string[]
  /** 针对该痛点的选题（2-3 条） */
  topics: InsightTopicIdea[]
}

export interface InsightResponse {
  success: boolean
  pain_points?: PainPoint[]
  /** 实际参与分析的评论条数 */
  comment_count?: number
  error?: AppError | string
  error_message?: string
}

export interface MineInsightsParams {
  /** 粉丝评论列表（每项一条） */
  comments: string[]
  /** 我的赛道/领域（可选），帮助 AI 聚焦 */
  niche?: string
}

export async function mineInsights(
  params: MineInsightsParams
): Promise<InsightResponse> {
  const response = await http.post<InsightResponse>(
    '/insight',
    {
      comments: params.comments,
      ...(params.niche?.trim() ? { niche: params.niche.trim() } : {})
    },
    // 评论洞察挖掘走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
