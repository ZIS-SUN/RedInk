/**
 * 套路模板库（localStorage）
 *
 * 对标拆解产出的「可复用套路模板」不再只有复制一条出路：
 * 用户可以把看中的套路存进本库长期沉淀（benchmarkHistory 仅 20 条滚动覆盖，攒下的套路会丢）。
 *
 * 模式与 toolArchive.ts / benchmarkHistory.ts 一致：
 * 纯函数负责校验、裁剪与损坏数据过滤，方便单测；
 * load/save 封装 localStorage 读写（node 环境下安全降级）。
 */

/** localStorage 存储键 */
export const PATTERN_LIBRARY_KEY = 'redink_pattern_library'

/** 套路条数上限 */
export const PATTERN_LIBRARY_LIMIT = 50

/** 套路名称最大字数（超出截断，避免列表被超长名称撑爆） */
export const PATTERN_NAME_MAX_CHARS = 50

/** localStorage 的最小接口，便于测试注入 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/** 一条套路模板 */
export interface PatternEntry {
  /** 唯一 ID */
  id: string
  /** 套路名称（默认取对标内容标题/摘要） */
  name: string
  /** 套路模板全文（槽位用【】标出） */
  template: string
  /** 来源对标内容的标题/摘要 */
  source_title: string
  /** 存入时间戳（毫秒） */
  created_at: number
}

/**
 * 规整套路名称：合并空白并截断到上限；空名回退到来源标题，再回退到「未命名套路」
 */
export function normalizePatternName(name: string, sourceTitle: string = ''): string {
  const collapsed = name.replace(/\s+/g, ' ').trim()
    || sourceTitle.replace(/\s+/g, ' ').trim()
    || '未命名套路'
  if (collapsed.length <= PATTERN_NAME_MAX_CHARS) return collapsed
  return collapsed.slice(0, PATTERN_NAME_MAX_CHARS) + '…'
}

/**
 * 判断一条套路是否结构完整（用于丢弃损坏数据）
 */
export function isValidPatternEntry(value: unknown): value is PatternEntry {
  if (typeof value !== 'object' || value === null) return false
  const entry = value as Record<string, unknown>
  if (typeof entry.id !== 'string' || !entry.id) return false
  if (typeof entry.name !== 'string' || !entry.name) return false
  if (typeof entry.template !== 'string' || !entry.template) return false
  if (typeof entry.source_title !== 'string') return false
  if (typeof entry.created_at !== 'number' || !Number.isFinite(entry.created_at)) return false
  return true
}

/**
 * 解析持久化 JSON：非法 JSON / 非数组返回空列表，损坏条目逐条丢弃
 */
export function parsePatternLibraryJson(json: string | null): PatternEntry[] {
  if (!json) return []

  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return []
  }

  if (!Array.isArray(parsed)) return []
  return parsed.filter(isValidPatternEntry).slice(0, PATTERN_LIBRARY_LIMIT)
}

/**
 * 头插一条套路并裁剪到上限（不修改入参）
 */
export function addPatternEntry(
  list: PatternEntry[],
  entry: PatternEntry,
  limit: number = PATTERN_LIBRARY_LIMIT
): PatternEntry[] {
  return [entry, ...list].slice(0, limit)
}

/**
 * 按 ID 删除一条套路（不修改入参；ID 不存在时原样返回新数组）
 */
export function removePatternEntry(list: PatternEntry[], id: string): PatternEntry[] {
  return list.filter(entry => entry.id !== id)
}

/**
 * 构造一条套路（name 为空时默认取来源标题）
 */
export function createPatternEntry(params: {
  name: string
  template: string
  sourceTitle: string
  now?: number
}): PatternEntry {
  const createdAt = params.now ?? Date.now()
  return {
    id: `pattern_${createdAt}_${Math.random().toString(36).slice(2, 8)}`,
    name: normalizePatternName(params.name, params.sourceTitle),
    template: params.template,
    source_title: params.sourceTitle,
    created_at: createdAt,
  }
}

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/**
 * 从 localStorage 读取套路库（不可用/损坏时返回空列表）
 */
export function loadPatternLibrary(storage: StorageLike | null = defaultStorage()): PatternEntry[] {
  if (!storage) return []
  try {
    return parsePatternLibraryJson(storage.getItem(PATTERN_LIBRARY_KEY))
  } catch {
    return []
  }
}

/**
 * 写入套路库到 localStorage（配额溢出等异常静默忽略）
 */
export function savePatternLibrary(
  list: PatternEntry[],
  storage: StorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(PATTERN_LIBRARY_KEY, JSON.stringify(list.slice(0, PATTERN_LIBRARY_LIMIT)))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响主流程
  }
}
