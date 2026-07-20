/**
 * 平台安全区数据与预览遮罩工具（纯前端）
 *
 * 背景：导出的图片在抖音 / 小红书 / B站等 App 内展示时，会被平台自身 UI
 * （右侧点赞评论栏、底部文案区、角标等）遮挡。本模块定义各平台的
 * 「遮挡区域」数据，供预览时叠加半透明遮罩提示创作者避开这些区域。
 *
 * 约定：
 * - 区域坐标统一使用 0~1 相对比例（相对目标尺寸宽高），任意分辨率可换算；
 * - 区域数值为经验值（按平台常见 UI 布局估算，非官方标准），会随平台改版偏移，
 *   仅作排版参考；
 * - 纯函数负责方案匹配与像素换算，便于 node 环境单测；
 * - 「安全区显隐」设置仿照 watermarkSettings.ts 做 localStorage 持久化，
 *   损坏 JSON 安全降级为默认值。
 *
 * 注意：遮罩只用于预览展示，绝不参与导出渲染（导出路径见 canvasExport.ts）。
 */
import type { StorageLike } from './watermarkSettings'

/** 单个遮挡区域（坐标为 0~1 相对比例） */
export interface SafeZoneRegion {
  key: string
  /** 中文名称，预览遮罩上的小标签 */
  label: string
  x: number
  y: number
  w: number
  h: number
}

/** 某个尺寸预设对应的安全区方案 */
export interface SafeZoneScheme {
  /** 对应 canvasExport.ts 里 SIZE_PRESETS 的 preset id */
  presetId: string
  /** 平台场景说明，用于 UI 提示 */
  label: string
  regions: SafeZoneRegion[]
}

/**
 * 内置安全区方案（key 为 preset id）
 *
 * 数值均为经验值：参考各平台 App 当前版面手工估算，
 * 平台改版后可能有 1%~3% 的偏移，够排版避让即可。
 */
export const SAFE_ZONE_SCHEMES: SafeZoneScheme[] = [
  {
    presetId: 'douyin-9-16',
    label: '抖音竖屏播放页',
    regions: [
      // 顶部：状态栏 + 搜索 / 直播入口，约占屏高 8%
      { key: 'douyin-top', label: '顶部搜索栏', x: 0, y: 0, w: 1, h: 0.08 },
      // 右侧：头像 / 点赞 / 评论 / 收藏 / 分享竖排操作栏，约占右侧 15% 宽、屏高 35%~85%
      { key: 'douyin-right', label: '点赞评论栏', x: 0.85, y: 0.35, w: 0.15, h: 0.5 },
      // 底部：作者昵称 + 文案 + 进度条 / 底部导航，约占屏高最后 22%
      { key: 'douyin-bottom', label: '底部文案区', x: 0, y: 0.78, w: 1, h: 0.22 }
    ]
  },
  {
    presetId: 'xhs-3-4',
    label: '小红书封面（信息流）',
    regions: [
      // 底部：信息流卡片上叠加的标题文字区，约占封面高最后 14%
      { key: 'xhs-bottom', label: '底部标题文字区', x: 0, y: 0.86, w: 1, h: 0.14 }
    ]
  },
  {
    presetId: 'bili-cover',
    label: 'B站封面（列表页）',
    regions: [
      // 右下角：视频时长角标，约占右侧 25% 宽、底部 12% 高
      { key: 'bili-duration', label: '时长角标', x: 0.75, y: 0.88, w: 0.25, h: 0.12 }
    ]
  }
]

/**
 * 按 preset id 匹配安全区方案，无数据的尺寸（如 1:1）返回 null
 * 纯函数，便于单测
 */
export function getSafeZoneScheme(presetId: string): SafeZoneScheme | null {
  return SAFE_ZONE_SCHEMES.find(scheme => scheme.presetId === presetId) ?? null
}

/** 像素矩形（目标画布坐标系） */
export interface SafeZonePixelRect {
  x: number
  y: number
  width: number
  height: number
}

/** 相对比例钳制到 0~1（非数值回退 0），防御脏数据 */
export function clamp01(value: number): number {
  if (!Number.isFinite(value)) return 0
  return Math.min(1, Math.max(0, value))
}

/**
 * 把相对坐标区域换算成目标尺寸下的像素矩形
 * 越界比例会被钳制在画布内，目标尺寸非法时返回零矩形
 * 纯函数，便于单测
 */
export function toPixelRect(
  region: Pick<SafeZoneRegion, 'x' | 'y' | 'w' | 'h'>,
  dstWidth: number,
  dstHeight: number
): SafeZonePixelRect {
  if (!Number.isFinite(dstWidth) || !Number.isFinite(dstHeight) || dstWidth <= 0 || dstHeight <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 }
  }
  const x = clamp01(region.x)
  const y = clamp01(region.y)
  // 宽高再按剩余空间钳制，保证矩形不超出画布
  const w = Math.min(clamp01(region.w), 1 - x)
  const h = Math.min(clamp01(region.h), 1 - y)
  return {
    x: Math.round(x * dstWidth),
    y: Math.round(y * dstHeight),
    width: Math.round(w * dstWidth),
    height: Math.round(h * dstHeight)
  }
}

/* ---------------- 显隐设置持久化 ---------------- */

/** localStorage 存储键 */
export const SAFE_ZONE_SETTINGS_KEY = 'redink_export_safezone'

/** 页面上可持久化的安全区设置 */
export interface SafeZoneSettings {
  /** 是否在预览上叠加安全区遮罩，默认关 */
  enabled: boolean
}

/** 默认设置：不显示遮罩 */
export function defaultSafeZoneSettings(): SafeZoneSettings {
  return { enabled: false }
}

/**
 * 解析持久化 JSON：损坏 / 非对象整体丢弃回默认值，
 * enabled 非布尔时回退默认值
 */
export function parseSafeZoneSettings(json: string | null): SafeZoneSettings {
  const defaults = defaultSafeZoneSettings()
  if (!json) return defaults

  let parsed: unknown
  try {
    parsed = JSON.parse(json)
  } catch {
    return defaults
  }
  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) return defaults

  const raw = parsed as Record<string, unknown>
  return {
    enabled: typeof raw.enabled === 'boolean' ? raw.enabled : defaults.enabled
  }
}

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/** 从 localStorage 读取设置（不可用/损坏时返回默认值） */
export function loadSafeZoneSettings(
  storage: StorageLike | null = defaultStorage()
): SafeZoneSettings {
  if (!storage) return defaultSafeZoneSettings()
  try {
    return parseSafeZoneSettings(storage.getItem(SAFE_ZONE_SETTINGS_KEY))
  } catch {
    return defaultSafeZoneSettings()
  }
}

/** 写入设置到 localStorage（配额溢出等异常静默忽略） */
export function saveSafeZoneSettings(
  settings: SafeZoneSettings,
  storage: StorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(SAFE_ZONE_SETTINGS_KEY, JSON.stringify(settings))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响预览主流程
  }
}
