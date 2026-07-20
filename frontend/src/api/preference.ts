/**
 * 创作偏好画像 API：从历史评分与编辑留痕聚合出的用户偏好
 */
import { http } from './client'
import type { AppError } from '../utils/errors'

/** 编辑习惯信号 */
export interface EditingSignal {
  /** 统计到的编辑留痕条数 */
  edit_count: number
  /** 平均长度变化比例（负数 = 改短，正数 = 改长） */
  avg_change_ratio: number
  /** 归纳结论：shorten 嫌啰嗦 / expand 嫌单薄 / neutral 幅度不明显；无编辑为 null */
  tendency: 'shorten' | 'expand' | 'neutral' | null
}

/** 创作偏好画像 */
export interface PreferenceProfile {
  /** 已评分样本不足（此时不输出结论字段） */
  insufficient: boolean
  /** 已评分作品数 */
  sample_count: number
  /** 置信下限（展示「当前样本 X/3」用） */
  min_samples: number
  /** 高分（rating >= 4）作品数 */
  liked_count: number
  /** 高分作品主题列表（去重） */
  liked_topics: string[]
  /** 高分作品最常见页数（无数据为 null） */
  preferred_page_count: number | null
  /** 高分作品页数分布 { 页数: 次数 } */
  page_count_distribution: Record<string, number>
  /** 编辑习惯信号 */
  editing_signal: EditingSignal
}

/** GET /preference/profile 响应 */
export interface PreferenceProfileResult {
  success: boolean
  profile?: PreferenceProfile
  error?: AppError | string
  error_message?: string
}

/** 获取创作偏好画像 */
export async function getPreferenceProfile(): Promise<PreferenceProfileResult> {
  const response = await http.get<PreferenceProfileResult>('/preference/profile')
  return response.data
}
