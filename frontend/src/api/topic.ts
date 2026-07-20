import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 单条 AI 选题灵感 */
export interface TopicIdea {
  /** 选题标题，可直接用于创作 */
  title: string
  /** 切入角度：为什么这个选题可能火（蹭热点模式下为蹭点角度） */
  angle: string
  /** 适合的内容形式，如：图文 / 口播 / 清单 / 教程 */
  format: string
  /** 预估热度 0-100（AI 主观预估，非实时数据） */
  heat: number
  /** 关联话题标签（不含 # 号） */
  tags: string[]
  /** 蹭热点模式：对应的热点原词（常规模式无此字段） */
  hot_topic?: string
  /** 蹭热点模式：建议发布窗口，如「48 小时内」 */
  publish_window?: string
  /** 蹭热点模式：与账号赛道的关联度评估（高/中/低 + 理由） */
  relevance?: string
}

export interface TopicResponse {
  success: boolean
  topics?: TopicIdea[]
  /** 本次生成是否实际结合了账号数据（数据复盘工具录入的记录） */
  account_context_used?: boolean
  error?: AppError | string
  error_message?: string
}

export interface GenerateTopicsParams {
  /** 领域/赛道，如：健身减脂、职场干货、亲子育儿 */
  niche: string
  /** 目标平台，如：小红书、抖音 */
  platform: string
  /** 是否结合账号数据（需先在数据复盘工具录入笔记数据），默认 false */
  use_account_data?: boolean
  /**
   * 手动粘贴的热榜词/热点标题（每行一条拆成数组）。
   * 提供时进入「蹭热点」模式：对每个热点产出蹭点角度、建议发布窗口与关联度评估
   */
  hot_topics?: string[]
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
