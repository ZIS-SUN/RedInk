import type { AnalyticsRecordInput } from '../api/analytics'

/**
 * 数据复盘「批量导入」的粘贴文本解析（纯函数，无副作用）
 *
 * 支持两种格式自动识别：
 * - 制表符分隔（从 Excel / 创作者中心表格直接复制）
 * - CSV 逗号分隔（支持双引号包裹的单元格）
 *
 * 首行为表头，宽松匹配中文表头别名（见 HEADER_ALIASES）；
 * 数字自动清洗（去千分位逗号、"1.2万" -> 12000）；
 * 空行跳过；无法解析的行收集到 errors（不中断整体解析）。
 */

/** 单行解析失败信息（line 为粘贴文本中 1 起的行号） */
export interface ImportRowError {
  line: number
  reason: string
}

export interface ImportParseResult {
  /** 解析成功、可直接提交批量接口的记录 */
  records: AnalyticsRecordInput[]
  /** 无法解析的行 */
  errors: ImportRowError[]
  /** 识别出的分隔符 */
  delimiter: 'tab' | 'comma'
  /** 表头各列被映射到的字段名（null 表示该列被忽略） */
  headerFields: (keyof AnalyticsRecordInput | null)[]
}

/** 表头别名 -> 记录字段（按声明顺序做"包含"匹配，先精确后模糊） */
const HEADER_ALIASES: Array<[keyof AnalyticsRecordInput, string[]]> = [
  ['title', ['标题', '内容标题', '作品标题', 'title']],
  ['platform', ['平台', '发布平台', 'platform']],
  // 注意顺序：「发布时间」必须先于「日期」检查，避免被"发布"前缀干扰
  ['publish_time', ['发布时间', '时间', 'time']],
  ['publish_date', ['日期', '发布日期', 'date']],
  ['content_type', ['类型', '内容类型', '标签', '分类']],
  ['views', ['曝光', '播放', '阅读', 'views']],
  ['likes', ['点赞', 'likes']],
  ['collects', ['收藏', 'collects']],
  ['comments', ['评论', 'comments']],
  ['shares', ['转发', '分享', 'shares']],
  ['followers_gained', ['涨粉', '新增粉丝', 'followers']],
  ['notes', ['备注', 'notes']]
]

const INT_FIELDS: ReadonlySet<keyof AnalyticsRecordInput> = new Set([
  'views',
  'likes',
  'collects',
  'comments',
  'shares',
  'followers_gained'
])

/** 表头单元格归一化：去空白、去全/半角括号内容、去星号、转小写 */
function normalizeHeaderCell(cell: string): string {
  return cell
    .replace(/[（(][^）)]*[）)]/g, '')
    .replace(/[\s*＊]/g, '')
    .toLowerCase()
}

/**
 * 宽松匹配单个表头单元格到记录字段；无法识别返回 null（该列被忽略）
 */
export function matchHeaderField(cell: string): keyof AnalyticsRecordInput | null {
  const text = normalizeHeaderCell(cell)
  if (!text) return null
  // 先精确命中别名
  for (const [field, aliases] of HEADER_ALIASES) {
    if (aliases.some(alias => text === alias.toLowerCase())) return field
  }
  // 再做包含匹配（如"曝光量(次)" -> views）
  for (const [field, aliases] of HEADER_ALIASES) {
    if (aliases.some(alias => text.includes(alias.toLowerCase()))) return field
  }
  return null
}

/**
 * 数字清洗：去千分位逗号 / 空格 / 加号，"1.2万" -> 12000，"3w" -> 30000。
 * 空值或无法解析时返回 0（与后端 _normalize_int 的宽松语义一致）。
 */
export function cleanNumber(raw: string): number {
  const text = String(raw ?? '')
    .replace(/[,，\s+]/g, '')
    .trim()
  if (!text) return 0

  let multiplier = 1
  let numberText = text
  if (/[万wW]$/.test(text)) {
    multiplier = 10000
    numberText = text.slice(0, -1)
  } else if (/亿$/.test(text)) {
    multiplier = 100000000
    numberText = text.slice(0, -1)
  }

  const value = Number(numberText)
  if (!Number.isFinite(value) || value < 0) return 0
  return Math.round(value * multiplier)
}

/** 日期归一化："2026/7/1"、"2026.07.01" -> "2026-07-01"；无法识别时原样返回（后端宽松存储） */
export function normalizeDate(raw: string): string {
  const text = String(raw ?? '').trim()
  const match = text.replace(/[/.．]/g, '-').match(/^(\d{4})-(\d{1,2})-(\d{1,2})/)
  if (!match) return text
  const [, year, month, day] = match
  return `${year}-${month.padStart(2, '0')}-${day.padStart(2, '0')}`
}

/** 时间归一化："21：30"、"8点05" -> "HH:MM"；无法识别返回空串（视为未填写，避免整行失败） */
export function normalizeTime(raw: string): string {
  const text = String(raw ?? '').trim()
  if (!text) return ''
  const match = text.match(/^(\d{1,2})[:：点时.](\d{1,2})/)
  if (!match) return ''
  const hour = Number(match[1])
  const minute = Number(match[2])
  if (hour > 23 || minute > 59) return ''
  return `${String(hour).padStart(2, '0')}:${String(minute).padStart(2, '0')}`
}

/** CSV 行拆分（支持双引号包裹与 "" 转义） */
function splitCsvLine(line: string): string[] {
  const cells: string[] = []
  let current = ''
  let inQuotes = false
  for (let i = 0; i < line.length; i++) {
    const ch = line[i]
    if (inQuotes) {
      if (ch === '"') {
        if (line[i + 1] === '"') {
          current += '"'
          i++
        } else {
          inQuotes = false
        }
      } else {
        current += ch
      }
    } else if (ch === '"') {
      inQuotes = true
    } else if (ch === ',') {
      cells.push(current)
      current = ''
    } else {
      current += ch
    }
  }
  cells.push(current)
  return cells
}

function splitLine(line: string, delimiter: 'tab' | 'comma'): string[] {
  return delimiter === 'tab' ? line.split('\t') : splitCsvLine(line)
}

/**
 * 解析粘贴的表格文本
 *
 * @param text 粘贴的原始文本（首个非空行为表头）
 * @returns 解析结果；表头缺少"标题/平台"列时 records 为空、errors 含表头错误
 */
export function parseAnalyticsImport(text: string): ImportParseResult {
  const lines = String(text ?? '').split(/\r\n|\r|\n/)

  // 找到首个非空行作为表头
  let headerIndex = -1
  for (let i = 0; i < lines.length; i++) {
    if (lines[i].trim()) {
      headerIndex = i
      break
    }
  }

  if (headerIndex === -1) {
    return { records: [], errors: [], delimiter: 'tab', headerFields: [] }
  }

  const headerLine = lines[headerIndex]
  const delimiter: 'tab' | 'comma' = headerLine.includes('\t') ? 'tab' : 'comma'
  const headerFields = splitLine(headerLine, delimiter).map(matchHeaderField)

  const errors: ImportRowError[] = []
  const records: AnalyticsRecordInput[] = []

  const hasTitle = headerFields.includes('title')
  const hasPlatform = headerFields.includes('platform')
  if (!hasTitle || !hasPlatform) {
    const missing = [!hasTitle ? '标题' : '', !hasPlatform ? '平台' : ''].filter(Boolean).join('、')
    errors.push({
      line: headerIndex + 1,
      reason: `表头缺少必需列：${missing}（支持的表头如：标题 / 平台 / 日期 / 发布时间 / 类型 / 曝光 / 点赞 / 收藏 / 评论 / 转发 / 涨粉）`
    })
    return { records, errors, delimiter, headerFields }
  }

  for (let i = headerIndex + 1; i < lines.length; i++) {
    const line = lines[i]
    if (!line.trim()) continue // 空行跳过

    const cells = splitLine(line, delimiter)
    const raw: Partial<Record<keyof AnalyticsRecordInput, string>> = {}
    headerFields.forEach((field, col) => {
      if (field && raw[field] === undefined) {
        raw[field] = (cells[col] ?? '').trim()
      }
    })

    const title = (raw.title ?? '').trim()
    const platform = (raw.platform ?? '').trim()
    if (!title || !platform) {
      const missing = [!title ? '标题' : '', !platform ? '平台' : ''].filter(Boolean).join('、')
      errors.push({ line: i + 1, reason: `缺少${missing}` })
      continue
    }

    const record: AnalyticsRecordInput = { title, platform }
    if (raw.publish_date !== undefined) record.publish_date = normalizeDate(raw.publish_date)
    if (raw.publish_time !== undefined) record.publish_time = normalizeTime(raw.publish_time)
    if (raw.content_type !== undefined) record.content_type = raw.content_type
    if (raw.notes !== undefined) record.notes = raw.notes
    for (const field of INT_FIELDS) {
      const value = raw[field]
      if (value !== undefined) {
        ;(record as Record<string, unknown>)[field] = cleanNumber(value)
      }
    }
    records.push(record)
  }

  return { records, errors, delimiter, headerFields }
}
