import { getApiErrorPayload, http, LLM_TIMEOUT } from './client'
import type { AppError } from '../utils/errors'

/**
 * 数据复盘（表现分析）API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 已发布内容的表现记录 */
export interface AnalyticsRecord {
  id: string
  /** 内容标题 */
  title: string
  /** 发布平台（如"小红书"/"抖音"） */
  platform: string
  /** 发布日期，YYYY-MM-DD */
  publish_date: string
  /** 内容类型/标签（如"干货教程"/"好物种草"） */
  content_type: string
  /** 曝光/播放数 */
  views: number
  /** 点赞数 */
  likes: number
  /** 收藏数 */
  collects: number
  /** 评论数 */
  comments: number
  /** 转发数 */
  shares: number
  /** 涨粉数 */
  followers_gained: number
  /** 备注 */
  notes: string
  created_at: string
  updated_at: string
}

/** 新建/更新记录时的入参（id 与时间戳由后端管理） */
export type AnalyticsRecordInput = Partial<
  Omit<AnalyticsRecord, 'id' | 'created_at' | 'updated_at'>
> & {
  title: string
  platform: string
}

/** 分组汇总（按平台 / 按内容类型） */
export interface AnalyticsGroupSummary {
  name: string
  count: number
  views: number
  likes: number
  collects: number
  comments: number
  shares: number
  followers_gained: number
  /** 互动率（百分比数值，如 5.21 表示 5.21%） */
  engagement_rate: number
}

/** 按月趋势点 */
export interface AnalyticsTrendPoint {
  /** YYYY-MM */
  month: string
  count: number
  views: number
  engagements: number
  followers_gained: number
}

/** 统计概览 */
export interface AnalyticsStats {
  total_records: number
  total_views: number
  total_likes: number
  total_collects: number
  total_comments: number
  total_shares: number
  total_followers_gained: number
  /** 平均互动率（百分比数值） */
  avg_engagement_rate: number
  platforms: AnalyticsGroupSummary[]
  content_types: AnalyticsGroupSummary[]
  trend: AnalyticsTrendPoint[]
}

/** AI 复盘洞察结果 */
export interface AnalyticsInsight {
  /** 整体表现总结 */
  summary: string
  /** 复盘洞察（哪类内容/标题/平台表现更好） */
  highlights: string[]
  /** 下一步建议 */
  suggestions: string[]
}

export async function getAnalyticsRecords(): Promise<{
  success: boolean
  records: AnalyticsRecord[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/analytics/records')
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      records: [],
      ...getApiErrorPayload(error, '获取表现记录失败')
    }
  }
}

export async function createAnalyticsRecord(data: AnalyticsRecordInput): Promise<{
  success: boolean
  record?: AnalyticsRecord
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/analytics/records', data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '创建表现记录失败') }
  }
}

export async function updateAnalyticsRecord(
  recordId: string,
  data: Partial<AnalyticsRecordInput>
): Promise<{
  success: boolean
  record?: AnalyticsRecord
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.put(`/analytics/records/${recordId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新表现记录失败') }
  }
}

export async function deleteAnalyticsRecord(recordId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/analytics/records/${recordId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除表现记录失败') }
  }
}

export async function getAnalyticsStats(): Promise<{
  success: boolean
  stats?: AnalyticsStats
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/analytics/stats')
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '获取统计概览失败') }
  }
}

export async function generateAnalyticsInsight(): Promise<{
  success: boolean
  insight?: AnalyticsInsight
  data_summary?: string
  error?: AppError | string
  error_message?: string
}> {
  try {
    // LLM 生成耗时较长，使用 LLM 专用超时
    const response = await http.post('/analytics/insight', {}, { timeout: LLM_TIMEOUT })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, 'AI 复盘洞察失败') }
  }
}
