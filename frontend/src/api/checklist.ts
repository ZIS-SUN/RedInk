import { http } from './client'
import type { AppError } from '../utils/errors'

/** 支持的发布平台标识 */
export type ChecklistPlatform = 'xiaohongshu' | 'douyin' | 'weixin' | 'bilibili' | 'weibo'

/** 检查项状态：pass-通过 warn-建议关注 fail-不合规 */
export type ChecklistStatus = 'pass' | 'warn' | 'fail'

/** 单条检查项 */
export interface ChecklistItem {
  /** 检查项标识：title_length / body_length / tags_count / image_count / banned_words / sensitive_words */
  id: string
  /** 检查项名称（如"标题长度"） */
  label: string
  /** 检查结果状态 */
  status: ChecklistStatus
  /** 结果说明文字 */
  detail: string
}

/** 各状态检查项计数 */
export interface ChecklistSummary {
  pass: number
  warn: number
  fail: number
}

/** POST /checklist 响应 */
export interface ChecklistResponse {
  success: boolean
  platform?: ChecklistPlatform
  items?: ChecklistItem[]
  summary?: ChecklistSummary
  error?: AppError | string
  error_message?: string
}

/** 发布前检查请求参数 */
export interface RunChecklistParams {
  /** 目标平台 */
  platform: ChecklistPlatform
  /** 标题（可选） */
  title?: string
  /** 正文文案（可选） */
  body?: string
  /** 标签列表（可选） */
  tags?: string[]
  /** 已生成图片数 */
  imageCount: number
  /** 禁用词列表（可选；不传时服务端自动读取当前启用品牌档案的禁用词） */
  bannedWords?: string[]
}

/**
 * 发布前检查：按目标平台的发布规范（标题字数/标签数量/禁用词/图片数等）
 * 做纯规则合规校验，不调用 LLM，秒回结果
 */
export async function runChecklist(params: RunChecklistParams): Promise<ChecklistResponse> {
  const body: Record<string, unknown> = {
    platform: params.platform,
    image_count: params.imageCount
  }
  if (params.title) body.title = params.title
  if (params.body) body.body = params.body
  if (params.tags && params.tags.length > 0) body.tags = params.tags
  if (params.bannedWords) body.banned_words = params.bannedWords

  const response = await http.post<ChecklistResponse>('/checklist', body)
  return response.data
}
