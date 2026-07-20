/**
 * 文字卡片工坊 - 可测纯函数
 *
 * 本模块不依赖 DOM / canvas / store，全部为纯函数，
 * 供 cardRender.ts 与 ToolCardStudioView.vue 使用，并在 node 环境下单测。
 */

/** 大纲页解析结果：首行为标题，剩余行为正文 */
export interface ParsedCard {
  title: string
  body: string
}

/**
 * 把一页大纲内容解析成卡片输入：
 * - 第一处非空行作为标题（剥离 markdown 标题符 # 与列表符）
 * - 剩余非空行剥离列表符后按行拼接为正文
 */
export function parseOutlinePageToCard(content: string): ParsedCard {
  const lines = content
    .split(/\r?\n/)
    .map(line => line.trim())
    .filter(line => line.length > 0)

  if (lines.length === 0) return { title: '', body: '' }

  const stripMarkers = (line: string) =>
    line
      .replace(/^#+\s*/, '')
      .replace(/^[-*•]\s+/, '')
      .trim()

  return {
    title: stripMarkers(lines[0]),
    body: lines
      .slice(1)
      .map(stripMarkers)
      .filter(line => line.length > 0)
      .join('\n')
  }
}

/** 解析出的 RGB 颜色（0~255） */
export interface RgbColor {
  r: number
  g: number
  b: number
}

/**
 * 解析 #rgb / #rrggbb 十六进制颜色，非法输入返回 null
 */
export function parseHexColor(hex: string): RgbColor | null {
  const value = hex.trim().replace(/^#/, '')
  if (/^[0-9a-fA-F]{3}$/.test(value)) {
    return {
      r: parseInt(value[0] + value[0], 16),
      g: parseInt(value[1] + value[1], 16),
      b: parseInt(value[2] + value[2], 16)
    }
  }
  if (/^[0-9a-fA-F]{6}$/.test(value)) {
    return {
      r: parseInt(value.slice(0, 2), 16),
      g: parseInt(value.slice(2, 4), 16),
      b: parseInt(value.slice(4, 6), 16)
    }
  }
  return null
}

/**
 * 按底色感知亮度选择文字色：
 * 亮度 = (0.299R + 0.587G + 0.114B) / 255，> 0.6 视为浅底用深字，否则用白字。
 * 非法颜色按浅底处理（返回深字），保证浅色默认主题下依然可读。
 */
export function pickTextColor(bgHex: string): '#fff' | '#1a1a1a' {
  const rgb = parseHexColor(bgHex)
  if (!rgb) return '#1a1a1a'
  const brightness = (0.299 * rgb.r + 0.587 * rgb.g + 0.114 * rgb.b) / 255
  return brightness > 0.6 ? '#1a1a1a' : '#fff'
}

/**
 * 归一化标签输入：按逗号（中英）、顿号、空白拆分，剥离前导 #，去空、按序去重
 */
export function normalizeTags(input: string): string[] {
  const seen = new Set<string>()
  const result: string[] = []
  for (const raw of input.split(/[,，、\s]+/)) {
    const tag = raw.replace(/^#+/, '').trim()
    if (!tag || seen.has(tag)) continue
    seen.add(tag)
    result.push(tag)
  }
  return result
}

/**
 * 单字符宽度估算（以「一个中文字宽」为 1 单位）：
 * CJK 表意字 / 全角标点 / 全角形式按 1，其余（ASCII、半角）按 0.5
 */
export function charUnits(char: string): number {
  const code = char.codePointAt(0) ?? 0
  if (
    (code >= 0x2e80 && code <= 0x9fff) || // CJK 部首、标点、假名、统一表意字
    (code >= 0xf900 && code <= 0xfaff) || // CJK 兼容表意字
    (code >= 0xff00 && code <= 0xff60) || // 全角形式
    code >= 0x20000 // CJK 扩展 B 及以后
  ) {
    return 1
  }
  return 0.5
}

/**
 * 与 ctx 无关的纯换行算法：按估算字宽贪心断行。
 * - maxUnitsPerLine 为每行最大「中文字宽」单位数（中文 1、半角 0.5）
 * - 保留输入中的显式换行；换行产生的新行忽略行首空格
 * - maxUnitsPerLine <= 0 时仅按显式换行拆分
 * - 空字符串返回 []
 */
export function wrapCanvasText(text: string, maxUnitsPerLine: number): string[] {
  if (!text) return []
  const paragraphs = text.split(/\r?\n/)
  if (maxUnitsPerLine <= 0) return paragraphs

  const lines: string[] = []
  for (const paragraph of paragraphs) {
    if (paragraph === '') {
      lines.push('')
      continue
    }
    let current = ''
    let units = 0
    for (const char of paragraph) {
      const width = charUnits(char)
      if (current !== '' && units + width > maxUnitsPerLine) {
        lines.push(current)
        // 折行后的新行不以空格开头
        if (char === ' ') {
          current = ''
          units = 0
        } else {
          current = char
          units = width
        }
      } else {
        current += char
        units += width
      }
    }
    if (current !== '') lines.push(current)
  }
  return lines
}
