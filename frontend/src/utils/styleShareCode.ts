import { styleCategories, type StyleCategory, type StyleTemplate } from '../data/styleTemplates'

/**
 * 风格分享码 - 自定义风格的编码 / 解码（纯函数，无副作用）
 *
 * 分享码格式：`RINK1.<base64url(JSON)>`
 * - `RINK1` 为版本前缀，便于未来演进（RINK2、RINK3 ...）；
 * - JSON 只包含白名单字段（不含 id / custom 等本地状态），
 *   中文与 emoji 先经 TextEncoder 转 UTF-8 字节再 base64，避免裸 btoa 的 Latin1 限制；
 * - base64url 变体（+ -> -，/ -> _，去 = padding），复制到聊天软件不会被转义。
 *
 * 解码时容忍首尾空白与中间换行（聊天软件常把长文本折行），
 * 并对各字段做长度钳制，防止恶意构造的超长内容注入 localStorage。
 */

/** 当前分享码版本前缀 */
export const SHARE_CODE_PREFIX = 'RINK1'

/** 字段长度上限（超出关键字段判失败，次要字段截断） */
export const SHARE_LIMITS = {
  /** 名称最长 30 字 */
  name: 30,
  /** 描述最长 200 字，超出截断 */
  description: 200,
  /** 提示词最长 2000 字 */
  stylePrompt: 2000,
  /** 封面渐变 CSS 最长 300 字，超出用配色重建 */
  coverGradient: 300,
  /** 最多保留 8 个配色 */
  colorCount: 8,
  /** 最多保留 10 个场景，单个场景最长 20 字 */
  sceneCount: 10,
  sceneLength: 20
} as const

/** 分享码中携带的风格数据（即可直接传给 addCustomStyle 的形状） */
export type SharedStylePayload = Omit<StyleTemplate, 'id' | 'custom'>

/** 解码失败原因 */
export type ShareCodeErrorCode =
  | 'invalid-format'
  | 'unsupported-version'
  | 'corrupt-data'
  | 'invalid-fields'

/** 解码结果（判别联合） */
export type DecodeShareCodeResult =
  | { ok: true; style: SharedStylePayload }
  | { ok: false; error: ShareCodeErrorCode; message: string }

/** 各失败原因对应的用户可读提示 */
const ERROR_MESSAGES: Record<ShareCodeErrorCode, string> = {
  'invalid-format': '这段文本不是有效的风格分享码，请确认复制完整（以 RINK 开头）',
  'unsupported-version': '分享码版本过新，当前版本暂不支持导入',
  'corrupt-data': '分享码内容已损坏，请让对方重新生成后再试',
  'invalid-fields': '分享码中的风格字段缺失或超长，无法导入'
}

function fail(error: ShareCodeErrorCode): DecodeShareCodeResult {
  return { ok: false, error, message: ERROR_MESSAGES[error] }
}

/** UTF-8 字节 -> base64url（无 padding） */
function bytesToBase64Url(bytes: Uint8Array): string {
  let binary = ''
  for (const byte of bytes) {
    binary += String.fromCharCode(byte)
  }
  return btoa(binary).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/, '')
}

/** base64url -> UTF-8 字节，非法输入返回 null */
function base64UrlToBytes(text: string): Uint8Array | null {
  const base64 = text.replace(/-/g, '+').replace(/_/g, '/')
  const padded = base64 + '='.repeat((4 - (base64.length % 4)) % 4)
  try {
    const binary = atob(padded)
    const bytes = new Uint8Array(binary.length)
    for (let i = 0; i < binary.length; i++) {
      bytes[i] = binary.charCodeAt(i)
    }
    return bytes
  } catch {
    return null
  }
}

/**
 * 把自定义风格编码为分享码文本
 *
 * 只序列化白名单字段，id / custom 等本地状态不进入分享码。
 */
export function encodeStyleShareCode(style: SharedStylePayload): string {
  const payload: SharedStylePayload = {
    name: style.name,
    category: style.category,
    description: style.description,
    coverGradient: style.coverGradient,
    colors: [...style.colors],
    scenes: [...style.scenes],
    stylePrompt: style.stylePrompt
  }
  const bytes = new TextEncoder().encode(JSON.stringify(payload))
  return `${SHARE_CODE_PREFIX}.${bytesToBase64Url(bytes)}`
}

/** hex 色值校验（#RGB / #RRGGBB / #RRGGBBAA 等 3~8 位） */
const HEX_COLOR_PATTERN = /^#[0-9a-fA-F]{3,8}$/

/** 配色缺失/全部非法时的兜底配色（与新建表单默认值一致） */
const FALLBACK_COLORS = ['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238']

/** 清洗配色数组：只保留合法 hex，统一大写，数量钳制，为空则兜底 */
function sanitizeColors(value: unknown): string[] {
  const colors = Array.isArray(value)
    ? value
        .filter((item): item is string => typeof item === 'string')
        .map(item => item.trim().toUpperCase())
        .filter(item => HEX_COLOR_PATTERN.test(item))
        .slice(0, SHARE_LIMITS.colorCount)
    : []
  return colors.length > 0 ? colors : [...FALLBACK_COLORS]
}

/** 清洗场景数组：去空白项，单项与数量都做钳制 */
function sanitizeScenes(value: unknown): string[] {
  if (!Array.isArray(value)) return []
  return value
    .filter((item): item is string => typeof item === 'string')
    .map(item => item.trim().slice(0, SHARE_LIMITS.sceneLength))
    .filter(Boolean)
    .slice(0, SHARE_LIMITS.sceneCount)
}

/** 用配色重建封面渐变（与新建表单的生成规则一致） */
function buildCoverGradient(colors: string[]): string {
  const [a, b, c] = [colors[0], colors[1] ?? colors[0], colors[2] ?? colors[0]]
  return `linear-gradient(135deg, ${a} 0%, ${b} 40%, ${c} 100%)`
}

/**
 * 封面渐变白名单校验：必须是渐变函数，且禁止 url()。
 * coverGradient 会绑定到卡片 background 样式，任意 CSS 里的 url() 可
 * 触发外部网络请求（追踪像素），恶意分享码不该有这个能力。
 */
function isSafeCoverGradient(value: string): boolean {
  const lower = value.toLowerCase()
  if (lower.includes('url(')) return false
  return /^(repeating-)?(linear|radial|conic)-gradient\(/.test(lower)
}

/**
 * 解析分享码文本
 *
 * 关键字段（名称、提示词）缺失或超长 -> 判失败；
 * 次要字段（描述、配色、场景、分类、封面）做截断 / 兜底，尽量导入成功。
 */
export function decodeStyleShareCode(text: string): DecodeShareCodeResult {
  if (typeof text !== 'string') return fail('invalid-format')
  // 容忍首尾空白与粘贴折行：分享码本体不含空白字符，直接全部剔除
  const compact = text.replace(/\s+/g, '')
  if (!compact) return fail('invalid-format')

  const match = /^RINK(\d{1,3})\.([A-Za-z0-9_-]+)$/.exec(compact)
  if (!match) return fail('invalid-format')
  if (match[1] !== '1') return fail('unsupported-version')

  const bytes = base64UrlToBytes(match[2])
  if (!bytes) return fail('corrupt-data')

  let parsed: unknown
  try {
    parsed = JSON.parse(new TextDecoder('utf-8', { fatal: true }).decode(bytes))
  } catch {
    return fail('corrupt-data')
  }
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    return fail('invalid-fields')
  }
  const raw = parsed as Record<string, unknown>

  // 关键字段：类型正确、非空、不超长，否则整体判失败
  const name = typeof raw.name === 'string' ? raw.name.trim() : ''
  const stylePrompt = typeof raw.stylePrompt === 'string' ? raw.stylePrompt.trim() : ''
  if (!name || name.length > SHARE_LIMITS.name) return fail('invalid-fields')
  if (!stylePrompt || stylePrompt.length > SHARE_LIMITS.stylePrompt) return fail('invalid-fields')

  // 次要字段：钳制 / 兜底
  const description =
    typeof raw.description === 'string'
      ? raw.description.trim().slice(0, SHARE_LIMITS.description)
      : ''
  const category: StyleCategory = styleCategories.includes(raw.category as StyleCategory)
    ? (raw.category as StyleCategory)
    : styleCategories[0]
  const colors = sanitizeColors(raw.colors)
  const rawGradient = typeof raw.coverGradient === 'string' ? raw.coverGradient.trim() : ''
  const coverGradient =
    rawGradient &&
    rawGradient.length <= SHARE_LIMITS.coverGradient &&
    isSafeCoverGradient(rawGradient)
      ? rawGradient
      : buildCoverGradient(colors)

  return {
    ok: true,
    style: {
      name,
      category,
      description: description || '来自分享码的风格',
      coverGradient,
      colors,
      scenes: sanitizeScenes(raw.scenes),
      stylePrompt
    }
  }
}

/**
 * 导入时的重名处理：若名称已存在，自动追加「(2)」「(3)」... 后缀
 *
 * @param name 期望使用的名称
 * @param existingNames 当前已有的全部风格名称（含预设与自定义）
 */
export function resolveDuplicateName(name: string, existingNames: readonly string[]): string {
  const taken = new Set(existingNames)
  if (!taken.has(name)) return name
  let suffix = 2
  while (taken.has(`${name}(${suffix})`)) {
    suffix++
  }
  return `${name}(${suffix})`
}
