import type { Config } from '../api/types'
import type { AppError } from './errors'

/**
 * AI 服务商配置状态检测
 *
 * 数据来源：GET /api/config 返回的脱敏配置。后端不直接返回"是否已配置"布尔字段，
 * 但脱敏逻辑（prepare_providers_for_response）保证：已保存 API Key 的服务商
 * api_key_masked 为非空字符串，未保存的为空字符串。据此判定配置状态。
 */

/** 各配置分区的检测结果 */
export interface ProviderConfigStatus {
  /** 文本生成分区存在至少一个已保存 API Key 的服务商 */
  textConfigured: boolean
  /** 图片生成分区存在至少一个已保存 API Key 的服务商 */
  imageConfigured: boolean
  /** 任一分区已配置（用于"新用户完全未配置"引导） */
  anyConfigured: boolean
  /** 两个分区都已配置 */
  fullyConfigured: boolean
}

/**
 * 判断服务商列表中是否存在已配置 API Key 的条目
 *
 * 兼容两种来源：
 * - 后端脱敏响应：api_key 恒为空串，api_key_masked 非空表示已保存
 * - 设置页本地状态：用户刚填写、尚未回读时 api_key 为真实值
 */
export function hasConfiguredProvider(
  providers: Record<string, unknown> | null | undefined
): boolean {
  if (!providers || typeof providers !== 'object') return false
  return Object.values(providers).some(provider => {
    if (!provider || typeof provider !== 'object') return false
    const record = provider as Record<string, unknown>
    return isNonEmptyString(record.api_key_masked) || isNonEmptyString(record.api_key)
  })
}

/** 从脱敏配置整体计算配置状态（config 为空视为完全未配置） */
export function getProviderConfigStatus(config: Config | null | undefined): ProviderConfigStatus {
  const textConfigured = hasConfiguredProvider(config?.text_generation?.providers)
  const imageConfigured = hasConfiguredProvider(config?.image_generation?.providers)
  return {
    textConfigured,
    imageConfigured,
    anyConfigured: textConfigured || imageConfigured,
    fullyConfigured: textConfigured && imageConfigured
  }
}

/** 明确属于"认证/权限"类的错误码（前后端 code 体系一致） */
const CONFIG_ERROR_CODES = new Set(['AUTH_OR_PERMISSION'])

/**
 * "未配置服务商/API Key"类错误没有专属 code（后端归为 UNKNOWN_ERROR 或
 * INVALID_REQUEST），只能按文案特征识别。覆盖的后端原始短语示例：
 * - "文本服务商 xxx 未配置 API Key"（backend/utils/llm_utils.py）
 * - "服务商 xxx 未配置 API Key" / "未配置 Base URL"（backend/config.py）
 * - "API Key 未配置"、"请先填写并保存该服务商的 API Key"（config_routes.py）
 * - "无服务商配置" / "激活服务商不存在"
 */
const UNCONFIGURED_PATTERN = new RegExp(
  [
    '(?:服务商|api[_\\s-]?key|base[_\\s-]?url)[^。\\n]{0,24}未配置',
    '未配置[^。\\n]{0,24}(?:服务商|api[_\\s-]?key|base[_\\s-]?url)',
    '无服务商配置',
    '激活的?服务商不存在',
    '请先填写并保存[^。\\n]{0,16}api[_\\s-]?key'
  ].join('|'),
  'i'
)

/**
 * 判断错误是否属于"未配置/认证类"——此类错误应引导用户去设置页，
 * 而不是原地重试
 */
export function isConfigRelatedError(error: AppError | null | undefined): boolean {
  if (!error) return false
  if (CONFIG_ERROR_CODES.has(error.code)) return true
  const text = `${error.title ?? ''}\n${error.detail ?? ''}\n${error.suggestion ?? ''}`
  return UNCONFIGURED_PATTERN.test(text)
}

function isNonEmptyString(value: unknown): boolean {
  return typeof value === 'string' && value.trim() !== ''
}
