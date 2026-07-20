/**
 * 对标拆解本地历史（localStorage）
 *
 * 纯函数负责摘要、裁剪与损坏数据过滤，方便单测；
 * load/save 封装 localStorage 读写（node 环境下安全降级）。
 */
import type { BenchmarkAnalysis } from '../api/benchmark'

/** localStorage 存储键 */
export const BENCHMARK_HISTORY_KEY = 'redink_benchmark_history'

/** 历史条数上限 */
export const BENCHMARK_HISTORY_LIMIT = 20

/** 输入摘要最大字数 */
export const SUMMARY_MAX_CHARS = 50

/** 一条拆解历史记录 */
export interface BenchmarkHistoryEntry {
  /** 唯一 ID */
  id: string
  /** 输入摘要（内容前 50 字或链接） */
  summary: string
  /** 完整拆解结果 */
  analysis: BenchmarkAnalysis
  /** 仿写草稿（无则为空串） */
  draft: string
  /** 当时填写的「我的主题」 */
  myTopic: string
  /** 时间戳（毫秒） */
  createdAt: number
}

/** localStorage 的最小接口，便于测试注入 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/**
 * 把拆解输入压缩成摘要：合并空白后截取前 50 字
 */
export function buildSummary(input: string, maxChars: number = SUMMARY_MAX_CHARS): string {
  const collapsed = input.replace(/\s+/g, ' ').trim()
  if (collapsed.length <= maxChars) return collapsed
  return collapsed.slice(0, maxChars) + '…'
}

/**
 * 判断一条记录是否结构完整（用于丢弃损坏数据）
 */
export function isValidEntry(value: unknown): value is BenchmarkHistoryEntry {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  if (typeof entry.id !== 'string' || !entry.id) return false
  if (typeof entry.summary !== 'string') return false
  if (typeof entry.draft !== 'string') return false
  if (typeof entry.myTopic !== 'string') return false
  if (typeof entry.createdAt !== 'number' || !Number.isFinite(entry.createdAt)) return false

  const analysis = entry.analysis as Record<string, unknown> | null | undefined
  if (typeof analysis !== 'object' || analysis === null) return false
  const strFields = ['hook', 'opening', 'emotion', 'audience', 'reusable_template'] as const
  if (strFields.some(field => typeof analysis[field] !== 'string')) return false
  if (!Array.isArray(analysis.structure) || !Array.isArray(analysis.viral_elements)) return false

  return true
}

/**
 * 解析持久化 JSON：非法 JSON / 非数组返回空列表，损坏条目逐条丢弃
 */
export function parseHistoryJson(json: string | null): BenchmarkHistoryEntry[] {
  if (!json) return []

  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return []
  }

  if (!Array.isArray(parsed)) return []
  return parsed.filter(isValidEntry).slice(0, BENCHMARK_HISTORY_LIMIT)
}

/**
 * 头插一条记录并裁剪到上限（不修改入参）
 */
export function addEntry(
  list: BenchmarkHistoryEntry[],
  entry: BenchmarkHistoryEntry,
  limit: number = BENCHMARK_HISTORY_LIMIT
): BenchmarkHistoryEntry[] {
  return [entry, ...list].slice(0, limit)
}

/**
 * 构造一条新历史记录
 */
export function createEntry(params: {
  input: string
  analysis: BenchmarkAnalysis
  draft: string
  myTopic: string
  now?: number
}): BenchmarkHistoryEntry {
  const createdAt = params.now ?? Date.now()
  return {
    id: `bm_${createdAt}_${Math.random().toString(36).slice(2, 8)}`,
    summary: buildSummary(params.input),
    analysis: params.analysis,
    draft: params.draft,
    myTopic: params.myTopic,
    createdAt,
  }
}

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/**
 * 从 localStorage 读取历史（不可用/损坏时返回空列表）
 */
export function loadHistory(storage: StorageLike | null = defaultStorage()): BenchmarkHistoryEntry[] {
  if (!storage) return []
  try {
    return parseHistoryJson(storage.getItem(BENCHMARK_HISTORY_KEY))
  } catch {
    return []
  }
}

/**
 * 写入历史到 localStorage（配额溢出等异常静默忽略）
 */
export function saveHistory(
  list: BenchmarkHistoryEntry[],
  storage: StorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(BENCHMARK_HISTORY_KEY, JSON.stringify(list.slice(0, BENCHMARK_HISTORY_LIMIT)))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响主流程
  }
}
