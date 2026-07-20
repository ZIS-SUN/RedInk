import { getApiErrorPayload, http, LLM_TIMEOUT } from './client'
import type { AppError } from '../utils/errors'
import type { AnalyticsRecord } from './analytics'

/**
 * 内容日历（发布计划）API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 发布平台 */
export type PlanPlatform = 'xiaohongshu' | 'douyin' | 'gongzhonghao' | 'bilibili' | 'shipinhao'

/** 计划状态 */
export type PlanStatus = 'idea' | 'in_progress' | 'ready' | 'published'

/** 内容计划条目 */
export interface PlanItem {
  id: string
  /** 计划标题 */
  title: string
  /** 发布平台 */
  platform: PlanPlatform
  /** 计划发布日期（YYYY-MM-DD） */
  publish_date: string
  /** 计划发布时间（HH:MM），空串表示未填写（旧条目可能缺失该字段） */
  publish_time?: string
  /** 状态 */
  status: PlanStatus
  /** 备注 */
  notes: string
  /** 关联的历史记录 ID，空串表示未关联（旧条目可能缺失该字段） */
  record_id?: string
  created_at: string
  updated_at: string
}

/** 新建/更新条目时的入参（id 与时间戳由后端管理） */
export type PlanItemInput = Partial<Omit<PlanItem, 'id' | 'created_at' | 'updated_at'>> & {
  title: string
  publish_date: string
}

/** 按月统计结果 */
export interface PlanStats {
  /** 统计月份（YYYY-MM） */
  month: string
  /** 该月计划总数 */
  total: number
  /** 全部计划总数 */
  all_total: number
  /** 该月各状态数量 */
  by_status: Record<PlanStatus, number>
  /** 该月各平台数量 */
  by_platform: Record<PlanPlatform, number>
}

/** 列表过滤参数（可组合） */
export interface PlanListFilters {
  /** 按月过滤（YYYY-MM） */
  month?: string
  platform?: PlanPlatform
  status?: PlanStatus
}

export async function getPlanList(filters: PlanListFilters = {}): Promise<{
  success: boolean
  plans: PlanItem[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const params: Record<string, string> = {}
    if (filters.month) params.month = filters.month
    if (filters.platform) params.platform = filters.platform
    if (filters.status) params.status = filters.status

    const response = await http.get('/plans', { params })
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      plans: [],
      ...getApiErrorPayload(error, '获取内容计划列表失败')
    }
  }
}

export async function createPlan(data: PlanItemInput): Promise<{
  success: boolean
  plan?: PlanItem
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/plans', data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '创建内容计划失败') }
  }
}

export async function updatePlan(
  planId: string,
  data: Partial<PlanItemInput>
): Promise<{
  success: boolean
  plan?: PlanItem
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.put(`/plans/${planId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新内容计划失败') }
  }
}

export async function deletePlan(planId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/plans/${planId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除内容计划失败') }
  }
}

/** 一键转录到数据复盘的请求参数（均可选，未提供的字段由后端从日历条目预填） */
export interface LogPlanPerformanceInput {
  title?: string
  /** 发布平台（自由文本中文名，如"小红书"） */
  platform?: string
  /** 发布日期（YYYY-MM-DD） */
  publish_date?: string
  /** 发布时间（HH:MM） */
  publish_time?: string
  /** 内容类型/标签 */
  content_type?: string
  views?: number
  likes?: number
  collects?: number
  comments?: number
  shares?: number
  followers_gained?: number
  notes?: string
}

/**
 * 把日历条目一键转录到数据复盘。
 * 同一条目重复转录时后端会更新已有关联记录而非新建（created 为 false）。
 */
export async function logPlanPerformance(
  planId: string,
  data: LogPlanPerformanceInput = {}
): Promise<{
  success: boolean
  record?: AnalyticsRecord
  /** 是否为新建记录（false 表示更新了已有关联记录） */
  created?: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post(`/plans/${planId}/log-performance`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '转录到数据复盘失败') }
  }
}

/** AI 一周排期的请求参数 */
export interface GenerateWeekPlanInput {
  /** 领域/赛道（必填） */
  niche: string
  /** 发布平台（可选，默认 xiaohongshu） */
  platform?: PlanPlatform
  /** 周一日期 YYYY-MM-DD（可选，默认下周一） */
  start_date?: string
  /** 每周条数 1-7（可选，默认 3） */
  frequency?: number
  /** 是否结合账号数据（可选，默认 false） */
  use_account_data?: boolean
}

/** AI 一周排期预览条目（未落盘，确认后逐条调 createPlan） */
export interface WeekPlanPreviewItem {
  title: string
  platform: PlanPlatform
  publish_date: string
  publish_time: string
  notes: string
  status: PlanStatus
}

export async function generateWeekPlan(input: GenerateWeekPlanInput): Promise<{
  success: boolean
  plans?: WeekPlanPreviewItem[]
  account_context_used?: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    // LLM 生成耗时较长，使用 LLM 专用超时
    const response = await http.post('/plans/generate-week', input, { timeout: LLM_TIMEOUT })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, 'AI 一周排期生成失败') }
  }
}

export async function getPlanStats(month?: string): Promise<{
  success: boolean
  stats?: PlanStats
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/plans/stats', {
      params: month ? { month } : {}
    })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '获取计划统计失败') }
  }
}
