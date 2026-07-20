/**
 * 工具结果本地存档（localStorage）：标题工坊/多平台改写/口播脚本/评论助手/封面 A/B
 *
 * 模式与 ideaArchive.ts / benchmarkHistory.ts 一致：
 * 纯函数负责摘要、裁剪与损坏数据过滤，方便单测；
 * load/save 封装 localStorage 读写（node 环境下安全降级）。
 *
 * 存档按工具 key 分桶（每桶独立 localStorage 键），条目结构统一为
 * { id, summary, payload, createdAt }，payload 为各工具自己的输入 + 完整结果，
 * 点击存档条目即可把该次生成恢复到页面，不再重新消耗 AI 额度。
 */
import type { TitleCandidate } from '../api/title'
import type { RewritePlatform, RewriteResult } from '../api/rewrite'
import type { ScriptDuration, ScriptScene, VideoScript } from '../api/script'
import type { ReplyItem, ReplyTone } from '../api/reply'
import type { CoverDirection } from '../api/cover'

/** 每个工具桶的存档条数上限 */
export const TOOL_ARCHIVE_LIMIT = 10

/** 输入摘要最大字数 */
export const TOOL_SUMMARY_MAX_CHARS = 50

/** 各工具桶的 localStorage 键 */
export const TITLE_ARCHIVE_KEY = 'redink_title_archive'
export const REWRITE_ARCHIVE_KEY = 'redink_rewrite_archive'
export const SCRIPT_ARCHIVE_KEY = 'redink_script_archive'
export const REPLY_ARCHIVE_KEY = 'redink_reply_archive'
export const COVER_ARCHIVE_KEY = 'redink_cover_archive'

/** localStorage 的最小接口，便于测试注入 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/** 一条工具存档（payload 为各工具的输入 + 完整结果） */
export interface ToolArchiveEntry<P> {
  /** 唯一 ID */
  id: string
  /** 输入摘要（前 50 字） */
  summary: string
  /** 该次生成的输入与完整结果 */
  payload: P
  /** 时间戳（毫秒） */
  createdAt: number
}

// ==================== 各工具的 payload 结构 ====================

/** 标题工坊：一次生成的输入与候选标题 */
export interface TitleArchivePayload {
  topic: string
  platform: string
  style: string
  titles: TitleCandidate[]
}

/** 多平台改写：一次改写的输入与各平台结果 */
export interface RewriteArchivePayload {
  content: string
  sourcePlatform: RewritePlatform | ''
  targetPlatforms: RewritePlatform[]
  results: RewriteResult[]
}

/** 口播脚本：一次生成的输入与完整脚本 */
export interface ScriptArchivePayload {
  content: string
  duration: ScriptDuration
  scene: ScriptScene
  script: VideoScript
}

/** 评论助手：一次生成的输入与回复建议 */
export interface ReplyArchivePayload {
  comments: string[]
  tone: ReplyTone
  includePinned: boolean
  replies: ReplyItem[]
  pinnedComment: string
}

/** 封面 A/B：一次生成的输入、方向数组与逐方向的「已采用」标记 */
export interface CoverArchivePayload {
  topic: string
  content: string
  directions: CoverDirection[]
  /** 与 directions 一一对应；标记该方向是否被实际采用（为将来的封面胜率统计沉淀数据） */
  adopted: boolean[]
}

// ==================== 纯函数：摘要 / 校验 / 解析 / 裁剪 ====================

/**
 * 把输入压缩成摘要：合并空白后截取前 50 字
 */
export function buildInputSummary(input: string, maxChars: number = TOOL_SUMMARY_MAX_CHARS): string {
  const collapsed = input.replace(/\s+/g, ' ').trim()
  if (collapsed.length <= maxChars) return collapsed
  return collapsed.slice(0, maxChars) + '…'
}

function isStringArray(value: unknown): value is string[] {
  return Array.isArray(value) && value.every(item => typeof item === 'string')
}

/** 校验标题工坊 payload（用于丢弃损坏数据） */
export function isValidTitlePayload(value: unknown): value is TitleArchivePayload {
  if (typeof value !== 'object' || value === null) return false
  const p = value as Record<string, unknown>
  if (typeof p.topic !== 'string' || typeof p.platform !== 'string' || typeof p.style !== 'string') return false
  if (!Array.isArray(p.titles) || p.titles.length === 0) return false
  return p.titles.every(item => {
    if (typeof item !== 'object' || item === null) return false
    const t = item as Record<string, unknown>
    return typeof t.text === 'string' && !!t.text
      && typeof t.score === 'number' && Number.isFinite(t.score)
      && isStringArray(t.elements)
  })
}

/** 校验多平台改写 payload */
export function isValidRewritePayload(value: unknown): value is RewriteArchivePayload {
  if (typeof value !== 'object' || value === null) return false
  const p = value as Record<string, unknown>
  if (typeof p.content !== 'string' || typeof p.sourcePlatform !== 'string') return false
  if (!isStringArray(p.targetPlatforms)) return false
  if (!Array.isArray(p.results) || p.results.length === 0) return false
  return p.results.every(item => {
    if (typeof item !== 'object' || item === null) return false
    const r = item as Record<string, unknown>
    return typeof r.platform === 'string'
      && typeof r.title === 'string'
      && typeof r.content === 'string'
      && isStringArray(r.tags)
  })
}

/** 校验口播脚本 payload */
export function isValidScriptPayload(value: unknown): value is ScriptArchivePayload {
  if (typeof value !== 'object' || value === null) return false
  const p = value as Record<string, unknown>
  if (typeof p.content !== 'string' || typeof p.duration !== 'string' || typeof p.scene !== 'string') return false

  const script = p.script as Record<string, unknown> | null | undefined
  if (typeof script !== 'object' || script === null) return false
  const strFields = ['title', 'hook', 'bgm_mood', 'cta'] as const
  if (strFields.some(field => typeof script[field] !== 'string')) return false
  if (!Array.isArray(script.segments) || script.segments.length === 0) return false
  return script.segments.every(item => {
    if (typeof item !== 'object' || item === null) return false
    const seg = item as Record<string, unknown>
    return typeof seg.voiceover === 'string' && !!seg.voiceover
  })
}

/** 校验评论助手 payload */
export function isValidReplyPayload(value: unknown): value is ReplyArchivePayload {
  if (typeof value !== 'object' || value === null) return false
  const p = value as Record<string, unknown>
  if (!isStringArray(p.comments)) return false
  if (typeof p.tone !== 'string' || typeof p.includePinned !== 'boolean') return false
  if (typeof p.pinnedComment !== 'string') return false
  if (!Array.isArray(p.replies) || p.replies.length === 0) return false
  return p.replies.every(item => {
    if (typeof item !== 'object' || item === null) return false
    const r = item as Record<string, unknown>
    return typeof r.comment === 'string' && isStringArray(r.suggestions)
  })
}

/** 校验封面 A/B payload */
export function isValidCoverPayload(value: unknown): value is CoverArchivePayload {
  if (typeof value !== 'object' || value === null) return false
  const p = value as Record<string, unknown>
  if (typeof p.topic !== 'string' || typeof p.content !== 'string') return false
  if (!Array.isArray(p.adopted) || !p.adopted.every(item => typeof item === 'boolean')) return false
  if (!Array.isArray(p.directions) || p.directions.length === 0) return false
  return p.directions.every(item => {
    if (typeof item !== 'object' || item === null) return false
    const d = item as Record<string, unknown>
    return typeof d.title === 'string' && !!d.title
      && typeof d.subtitle === 'string'
      && typeof d.visual_concept === 'string'
      && typeof d.style === 'string'
      && typeof d.score === 'number' && Number.isFinite(d.score)
      && typeof d.reason === 'string'
  })
}

/**
 * 判断一条存档条目是否结构完整（payload 交给各工具的校验函数）
 */
export function isValidToolEntry<P>(
  value: unknown,
  isValidPayload: (payload: unknown) => payload is P
): value is ToolArchiveEntry<P> {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  if (typeof entry.id !== 'string' || !entry.id) return false
  if (typeof entry.summary !== 'string') return false
  if (typeof entry.createdAt !== 'number' || !Number.isFinite(entry.createdAt)) return false
  return isValidPayload(entry.payload)
}

/**
 * 解析持久化 JSON：非法 JSON / 非数组返回空列表，损坏条目逐条丢弃
 */
export function parseToolArchiveJson<P>(
  json: string | null,
  isValidPayload: (payload: unknown) => payload is P
): Array<ToolArchiveEntry<P>> {
  if (!json) return []

  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return []
  }

  if (!Array.isArray(parsed)) return []
  return parsed
    .filter((item): item is ToolArchiveEntry<P> => isValidToolEntry(item, isValidPayload))
    .slice(0, TOOL_ARCHIVE_LIMIT)
}

/**
 * 头插一条存档并裁剪到上限（不修改入参）
 */
export function addToolArchiveEntry<P>(
  list: Array<ToolArchiveEntry<P>>,
  entry: ToolArchiveEntry<P>,
  limit: number = TOOL_ARCHIVE_LIMIT
): Array<ToolArchiveEntry<P>> {
  return [entry, ...list].slice(0, limit)
}

/**
 * 构造一条存档条目（summary 由 input 自动压缩）
 */
export function createToolArchiveEntry<P>(params: {
  input: string
  payload: P
  now?: number
}): ToolArchiveEntry<P> {
  const createdAt = params.now ?? Date.now()
  return {
    id: `tool_${createdAt}_${Math.random().toString(36).slice(2, 8)}`,
    summary: buildInputSummary(params.input),
    payload: params.payload,
    createdAt,
  }
}

/** 存档时间的展示格式：M/D HH:mm（与选题/洞察历史区一致） */
export function formatArchiveTime(timestamp: number): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ==================== localStorage 读写 ====================

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/**
 * 从 localStorage 读取某个工具桶的存档（不可用/损坏时返回空列表）
 */
export function loadToolArchive<P>(
  key: string,
  isValidPayload: (payload: unknown) => payload is P,
  storage: StorageLike | null = defaultStorage()
): Array<ToolArchiveEntry<P>> {
  if (!storage) return []
  try {
    return parseToolArchiveJson(storage.getItem(key), isValidPayload)
  } catch {
    return []
  }
}

/**
 * 写入某个工具桶的存档到 localStorage（配额溢出等异常静默忽略）
 */
export function saveToolArchive<P>(
  key: string,
  list: Array<ToolArchiveEntry<P>>,
  storage: StorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(key, JSON.stringify(list.slice(0, TOOL_ARCHIVE_LIMIT)))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响主流程
  }
}
