/**
 * 前端本地数据（localStorage）的备份收集与恢复。
 *
 * 后端数据（history/ brand_kits/ 等）由 /api/data/export 打包，
 * 而自定义风格模板、对标拆解历史、水印设置等只存在浏览器 localStorage，
 * 导出备份时由前端收集为 JSON 一并 POST 给后端合入 zip
 * （frontend/local_storage.json）；导入时后端把该 JSON 原样回传，
 * 前端调用 restoreLocalBackup 写回 localStorage。
 *
 * 纯函数 + 可注入 storage，方便单测。
 */
import { ACTIVE_STYLE_STORAGE_KEY, CUSTOM_STYLES_STORAGE_KEY } from '../composables/useStyleLibrary'
import { BENCHMARK_HISTORY_KEY } from './benchmarkHistory'
import { HOTSPOT_LAYER_STORAGE_KEY } from './hotspotLayer'
import { INSIGHT_ARCHIVE_KEY, TOPIC_ARCHIVE_KEY } from './ideaArchive'
import { PATTERN_LIBRARY_KEY } from './patternLibrary'
import { SAFE_ZONE_SETTINGS_KEY } from './safeZone'
import {
  COVER_ARCHIVE_KEY,
  REPLY_ARCHIVE_KEY,
  REWRITE_ARCHIVE_KEY,
  SCRIPT_ARCHIVE_KEY,
  TITLE_ARCHIVE_KEY
} from './toolArchive'
import { WATERMARK_SETTINGS_KEY } from './watermarkSettings'

/** localStorage 的最小接口，便于测试注入 */
export interface BackupStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
  removeItem(key: string): void
}

/**
 * 参与备份的 localStorage key 白名单。
 *
 * 纳入原则：用户长期沉淀的资产/偏好（风格模板、各类存档、历史、导出设置），
 * 键名一律 import 源模块导出的常量，避免字符串字面量漂移。
 * 排除原则：
 * - 凭证类：访问令牌（api/client.ts 的 redink:access-token）备份进 zip 会泄露密钥，
 *   且换环境导入后旧令牌反而失效误导用户；
 * - 一次性传递键：sessionStorage 的 handoff/prefill（如 redink_comment_handoff、
 *   redink_topic_niche_prefill），读后即清，无备份意义；
 * - dismiss 类 UI 状态：横幅关闭标记等会话级提示状态，不属于用户资产。
 *
 * 新增本地持久化资产时在此登记（并同步 localBackup.test.ts 的键集合断言）。
 */
export const LOCAL_BACKUP_KEYS: readonly string[] = [
  // 卡片风格：当前应用的风格 + 用户自定义风格模板（useStyleLibrary）
  ACTIVE_STYLE_STORAGE_KEY,
  CUSTOM_STYLES_STORAGE_KEY,
  // 对标拆解历史（benchmarkHistory）
  BENCHMARK_HISTORY_KEY,
  // 多尺寸导出水印设置（watermarkSettings）
  WATERMARK_SETTINGS_KEY,
  // 导出安全区遮罩显隐设置（safeZone）
  SAFE_ZONE_SETTINGS_KEY,
  // 热点雷达图层开关（hotspotLayer）
  HOTSPOT_LAYER_STORAGE_KEY,
  // 创作现场恢复状态（stores/generator.ts 内部常量 STORAGE_KEY，未导出，字面量对齐）
  'generator-state',
  // 套路模板库（patternLibrary）
  PATTERN_LIBRARY_KEY,
  // 工具结果存档：标题工坊/多平台改写/口播脚本/评论助手/封面 A/B（toolArchive）
  TITLE_ARCHIVE_KEY,
  REWRITE_ARCHIVE_KEY,
  SCRIPT_ARCHIVE_KEY,
  REPLY_ARCHIVE_KEY,
  COVER_ARCHIVE_KEY,
  // 灵感存档：选题灵感 / 评论洞察（ideaArchive）
  TOPIC_ARCHIVE_KEY,
  INSIGHT_ARCHIVE_KEY
]

function defaultStorage(): BackupStorageLike | null {
  return typeof localStorage === 'undefined' ? null : localStorage
}

/**
 * 收集白名单内已有值的 localStorage 键值对。
 * storage 不可用（SSR/隐私模式异常）时返回空对象。
 */
export function collectLocalBackup(
  storage: BackupStorageLike | null = defaultStorage()
): Record<string, string> {
  const result: Record<string, string> = {}
  if (!storage) return result
  for (const key of LOCAL_BACKUP_KEYS) {
    try {
      const value = storage.getItem(key)
      if (value !== null) result[key] = value
    } catch {
      // 单个 key 读取异常不影响其余收集
    }
  }
  return result
}

/**
 * 把备份数据写回 localStorage——白名单全量替换语义。
 *
 * 与后端 core_data 恢复语义对齐（按注册表全量替换：包里没有的资产会被清除）：
 * 遍历 LOCAL_BACKUP_KEYS，备份 payload 中存在（且为字符串）的键写入，
 * 缺席的键从 localStorage 删除——否则用户在源机器上删掉的数据，
 * 导入备份后会在目标机器上"复活"。
 *
 * 白名单之外的键（访问令牌 redink:access-token、handoff/dismiss 键等）
 * 绝不触碰：既不从备份写入（防止导入的 zip 里混入恶意/未知 key
 * 污染本地存储），也不删除。
 *
 * 非对象的 payload 视为无效备份，直接返回 0、不做任何清除。
 *
 * @returns 实际写入的条目数
 */
export function restoreLocalBackup(
  data: unknown,
  storage: BackupStorageLike | null = defaultStorage()
): number {
  if (!storage) return 0
  if (typeof data !== 'object' || data === null || Array.isArray(data)) return 0

  let restored = 0
  const record = data as Record<string, unknown>
  for (const key of LOCAL_BACKUP_KEYS) {
    const value = record[key]
    try {
      if (typeof value === 'string') {
        storage.setItem(key, value)
        restored += 1
      } else {
        storage.removeItem(key)
      }
    } catch {
      // 配额满/不可写时跳过该条，不中断其余恢复
    }
  }
  return restored
}
