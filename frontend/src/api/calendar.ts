import { getApiErrorPayload, http } from './client'
import type { AppError } from '../utils/errors'

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
  /** 状态 */
  status: PlanStatus
  /** 备注 */
  notes: string
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
