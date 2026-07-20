/**
 * 多尺寸导出水印设置的本地持久化（localStorage）
 *
 * 纯函数负责默认值、损坏 JSON 丢弃与越界参数钳制，方便单测；
 * load/save 封装 localStorage 读写（node 环境下安全降级）。
 */
import type { WatermarkPosition } from './canvasExport'

/** localStorage 存储键 */
export const WATERMARK_SETTINGS_KEY = 'redink_export_watermark'

/** 水印文字最大长度（与输入框 maxlength 一致） */
export const WATERMARK_TEXT_MAX_CHARS = 30

/** 字号档位 */
export type WatermarkSizeKey = 'small' | 'medium' | 'large'

/** 颜色档位（white 带阴影保证深浅底可读 / black / 主题红） */
export type WatermarkColorKey = 'white' | 'black' | 'red'

/** 字号档位 → 占画布宽度比例 */
export const WATERMARK_SIZE_RATIOS: Record<WatermarkSizeKey, number> = {
  small: 0.025,
  medium: 0.035,
  large: 0.05
}

/** 颜色档位 → 绘制色值（red 取设计 token --primary） */
export const WATERMARK_COLOR_VALUES: Record<WatermarkColorKey, string> = {
  white: '#FFFFFF',
  black: '#211E1B',
  red: '#EF2A45'
}

/** 页面上可持久化的全部水印设置 */
export interface WatermarkSettings {
  text: string
  position: WatermarkPosition
  /** 不透明度 0.1~1 */
  opacity: number
  size: WatermarkSizeKey
  color: WatermarkColorKey
}

const POSITIONS: WatermarkPosition[] = [
  'top-left',
  'top-right',
  'bottom-left',
  'bottom-right',
  'bottom-center'
]

const SIZE_KEYS: WatermarkSizeKey[] = ['small', 'medium', 'large']
const COLOR_KEYS: WatermarkColorKey[] = ['white', 'black', 'red']

/** 默认设置：右下角 / 60% 不透明度 / 中号 / 白色 */
export function defaultWatermarkSettings(): WatermarkSettings {
  return {
    text: '',
    position: 'bottom-right',
    opacity: 0.6,
    size: 'medium',
    color: 'white'
  }
}

/** 不透明度钳制到 0.1~1（非数值回退默认 0.6） */
export function clampOpacity(value: unknown): number {
  if (typeof value !== 'number' || !Number.isFinite(value)) return 0.6
  return Math.min(1, Math.max(0.1, value))
}

/**
 * 解析持久化 JSON：损坏 / 非对象整体丢弃回默认值，
 * 单个字段非法则回退该字段默认值并钳制越界参数
 */
export function parseWatermarkSettings(json: string | null): WatermarkSettings {
  const defaults = defaultWatermarkSettings()
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
    text:
      typeof raw.text === 'string' ? raw.text.slice(0, WATERMARK_TEXT_MAX_CHARS) : defaults.text,
    position: POSITIONS.includes(raw.position as WatermarkPosition)
      ? (raw.position as WatermarkPosition)
      : defaults.position,
    opacity: clampOpacity(raw.opacity),
    size: SIZE_KEYS.includes(raw.size as WatermarkSizeKey)
      ? (raw.size as WatermarkSizeKey)
      : defaults.size,
    color: COLOR_KEYS.includes(raw.color as WatermarkColorKey)
      ? (raw.color as WatermarkColorKey)
      : defaults.color
  }
}

/** localStorage 的最小接口，便于测试注入 */
export interface StorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

function defaultStorage(): StorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/** 从 localStorage 读取设置（不可用/损坏时返回默认值） */
export function loadWatermarkSettings(
  storage: StorageLike | null = defaultStorage()
): WatermarkSettings {
  if (!storage) return defaultWatermarkSettings()
  try {
    return parseWatermarkSettings(storage.getItem(WATERMARK_SETTINGS_KEY))
  } catch {
    return defaultWatermarkSettings()
  }
}

/** 写入设置到 localStorage（配额溢出等异常静默忽略） */
export function saveWatermarkSettings(
  settings: WatermarkSettings,
  storage: StorageLike | null = defaultStorage()
): void {
  if (!storage) return
  try {
    storage.setItem(WATERMARK_SETTINGS_KEY, JSON.stringify(settings))
  } catch {
    // localStorage 不可写（隐私模式/配额满）时放弃持久化，不影响导出主流程
  }
}
