/**
 * 发布助手纯逻辑：
 * - 平台 key → 中文 label → 徽标色调 的映射（未知 key 安全回退）
 * - 备料结果的小判断：图片数量文案、文案完整性
 * 与视图解耦，便于 vitest 单测。
 */

/** 徽标色调，视图层映射到对应 -soft 底色 token */
export type PlatformTone = 'primary' | 'info' | 'success' | 'warning' | 'danger' | 'neutral'

export interface PlatformMeta {
  /** 中文名称 */
  label: string
  /** 徽标色调 */
  tone: PlatformTone
}

/** 已知平台的内置映射（后端 key 约定为拼音/英文小写） */
const PLATFORM_META: Record<string, PlatformMeta> = {
  xiaohongshu: { label: '小红书', tone: 'primary' },
  douyin: { label: '抖音', tone: 'neutral' },
  bilibili: { label: 'B站', tone: 'info' },
  shipinhao: { label: '视频号', tone: 'success' },
  kuaishou: { label: '快手', tone: 'warning' },
  weibo: { label: '微博', tone: 'danger' },
  zhihu: { label: '知乎', tone: 'info' },
  gongzhonghao: { label: '公众号', tone: 'success' }
}

/**
 * 取平台展示信息。
 * @param key 平台 key（如 "xiaohongshu"）
 * @param backendLabel 后端下发的 label，优先于内置映射
 * 未知 key 回退：label 用 backendLabel，其次 key 本身，都没有则「未知平台」；色调回退 neutral。
 */
export function getPlatformMeta(key: string | null | undefined, backendLabel?: string): PlatformMeta {
  const normalized = (key || '').trim().toLowerCase()
  const builtin = normalized ? PLATFORM_META[normalized] : undefined
  if (builtin) {
    return { label: backendLabel?.trim() || builtin.label, tone: builtin.tone }
  }
  return {
    label: backendLabel?.trim() || (key || '').trim() || '未知平台',
    tone: 'neutral'
  }
}

/** 备料返回的文案块 */
export interface PrepareText {
  titles?: string[] | null
  copywriting?: string | null
  tags?: string[] | null
}

/** 是否有已导出的图片文件 */
export function hasPreparedFiles(files: string[] | null | undefined): boolean {
  return Array.isArray(files) && files.length > 0
}

/** 图片数量的展示文案 */
export function fileCountLabel(files: string[] | null | undefined): string {
  if (!hasPreparedFiles(files)) return '暂无图片'
  return `共 ${files!.length} 张图片`
}

/** 单块文案是否为空（去空白后） */
function isBlank(value: string | null | undefined): boolean {
  return !value || value.trim().length === 0
}

function hasNonBlankItem(list: string[] | null | undefined): boolean {
  return Array.isArray(list) && list.some(item => !isBlank(item))
}

/**
 * 找出缺失的文案块，返回中文名称列表（顺序固定：标题/正文/标签）。
 * 全部齐备时返回空数组。
 */
export function missingTextParts(text: PrepareText | null | undefined): string[] {
  const missing: string[] = []
  if (!hasNonBlankItem(text?.titles)) missing.push('标题')
  if (isBlank(text?.copywriting)) missing.push('正文')
  if (!hasNonBlankItem(text?.tags)) missing.push('标签')
  return missing
}

/** 文案是否完整（标题、正文、标签都非空） */
export function isPrepareTextComplete(text: PrepareText | null | undefined): boolean {
  return missingTextParts(text).length === 0
}
