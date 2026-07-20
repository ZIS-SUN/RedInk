/**
 * 选题灵感 / 评论洞察结果本地存档（localStorage）
 *
 * 模式与 benchmarkHistory.ts 一致：
 * 纯函数负责校验、裁剪与损坏数据过滤，方便单测；
 * load/save 封装 localStorage 读写（node 环境下安全降级）。
 *
 * 另含「选题 → 内容日历条目」的字段映射纯函数（供加入日历弹窗与单测复用）。
 */
import type { TopicIdea } from '../api/topic'
import type { PainPoint } from '../api/insight'
import type { PlanItemInput, PlanPlatform } from '../api/calendar'

/** 选题灵感存档的 localStorage 键 */
export const TOPIC_ARCHIVE_KEY = 'redink_topic_archive'

/** 评论洞察存档的 localStorage 键 */
export const INSIGHT_ARCHIVE_KEY = 'redink_insight_archive'

/** 每类存档的条数上限 */
export const IDEA_ARCHIVE_LIMIT = 10

/** localStorage 的最小接口，便于测试注入 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/** 一次选题灵感生成的存档 */
export interface TopicArchiveEntry {
  /** 唯一 ID */
  id: string
  /** 输入参数：领域/赛道 */
  niche: string
  /** 输入参数：目标平台（中文名，如「小红书」） */
  platform: string
  /** 本次生成是否实际结合了账号数据 */
  accountContextUsed: boolean
  /** 完整生成结果 */
  topics: TopicIdea[]
  /** 时间戳（毫秒） */
  createdAt: number
}

/** 一次评论洞察挖掘的存档 */
export interface InsightArchiveEntry {
  /** 唯一 ID */
  id: string
  /** 输入参数：赛道（选填，可为空串） */
  niche: string
  /** 输入参数：参与分析的评论列表 */
  comments: string[]
  /** 实际参与分析的评论条数 */
  commentCount: number
  /** 完整挖掘结果 */
  painPoints: PainPoint[]
  /** 时间戳（毫秒） */
  createdAt: number
}

/** 校验单条选题结构（TopicIdea / InsightTopicIdea 同构） */
function isValidIdea(value: unknown): value is TopicIdea {
  if (typeof value !== 'object' || value === null) return false
  const idea = value as Record<string, unknown>
  if (typeof idea.title !== 'string' || !idea.title) return false
  if (typeof idea.angle !== 'string') return false
  if (typeof idea.format !== 'string') return false
  if (typeof idea.heat !== 'number' || !Number.isFinite(idea.heat)) return false
  if (!Array.isArray(idea.tags) || idea.tags.some(t => typeof t !== 'string')) return false
  return true
}

/** 校验单个痛点结构 */
function isValidPainPoint(value: unknown): value is PainPoint {
  if (typeof value !== 'object' || value === null) return false
  const point = value as Record<string, unknown>
  if (typeof point.theme !== 'string' || !point.theme) return false
  if (typeof point.summary !== 'string') return false
  if (typeof point.frequency !== 'number' || !Number.isFinite(point.frequency)) return false
  if (!Array.isArray(point.evidence) || point.evidence.some(e => typeof e !== 'string')) return false
  if (!Array.isArray(point.topics) || !point.topics.every(isValidIdea)) return false
  return true
}

/**
 * 判断一条选题灵感存档是否结构完整（用于丢弃损坏数据）
 */
export function isValidTopicEntry(value: unknown): value is TopicArchiveEntry {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  if (typeof entry.id !== 'string' || !entry.id) return false
  if (typeof entry.niche !== 'string') return false
  if (typeof entry.platform !== 'string') return false
  if (typeof entry.accountContextUsed !== 'boolean') return false
  if (typeof entry.createdAt !== 'number' || !Number.isFinite(entry.createdAt)) return false
  if (!Array.isArray(entry.topics) || entry.topics.length === 0) return false
  return entry.topics.every(isValidIdea)
}

/**
 * 判断一条评论洞察存档是否结构完整（用于丢弃损坏数据）
 */
export function isValidInsightEntry(value: unknown): value is InsightArchiveEntry {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  if (typeof entry.id !== 'string' || !entry.id) return false
  if (typeof entry.niche !== 'string') return false
  if (!Array.isArray(entry.comments) || entry.comments.some(c => typeof c !== 'string')) return false
  if (typeof entry.commentCount !== 'number' || !Number.isFinite(entry.commentCount)) return false
  if (typeof entry.createdAt !== 'number' || !Number.isFinite(entry.createdAt)) return false
  if (!Array.isArray(entry.painPoints) || entry.painPoints.length === 0) return false
  return entry.painPoints.every(isValidPainPoint)
}

/**
 * 解析持久化 JSON：非法 JSON / 非数组返回空列表，损坏条目逐条丢弃
 */
function parseArchiveJson<T>(json: string | null, isValid: (value: unknown) => value is T): T[] {
  if (!json) return []

  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return []
  }

  if (!Array.isArray(parsed)) return []
  return parsed.filter(isValid).slice(0, IDEA_ARCHIVE_LIMIT)
}

export function parseTopicArchiveJson(json: string | null): TopicArchiveEntry[] {
  return parseArchiveJson(json, isValidTopicEntry)
}

export function parseInsightArchiveJson(json: string | null): InsightArchiveEntry[] {
  return parseArchiveJson(json, isValidInsightEntry)
}

/**
 * 头插一条存档并裁剪到上限（不修改入参）
 */
export function addArchiveEntry<T>(list: T[], entry: T, limit: number = IDEA_ARCHIVE_LIMIT): T[] {
  return [entry, ...list].slice(0, limit)
}

function makeId(prefix: string, createdAt: number): string {
  return `${prefix}_${createdAt}_${Math.random().toString(36).slice(2, 8)}`
}

/**
 * 构造一条选题灵感存档
 */
export function createTopicArchiveEntry(params: {
  niche: string
  platform: string
  accountContextUsed: boolean
  topics: TopicIdea[]
  now?: number
}): TopicArchiveEntry {
  const createdAt = params.now ?? Date.now()
  return {
    id: makeId('topic', createdAt),
    niche: params.niche,
    platform: params.platform,
    accountContextUsed: params.accountContextUsed,
    topics: params.topics,
    createdAt,
  }
}

/**
 * 构造一条评论洞察存档
 */
export function createInsightArchiveEntry(params: {
  niche: string
  comments: string[]
  commentCount: number
  painPoints: PainPoint[]
  now?: number
}): InsightArchiveEntry {
  const createdAt = params.now ?? Date.now()
  return {
    id: makeId('insight', createdAt),
    niche: params.niche,
    comments: params.comments,
    commentCount: params.commentCount,
    painPoints: params.painPoints,
    createdAt,
  }
}

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/**
 * 从 localStorage 读取选题灵感存档（不可用/损坏时返回空列表）
 */
export function loadTopicArchive(storage: StorageLike | null = defaultStorage()): TopicArchiveEntry[] {
  if (!storage) return []
  try {
    return parseTopicArchiveJson(storage.getItem(TOPIC_ARCHIVE_KEY))
  } catch {
    return []
  }
}

/**
 * 从 localStorage 读取评论洞察存档（不可用/损坏时返回空列表）
 */
export function loadInsightArchive(storage: StorageLike | null = defaultStorage()): InsightArchiveEntry[] {
  if (!storage) return []
  try {
    return parseInsightArchiveJson(storage.getItem(INSIGHT_ARCHIVE_KEY))
  } catch {
    return []
  }
}

function saveArchive<T>(key: string, list: T[], storage: StorageLike | null): void {
  if (!storage) return
  try {
    storage.setItem(key, JSON.stringify(list.slice(0, IDEA_ARCHIVE_LIMIT)))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响主流程
  }
}

/**
 * 写入选题灵感存档到 localStorage（配额溢出等异常静默忽略）
 */
export function saveTopicArchive(
  list: TopicArchiveEntry[],
  storage: StorageLike | null = defaultStorage()
): void {
  saveArchive(TOPIC_ARCHIVE_KEY, list, storage)
}

/**
 * 写入评论洞察存档到 localStorage（配额溢出等异常静默忽略）
 */
export function saveInsightArchive(
  list: InsightArchiveEntry[],
  storage: StorageLike | null = defaultStorage()
): void {
  saveArchive(INSIGHT_ARCHIVE_KEY, list, storage)
}

// ==================== 选题 → 内容日历条目的字段映射 ====================

/** 加入日历所需的选题字段（TopicIdea / InsightTopicIdea 均满足） */
export interface CalendarIdeaLike {
  title: string
  angle: string
  tags: string[]
}

/** 无最佳时段推荐时的默认发布时间 */
export const DEFAULT_PUBLISH_TIME = '19:00'

/** 平台中文名 → 日历 PlanPlatform 枚举（未知平台返回 null） */
const PLATFORM_LABEL_TO_PLAN: Record<string, PlanPlatform> = {
  小红书: 'xiaohongshu',
  抖音: 'douyin',
  公众号: 'gongzhonghao',
  B站: 'bilibili',
  视频号: 'shipinhao',
}

export function platformLabelToPlanPlatform(label: string): PlanPlatform | null {
  return PLATFORM_LABEL_TO_PLAN[label.trim()] ?? null
}

/** 本地时区的 YYYY-MM-DD（避免 toISOString 的 UTC 偏移） */
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 明天的日期（YYYY-MM-DD，本地时区），作为加入日历的默认发布日期 */
export function tomorrowDateStr(now: Date = new Date()): string {
  const d = new Date(now)
  d.setDate(d.getDate() + 1)
  return toDateStr(d)
}

/**
 * 把一条选题映射为 createPlan 的入参：
 * - 标题直接用选题标题
 * - 备注带上切入角度与建议标签（空字段跳过对应行）
 * - 状态固定为 idea（与日历新建表单的默认惯例一致）
 * - 未提供发布时间时回退到默认 19:00
 */
export function ideaToPlanInput(
  idea: CalendarIdeaLike,
  options: {
    platform: PlanPlatform
    publishDate: string
    publishTime?: string
  }
): PlanItemInput {
  const noteLines: string[] = []
  if (idea.angle.trim()) {
    noteLines.push(`切入角度：${idea.angle.trim()}`)
  }
  if (idea.tags.length > 0) {
    noteLines.push(`建议标签：${idea.tags.map(t => `#${t}`).join(' ')}`)
  }

  return {
    title: idea.title,
    platform: options.platform,
    publish_date: options.publishDate,
    publish_time: options.publishTime || DEFAULT_PUBLISH_TIME,
    status: 'idea',
    notes: noteLines.join('\n'),
  }
}

// ==================== 日历备注 → 创作主题文本（ideaToPlanInput 的逆向解析） ====================

/** 从日历备注中解析出的创作上下文 */
export interface PlanNotesContext {
  /** 切入角度（无则为空串） */
  angle: string
  /** 建议标签（已去掉 # 前缀，无则为空数组） */
  tags: string[]
}

/**
 * 解析日历备注中的「切入角度：」「建议标签：」结构化行
 * （选题加入日历时由 ideaToPlanInput 写入；手写备注不匹配时返回空值）
 */
export function parsePlanNotes(notes: string): PlanNotesContext {
  let angle = ''
  let tags: string[] = []

  for (const rawLine of (notes || '').split('\n')) {
    const line = rawLine.trim()
    if (line.startsWith('切入角度：')) {
      angle = line.slice('切入角度：'.length).trim()
    } else if (line.startsWith('建议标签：')) {
      tags = line
        .slice('建议标签：'.length)
        .split(/\s+/)
        .map(tag => tag.replace(/^#/, '').trim())
        .filter(Boolean)
    }
  }

  return { angle, tags }
}

/**
 * 把日历计划（标题 + 备注里的角度/标签）拼成创作主题文本，
 * 与选题工具「用这个创作」的主题格式完全一致（空字段跳过对应行）
 */
export function buildCreationTopicFromPlan(title: string, notes: string): string {
  const lines = [title]
  const { angle, tags } = parsePlanNotes(notes)
  if (angle) {
    lines.push(`切入角度：${angle}`)
  }
  if (tags.length > 0) {
    lines.push(`建议标签：${tags.join(' ')}`)
  }
  return lines.join('\n')
}
