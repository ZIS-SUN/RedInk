import { LLM_TIMEOUT, http } from './client'
import type { AppError } from '../utils/errors'

/** 对标内容拆解结果 */
export interface BenchmarkAnalysis {
  /** 钩子类型及用法说明 */
  hook: string
  /** 开头如何抓人 */
  opening: string
  /** 内容结构（按顺序逐段拆解） */
  structure: string[]
  /** 情绪价值及调动手法 */
  emotion: string
  /** 目标受众画像 */
  audience: string
  /** 爆点要素列表 */
  viral_elements: string[]
  /** 可复用的套路模板（槽位用【】标出） */
  reusable_template: string
}

/** POST /benchmark 响应 */
export interface BenchmarkResponse {
  success: boolean
  analysis?: BenchmarkAnalysis
  /** 仿写草稿：未提供 my_topic 时为空字符串 */
  draft?: string
  error?: AppError | string
  error_message?: string
}

/** 拆解请求参数：content 与 url 至少提供一个，优先 content */
export interface AnalyzeBenchmarkParams {
  /** 对标内容（标题+正文） */
  content?: string
  /** 对标内容的网页链接（无 content 时，后端先抓取正文再分析） */
  url?: string
  /** 用户自己的主题（可选），提供时返回仿写草稿 */
  myTopic?: string
  /** 品牌档案 ID（可选），提供时后端按品牌人设约束生成仿写草稿 */
  brandId?: string
}

/**
 * 拆解对标/爆款内容，可选按同样套路为自己的主题生成原创仿写草稿
 */
export async function analyzeBenchmark(
  params: AnalyzeBenchmarkParams
): Promise<BenchmarkResponse> {
  const body: Record<string, string> = {}
  if (params.content) body.content = params.content
  if (params.url) body.url = params.url
  // 不做仿写时不携带 my_topic 键
  if (params.myTopic) body.my_topic = params.myTopic
  // 不使用品牌人设时不携带 brand_id 键，保持向后兼容
  if (params.brandId) body.brand_id = params.brandId

  const response = await http.post<BenchmarkResponse>(
    '/benchmark',
    body,
    // 抓取 + 拆解 + 仿写走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
