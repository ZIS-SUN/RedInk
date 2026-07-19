import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 支持的平台代号 */
export type RewritePlatform = 'xiaohongshu' | 'douyin' | 'wechat' | 'bilibili' | 'weibo'

/** 单个平台的改写结果 */
export interface RewriteResult {
  platform: RewritePlatform | string
  title: string
  content: string
  tags: string[]
}

export interface RewriteResponse {
  success: boolean
  results?: RewriteResult[]
  error?: AppError | string
  error_message?: string
}

/**
 * 多平台文案改写
 *
 * @param content 原始文案或主题
 * @param sourcePlatform 源平台代号，空字符串表示通用文案
 * @param targetPlatforms 目标平台代号列表（至少一个）
 * @param brandId 品牌档案 ID（可选），提供时后端按品牌人设约束生成
 */
export async function rewriteCopy(
  content: string,
  sourcePlatform: RewritePlatform | '',
  targetPlatforms: RewritePlatform[],
  brandId?: string
): Promise<RewriteResponse> {
  const response = await http.post<RewriteResponse>(
    '/rewrite',
    {
      content,
      source_platform: sourcePlatform,
      target_platforms: targetPlatforms,
      ...(brandId ? { brand_id: brandId } : {})
    },
    // 改写走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
