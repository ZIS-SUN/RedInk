/**
 * 数据管理中心 API：一键备份导出 / 导入恢复 / 诊断包导出
 */
import { http } from './client'
import type { AppError } from '../utils/errors'

/** 备份/诊断包下载与导入的超时：数据量可能较大，放宽到 5 分钟 */
const DATA_TRANSFER_TIMEOUT = 300_000

/** POST /data/import 响应摘要 */
export interface ImportBackupResult {
  success: boolean
  /** 备份包 manifest 摘要 */
  manifest?: {
    version?: string
    exported_at?: string
    include_keys?: boolean
  }
  /** 恢复的顶层条目（history / brand_kits / ...） */
  restored?: string[]
  /** 忽略的未知条目 */
  skipped?: string[]
  /** 覆盖前自动备份目录名（位于数据根目录下） */
  pre_import_backup?: string
  /** 备份包内的前端 localStorage 数据，由前端负责写回 */
  local_storage?: Record<string, string> | null
  error?: AppError | string
  error_message?: string
}

/**
 * 导出全量数据备份 zip。
 *
 * @param includeKeys 是否包含 providers 配置（含 API Key 明文）
 * @param localStorageData 前端收集的 localStorage 键值，合入 zip
 */
export async function exportBackup(
  includeKeys: boolean,
  localStorageData: Record<string, string>
): Promise<Blob> {
  const response = await http.post<Blob>(
    '/data/export',
    { local_storage: localStorageData },
    {
      params: includeKeys ? { include_keys: 'true' } : {},
      responseType: 'blob',
      timeout: DATA_TRANSFER_TIMEOUT
    }
  )
  return response.data
}

/** 导入备份 zip 恢复数据（服务端会先自动备份现有数据再覆盖） */
export async function importBackup(file: File): Promise<ImportBackupResult> {
  const form = new FormData()
  form.append('file', file)
  const response = await http.post<ImportBackupResult>('/data/import', form, {
    timeout: DATA_TRANSFER_TIMEOUT
  })
  return response.data
}

/** 导出诊断包 zip（日志 + 版本/平台信息 + 脱敏配置，不含 API Key） */
export async function exportDiagnostics(): Promise<Blob> {
  const response = await http.get<Blob>('/data/diagnostics', {
    responseType: 'blob',
    timeout: DATA_TRANSFER_TIMEOUT
  })
  return response.data
}

/** 触发浏览器下载 Blob */
export function downloadBlob(blob: Blob, filename: string): void {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  URL.revokeObjectURL(url)
}
