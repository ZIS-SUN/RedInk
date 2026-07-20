import { getApiErrorPayload, http } from './client'
import type { AppError } from '../utils/errors'

/**
 * 剪藏收件箱 API（浏览器插件进料）
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 剪藏来源平台 */
export type ClipSource = 'xiaohongshu' | 'douyin' | 'other'

/** 剪藏互动数据（插件能取到哪项就有哪项） */
export interface ClipStats {
  /** 点赞数 */
  likes?: number
  /** 收藏数 */
  collects?: number
  /** 评论数 */
  comments?: number
}

/** 单条剪藏 */
export interface Clip {
  id: string
  /** 来源平台 */
  source: ClipSource
  /** 原始页面链接 */
  url: string
  /** 标题 */
  title: string
  /** 作者 */
  author: string
  /** 正文文本 */
  content: string
  /** 话题标签 */
  tags: string[]
  /** 互动数据；插件未采集到时为 null */
  stats: ClipStats | null
  created_at: string
}

export async function getClipList(): Promise<{
  success: boolean
  clips: Clip[]
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.get('/clips')
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      clips: [],
      ...getApiErrorPayload(error, '获取剪藏收件箱失败')
    }
  }
}

export async function deleteClip(clipId: string): Promise<{
  success: boolean
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete(`/clips/${clipId}`)
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '删除剪藏失败') }
  }
}

export async function clearClips(): Promise<{
  success: boolean
  removed?: number
  error?: AppError | string
  error_message?: string
}> {
  try {
    const response = await http.delete('/clips')
    return response.data
  } catch (error: unknown) {
    return { success: false, ...getApiErrorPayload(error, '清空剪藏收件箱失败') }
  }
}
