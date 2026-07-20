import { getApiErrorPayload, http, LLM_TIMEOUT } from './client'
import type { AppError } from '../utils/errors'

/**
 * 数据复盘（表现分析）API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 行业基准红黄绿评级（B10）：red=偏低 / yellow=待提升 / green=达标 */
export type BenchmarkRating = 'red' | 'yellow' | 'green'

/** 单个指标的值与评级（value/rating 为 null 表示无曝光数据无法评级） */
export interface AnalyticsMetricScore {
  value: number | null
  rating: BenchmarkRating | null
}

/** 汇总层指标评级（附带基准阈值与说明，供指标卡 hover 展示） */
export interface AnalyticsMetricRating extends AnalyticsMetricScore {
  label: string
  /** 低于该值为红 */
  red_below: number
  /** 达到该值为绿 */
  green_at: number
  note: string
}

/** 基准表元信息（来源标注「公开行业经验值，仅供参考」） */
export interface AnalyticsBenchmarksMeta {
  version: string
  updated_at: string
  source: string
}

/** 已发布内容的表现记录 */
export interface AnalyticsRecord {
  id: string
  /** 内容标题 */
  title: string
  /** 发布平台（如"小红书"/"抖音"） */
  platform: string
  /** 发布日期，YYYY-MM-DD */
  publish_date: string
  /** 发布时间，HH:MM，空串表示未填写（旧记录可能缺失该字段） */
  publish_time?: string
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
  /** 关联的历史作品 ID，空串表示未关联（旧记录可能缺失该字段） */
  record_id?: string
  /** 关联的内容日历条目 ID，空串表示未关联（旧记录可能缺失该字段） */
  calendar_plan_id?: string
  created_at: string
  updated_at: string
  /**
   * 各指标的值与红黄绿评级（B10 新增的响应计算字段，旧后端可能缺失）
   * 键：engagement_rate / like_rate / collect_rate / comment_rate
   */
  metrics?: Record<string, AnalyticsMetricScore>
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
  /** 互动率的红黄绿评级（B10 新增，无曝光数据时为 null；旧后端可能缺失） */
  engagement_rating?: BenchmarkRating | null
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

/** 发布时段汇总（只统计填写了发布时间的记录） */
export interface AnalyticsTimeSlot {
  /** 时段名称，如"晚间 18-22" */
  name: string
  count: number
  /** 该时段平均互动率（百分比数值） */
  avg_engagement: number
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
  /** 发布时段汇总（新增字段，旧后端可能缺失） */
  time_slots?: AnalyticsTimeSlot[]
  /** 各指标的汇总评级（B10 新增，旧后端可能缺失） */
  metric_ratings?: Record<string, AnalyticsMetricRating>
  /** 行业基准表元信息（B10 新增，旧后端可能缺失） */
  benchmarks_meta?: AnalyticsBenchmarksMeta
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

/** 批量创建的单行失败信息 */
export interface AnalyticsBatchFailure {
  /** 提交数组中的行下标（0 起） */
  index: number
  error: string
}

export async function batchCreateAnalyticsRecords(records: AnalyticsRecordInput[]): Promise<{
  success: boolean
  created?: number
  failed?: AnalyticsBatchFailure[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/analytics/records/batch', { records })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '批量导入表现记录失败') }
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

/** 截图 OCR 识别出的一行数据（识别不了的字段为 null，由用户在预览表格中补全） */
export interface AnalyticsOcrRow {
  title: string | null
  /** YYYY-MM-DD */
  publish_date: string | null
  views: number | null
  likes: number | null
  collects: number | null
  comments: number | null
  shares: number | null
  followers_gained: number | null
}

/**
 * 截图 OCR 智能回填：上传 1-3 张创作者后台数据截图（base64 / data URL），
 * 由后端调用当前激活的文本模型做多模态识别，返回结构化行数组。
 * 只做识别不入库——确认后走 batchCreateAnalyticsRecords 批量入库。
 */
export async function ocrImportAnalyticsRecords(images: string[]): Promise<{
  success: boolean
  rows?: AnalyticsOcrRow[]
  count?: number
  model?: string
  error?: AppError | string
  error_message?: string
}> {
  try {
    // 多模态识别耗时较长（约 10-30 秒），使用 LLM 专用超时
    const response = await http.post('/analytics/ocr-import', { images }, { timeout: LLM_TIMEOUT })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '截图识别失败') }
  }
}
