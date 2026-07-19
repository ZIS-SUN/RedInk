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

/**
 * 拆解对标/爆款内容，可选按同样套路为自己的主题生成原创仿写草稿
 *
 * @param content 对标内容（标题+正文）
 * @param myTopic 用户自己的主题（可选），提供时返回仿写草稿
 */
export async function analyzeBenchmark(
  content: string,
  myTopic?: string
): Promise<BenchmarkResponse> {
  const response = await http.post<BenchmarkResponse>(
    '/benchmark',
    // 不做仿写时不携带 my_topic 键
    myTopic ? { content, my_topic: myTopic } : { content },
    // 拆解 + 仿写走 LLM，耗时较长
    { timeout: LLM_TIMEOUT }
  )
  return response.data
}
