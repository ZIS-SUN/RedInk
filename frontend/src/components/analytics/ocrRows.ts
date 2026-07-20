import type { AnalyticsOcrRow, AnalyticsRecordInput } from '../../api/analytics'
import { cleanNumber, normalizeDate } from '../../utils/analyticsImport'

/**
 * 截图 OCR 识别结果 → 可编辑预览行 → 批量导入入参 的纯函数转换
 * （从 OcrImportModal 中拆出便于单元测试，无副作用）
 *
 * 设计约定：
 * - 预览行的所有字段用字符串承载（数字字段空串 = 识别失败/未填写），
 *   直接绑定表格里的 input，用户可自由修改
 * - 提交时数字走 cleanNumber 清洗（兼容用户手改成「1.2万」的写法），
 *   空串字段不提交（后端按默认 0 处理）
 */

/** 预览表格中的一行（全部字段可编辑） */
export interface EditableOcrRow {
  title: string
  publish_date: string
  views: string
  likes: string
  collects: string
  comments: string
  shares: string
  followers_gained: string
}

/** 数字字段清单（与 AnalyticsRecordInput 的整型字段一致） */
export const OCR_NUMBER_FIELDS = [
  'views',
  'likes',
  'collects',
  'comments',
  'shares',
  'followers_gained'
] as const

export type OcrNumberField = (typeof OCR_NUMBER_FIELDS)[number]

/** 把后端识别行（字段可能为 null）转成可编辑字符串行 */
export function toEditableRows(rows: AnalyticsOcrRow[]): EditableOcrRow[] {
  return rows.map(row => ({
    title: row.title ?? '',
    publish_date: row.publish_date ?? '',
    views: row.views == null ? '' : String(row.views),
    likes: row.likes == null ? '' : String(row.likes),
    collects: row.collects == null ? '' : String(row.collects),
    comments: row.comments == null ? '' : String(row.comments),
    shares: row.shares == null ? '' : String(row.shares),
    followers_gained: row.followers_gained == null ? '' : String(row.followers_gained)
  }))
}

export interface OcrPayloadResult {
  /** 可直接提交批量创建接口的记录 */
  records: AnalyticsRecordInput[]
  /** 行级校验错误（如缺标题），提示后阻止提交 */
  errors: string[]
}

/**
 * 把编辑后的预览行转成批量创建入参（统一套用所选平台）。
 * 标题为空的行报错并整体阻止提交，避免静默丢行。
 */
export function buildOcrImportPayload(rows: EditableOcrRow[], platform: string): OcrPayloadResult {
  const records: AnalyticsRecordInput[] = []
  const errors: string[] = []
  const platformText = platform.trim()
  if (!platformText) {
    errors.push('请先选择发布平台')
  }

  rows.forEach((row, index) => {
    const title = row.title.trim()
    if (!title) {
      errors.push(`第 ${index + 1} 行缺少标题，请补全或删除该行`)
      return
    }

    const record: AnalyticsRecordInput = { title, platform: platformText }
    if (row.publish_date.trim()) {
      record.publish_date = normalizeDate(row.publish_date)
    }
    for (const field of OCR_NUMBER_FIELDS) {
      const raw = row[field].trim()
      if (raw !== '') {
        record[field] = cleanNumber(raw)
      }
    }
    records.push(record)
  })

  return { records: errors.length ? [] : records, errors }
}
