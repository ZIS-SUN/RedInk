import { getApiErrorPayload, http } from './client'
import type { AppError } from '../utils/errors'

/**
 * 热点节点（营销日历图层）API
 * 纯静态数据接口，不依赖 AI 模型配置。
 * 约定：本模块的函数不抛异常，统一返回 { success: false, error, error_message }，
 * 错误归一化由统一 axios 实例的响应拦截器 + getApiErrorPayload 完成。
 */

/** 节点类型：节日 / 电商大促 / 周期性季节节点 */
export type HotspotType = 'festival' | 'ecommerce' | 'season'

/** 单个营销热点节点 */
export interface HotspotNode {
  /** 稳定标识（日期 + 名称） */
  id: string
  /** 节点名称，如"春节"、"618" */
  name: string
  /** 公历日期（YYYY-MM-DD） */
  date: string
  /** 节点类型 */
  type: HotspotType
  /** 建议提前备稿天数（3-14） */
  prep_days: number
  /** 平台侧重提示 */
  platform_hint: string
  /** 适配赛道提示 */
  niche_hint: string
}

/** 查询区间（均可选：start 缺省为今天，end 缺省为 start + 60 天） */
export interface HotspotRange {
  start?: string
  end?: string
}

export async function getHotspots(range: HotspotRange = {}): Promise<{
  success: boolean
  hotspots: HotspotNode[]
  /** 实际生效的查询区间 */
  start?: string
  end?: string
  error?: AppError | string
  error_message?: string
}> {
  try {
    const params: Record<string, string> = {}
    if (range.start) params.start = range.start
    if (range.end) params.end = range.end

    const response = await http.get('/hotspots', { params })
    return response.data
  } catch (error: unknown) {
    return {
      success: false,
      hotspots: [],
      ...getApiErrorPayload(error, '获取营销节点失败')
    }
  }
}
