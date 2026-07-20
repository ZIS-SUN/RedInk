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

/** localStorage 的最小接口，便于测试注入 */
export interface BackupStorageLike {
  getItem(key: string): string | null
  setItem(key: string, value: string): void
}

/**
 * 参与备份的 localStorage key 白名单。
 * 新增本地持久化数据时在此登记即可纳入备份。
 */
export const LOCAL_BACKUP_KEYS: readonly string[] = [
  // 卡片风格：当前应用的风格 + 用户自定义风格模板（useStyleLibrary）
  'redink_active_style',
  'redink_custom_styles',
  // 对标拆解历史（benchmarkHistory）
  'redink_benchmark_history',
  // 多尺寸导出水印设置（watermarkSettings）
  'redink_export_watermark',
  // 热点雷达图层开关（hotspotLayer）
  'redink_hotspot_layer_enabled',
  // 创作现场恢复状态（generator store）
  'generator-state'
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
 * 把备份数据写回 localStorage。
 *
 * 只恢复白名单内、值为字符串的条目（防止导入的 zip 里
 * 混入恶意/未知 key 污染本地存储）。
 *
 * @returns 实际恢复的条目数
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
    if (typeof value !== 'string') continue
    try {
      storage.setItem(key, value)
      restored += 1
    } catch {
      // 配额满/不可写时跳过该条，不中断其余恢复
    }
  }
  return restored
}
