import {
  getApiErrorPayload,
  http
} from './client'
import type {
  HistoryDetail,
  HistoryRecord,
  Page,
  UpdateHistoryParams
} from './types'
import type { AppError } from '../utils/errors'

/**
 * 历史记录 API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

export async function createHistory(
  topic: string,
  outline: { raw: string; pages: Page[] },
  taskId?: string
): Promise<{ success: boolean; record_id?: string; error?: AppError | string; error_message?: string }> {
  try {
    const response = await http.post('/history', {
      topic,
      outline,
      task_id: taskId
    })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '创建历史记录失败') }
  }
}

export async function getHistoryList(
  page: number = 1,
  pageSize: number = 20,
  status?: string
): Promise<{
  success: boolean
  records: HistoryRecord[]
  total: number
  page: number
  page_size: number
  total_pages: number
  error?: AppError | string
  error_message?: string
}> {
  try {
    const params: Record<string, string | number> = { page, page_size: pageSize }
    if (status) params.status = status

    const response = await http.get('/history', { params })
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      records: [],
      total: 0,
      page: 1,
      page_size: pageSize,
      total_pages: 0,
      ...getApiErrorPayload(error, '获取历史记录列表失败')
    }
  }
}

export async function getHistory(recordId: string): Promise<{
  success: boolean
  record?: HistoryDetail
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get(`/history/${recordId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '获取历史记录详情失败') }
  }
}

export async function updateHistory(
  recordId: string,
  data: UpdateHistoryParams
): Promise<{ success: boolean; error?: AppError | string; error_message?: string }> {
  try {
    const response = await http.put(`/history/${recordId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新历史记录失败') }
  }
}

export async function checkHistoryExists(recordId: string): Promise<boolean> {
  try {
    const response = await http.get(`/history/${recordId}/exists`, {
      timeout: 5000
    })
    return response.data.exists === true
  } catch {
    return false
  }
}

export async function deleteHistory(recordId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/history/${recordId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除历史记录失败') }
  }
}

export async function searchHistory(keyword: string): Promise<{
  success: boolean
  records: HistoryRecord[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/history/search', {
      params: { keyword }
    })
    return response.data
  } catch (error: unknown) {
    return { success: false, records: [], ...getApiErrorPayload(error, '搜索历史记录失败') }
  }
}

export async function getHistoryStats(): Promise<{
  success: boolean
  total: number
  by_status: Record<string, number>
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/history/stats')
    return response.data
  } catch (error: unknown) {
    return { success: false, total: 0, by_status: {}, ...getApiErrorPayload(error, '获取统计信息失败') }
  }
}

export async function scanAllTasks(): Promise<{
  success: boolean
  total_tasks?: number
  synced?: number
  failed?: number
  orphan_tasks?: string[]
  results?: unknown[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    // 全量扫描任务目录可能较慢
    const response = await http.post('/history/scan-all', undefined, { timeout: 60_000 })
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '同步历史记录失败') }
  }
}
