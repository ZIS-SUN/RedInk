import { LLM_TIMEOUT, http } from './client'
import type { Page } from './types'
import type { AppError } from '../utils/errors'

/** 单个评分维度 */
export interface ReviewDimension {
  /** 维度名：封面钩子 | 标题吸引力 | 内容结构 | 情绪价值 | 行动引导 */
  name: string
  /** 0-100 分 */
  score: number
  /** 简短点评 */
  comment: string
}

/** 单条修改建议 */
export interface ReviewSuggestion {
  /** 建议对象：page-某页文案 title-标题 copywriting-发布文案 tags-标签 */
  target: 'page' | 'title' | 'copywriting' | 'tags'
  /** target 为 page 时对应的页码（从 0 开始），其他情况为 null */
  page_index: number | null
  /** 问题描述 */
  issue: string
  /** 具体修改建议 */
  suggestion: string
  /** 可直接使用的改写文本（没有则为空字符串） */
  rewrite: string
}

/** 体检报告 */
export interface ReviewReport {
  /** 综合分 0-100 */
  overall_score: number
  /** 一句话总评 */
  verdict: string
  /** 五个维度的评分与点评 */
  dimensions: ReviewDimension[]
  /** 最多 5 条修改建议 */
  suggestions: ReviewSuggestion[]
}

/** POST /review 响应 */
export interface ReviewResponse {
  success: boolean
  review?: ReviewReport
  error?: AppError | string
  error_message?: string
}

/** 体检请求参数 */
export interface ReviewWorkParams {
  /** 创作主题 */
  topic: string
  /** 全部页面（含页码/类型/文案） */
  pages: Page[]
  /** 候选标题列表（可选） */
  titles?: string[]
  /** 发布文案（可选） */
  copywriting?: string
  /** 标签列表（可选） */
  tags?: string[]
}

/**
 * 爆款体检：AI 从封面钩子/标题吸引力/内容结构/情绪价值/行动引导
 * 五个维度给成品打分，并给出可执行的修改建议
 */
export async function reviewWork(params: ReviewWorkParams): Promise<ReviewResponse> {
  const body: Record<string, unknown> = {
    topic: params.topic,
    pages: params.pages
  }
  if (params.titles && params.titles.length > 0) body.titles = params.titles
  if (params.copywriting) body.copywriting = params.copywriting
  if (params.tags && params.tags.length > 0) body.tags = params.tags

  const response = await http.post<ReviewResponse>(
    '/review',
    body,
    // 审稿走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
