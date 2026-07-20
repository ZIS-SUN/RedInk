import { getApiErrorPayload, http } from './client'
import type { AppError } from '../utils/errors'

/**
 * 我的选题库 API
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 选题来源 */
export type IdeaSource = 'manual' | 'topic' | 'insight' | 'hotspot'

/** 选题状态（想法 / 待做 / 已做 / 已爆） */
export type IdeaStatus = 'idea' | 'todo' | 'done' | 'viral'

/** 选题库条目 */
export interface IdeaItem {
  id: string
  /** 选题标题 */
  title: string
  /** 切入角度 */
  angle: string
  /** 建议标签（不含 # 号） */
  tags: string[]
  /** 来源 */
  source: IdeaSource
  /** 状态 */
  status: IdeaStatus
  /** 赛道/领域 */
  niche: string
  created_at: string
  updated_at: string
}

/** 新建条目入参（id 与时间戳由后端管理；title 必填，其余可选） */
export interface IdeaItemInput {
  title: string
  angle?: string
  tags?: string[]
  source?: IdeaSource
  status?: IdeaStatus
  niche?: string
}

/** 列表过滤参数（可组合） */
export interface IdeaListFilters {
  status?: IdeaStatus
  source?: IdeaSource
}

export async function listIdeas(filters: IdeaListFilters = {}): Promise<{
  success: boolean
  ideas: IdeaItem[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const params: Record<string, string> = {}
    if (filters.status) params.status = filters.status
    if (filters.source) params.source = filters.source

    const response = await http.get('/ideas', { params })
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      ideas: [],
      ...getApiErrorPayload(error, '获取选题库列表失败')
    }
  }
}

export async function createIdea(data: IdeaItemInput): Promise<{
  success: boolean
  idea?: IdeaItem
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.post('/ideas', data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '存入选题库失败') }
  }
}

export async function updateIdea(
  ideaId: string,
  data: Partial<IdeaItemInput>
): Promise<{
  success: boolean
  idea?: IdeaItem
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.put(`/ideas/${ideaId}`, data)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '更新选题失败') }
  }
}

export async function deleteIdea(ideaId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/ideas/${ideaId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除选题失败') }
  }
}
