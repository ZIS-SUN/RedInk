import { describe, expect, it } from 'vitest'
import type { AnalyticsOcrRow } from '../../../api/analytics'
import { buildOcrImportPayload, toEditableRows } from '../ocrRows'

/** 截图 OCR 预览行转换的纯函数测试（识别行 → 可编辑行 → 批量导入入参） */

function ocrRow(overrides: Partial<AnalyticsOcrRow> = {}): AnalyticsOcrRow {
  return {
    title: '敏感肌自救指南',
    publish_date: '2026-07-01',
    views: 12000,
    likes: 1024,
    collects: 300,
    comments: 56,
    shares: 18,
    followers_gained: 12,
    ...overrides
  }
}

describe('toEditableRows', () => {
  it('数字转为字符串，null 字段转为空串（表示未识别到）', () => {
    const rows = toEditableRows([
      ocrRow({ views: null, publish_date: null, title: null })
    ])

    expect(rows[0].title).toBe('')
    expect(rows[0].publish_date).toBe('')
    expect(rows[0].views).toBe('')
    expect(rows[0].likes).toBe('1024')
    expect(rows[0].followers_gained).toBe('12')
  })

  it('0 是有效值，不能被当成缺失', () => {
    const rows = toEditableRows([ocrRow({ shares: 0 })])
    expect(rows[0].shares).toBe('0')
  })
})

describe('buildOcrImportPayload', () => {
  it('生成带统一平台的批量导入入参，空数字字段不提交', () => {
    const editable = toEditableRows([ocrRow({ comments: null })])
    const { records, errors } = buildOcrImportPayload(editable, '小红书')

    expect(errors).toEqual([])
    expect(records).toHaveLength(1)
    expect(records[0]).toMatchObject({
      title: '敏感肌自救指南',
      platform: '小红书',
      publish_date: '2026-07-01',
      views: 12000,
      likes: 1024
    })
    // 未识别的字段不提交，由后端按默认 0 处理
    expect('comments' in records[0]).toBe(false)
  })

  it('用户手改的「1.2万」「1,024」等写法在提交时被清洗', () => {
    const editable = toEditableRows([ocrRow()])
    editable[0].views = '1.2万'
    editable[0].likes = '1,024'
    const { records } = buildOcrImportPayload(editable, '抖音')

    expect(records[0].views).toBe(12000)
    expect(records[0].likes).toBe(1024)
  })

  it('日期分隔符归一化为 YYYY-MM-DD', () => {
    const editable = toEditableRows([ocrRow()])
    editable[0].publish_date = '2026/7/1'
    const { records } = buildOcrImportPayload(editable, '小红书')
    expect(records[0].publish_date).toBe('2026-07-01')
  })

  it('缺标题的行报错并整体阻止提交（避免静默丢行）', () => {
    const editable = toEditableRows([ocrRow(), ocrRow({ title: null })])
    const { records, errors } = buildOcrImportPayload(editable, '小红书')

    expect(records).toEqual([])
    expect(errors.some(e => e.includes('第 2 行'))).toBe(true)
  })

  it('平台为空时报错', () => {
    const editable = toEditableRows([ocrRow()])
    const { errors } = buildOcrImportPayload(editable, '  ')
    expect(errors.some(e => e.includes('平台'))).toBe(true)
  })
})
