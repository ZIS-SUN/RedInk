/**
 * 文字卡片工坊 - Canvas 绘制（1080 x 1440，3:4）
 *
 * 绘制函数只依赖传入的 ctx 与配置，不读取 DOM / store / 全局状态，
 * 预览画布与导出用的离屏画布走同一套绘制逻辑，保证导出即所得。
 */
import { parseHexColor, pickTextColor, wrapCanvasText } from './cardStudio'

export const CARD_WIDTH = 1080
export const CARD_HEIGHT = 1440

const PADDING = 96
const CONTENT_WIDTH = CARD_WIDTH - PADDING * 2

const FONT_STACK =
  '-apple-system, BlinkMacSystemFont, "PingFang SC", "Hiragino Sans GB", "Microsoft YaHei", sans-serif'
const QUOTE_FONT_STACK = 'Georgia, "Songti SC", STSong, serif'

/** 三款模板 */
export type CardTemplateId = 'poster' | 'list' | 'quote'

/** 字号档位 */
export type FontScaleId = 'small' | 'normal' | 'large'

export const FONT_SCALE_VALUES: Record<FontScaleId, number> = {
  small: 0.88,
  normal: 1,
  large: 1.14
}

/** 配色主题：bg 底色 + accent 强调色，文字色按底色亮度自动选黑/白 */
export interface CardTheme {
  id: string
  name: string
  bg: string
  accent: string
}

/** 内置 5 组预设主题（浅底深字 / 深底白字均保证对比度） */
export const PRESET_THEMES: CardTheme[] = [
  { id: 'cream', name: '奶油纸感', bg: '#F7F1E5', accent: '#C75C2E' },
  { id: 'sunset', name: '落日暖橙', bg: '#E8622C', accent: '#FFE3CC' },
  { id: 'forest', name: '墨绿信笺', bg: '#1E3A2F', accent: '#CBB57B' },
  { id: 'noir', name: '黑金夜航', bg: '#171412', accent: '#D4AF37' },
  { id: 'rednote', name: '红白经典', bg: '#FFFFFF', accent: '#EF2A45' }
]

/** 单张卡片的完整渲染配置 */
export interface CardRenderConfig {
  template: CardTemplateId
  title: string
  /** 多行正文（\n 分隔；清单卡按行拆条目，金句卡整体为金句） */
  body: string
  /** 已归一化的标签（不含 #） */
  tags: string[]
  /** 署名 / 页脚，空字符串表示不绘制 */
  footer: string
  theme: CardTheme
  fontScale: FontScaleId
  bold: boolean
}

/* ---------------- 内部工具 ---------------- */

interface Palette {
  bg: string
  text: string
  subText: string
  faintText: string
  accent: string
  accentText: string
}

function withAlpha(hex: string, alpha: number): string {
  const rgb = parseHexColor(hex)
  if (!rgb) return hex
  return `rgba(${rgb.r}, ${rgb.g}, ${rgb.b}, ${alpha})`
}

function buildPalette(theme: CardTheme): Palette {
  const text = pickTextColor(theme.bg)
  return {
    bg: theme.bg,
    text,
    subText: withAlpha(text, 0.72),
    faintText: withAlpha(text, 0.45),
    accent: theme.accent,
    accentText: pickTextColor(theme.accent)
  }
}

function setFont(
  ctx: CanvasRenderingContext2D,
  size: number,
  weight: number,
  family: string = FONT_STACK
) {
  ctx.font = `${weight} ${Math.round(size)}px ${family}`
}

/** 每行可容纳的「中文字宽」单位数（半角字符按 0.5 计） */
function maxUnits(fontSize: number, width: number = CONTENT_WIDTH): number {
  return Math.max(1, Math.floor(width / fontSize))
}

/** 超过 max 行时截断并在末行加省略号 */
function clampLines(lines: string[], max: number): string[] {
  if (lines.length <= max) return lines
  const kept = lines.slice(0, max)
  kept[max - 1] = `${kept[max - 1]}…`
  return kept
}

interface TagsRowOptions {
  y: number
  size: number
  align: 'center' | 'left'
  maxWidth: number
  color: string
}

/** 绘制一行 #tag 标签，超出可用宽度的标签直接省略 */
function drawTagsRow(
  ctx: CanvasRenderingContext2D,
  tags: string[],
  options: TagsRowOptions
) {
  if (tags.length === 0) return
  const { y, size, align, maxWidth, color } = options
  setFont(ctx, size, 600)
  const gap = size * 0.9

  const kept: string[] = []
  const widths: number[] = []
  let total = 0
  for (const tag of tags) {
    const label = `#${tag}`
    const width = ctx.measureText(label).width
    const extra = kept.length === 0 ? width : width + gap
    if (total + extra > maxWidth) break
    kept.push(label)
    widths.push(width)
    total += extra
  }
  if (kept.length === 0) return

  let x = align === 'center' ? (CARD_WIDTH - total) / 2 : PADDING
  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = color
  kept.forEach((label, i) => {
    ctx.fillText(label, x, y)
    x += widths[i] + gap
  })
}

/* ---------------- 模板：大字报 ---------------- */

function drawPoster(
  ctx: CanvasRenderingContext2D,
  config: CardRenderConfig,
  palette: Palette,
  scale: number
) {
  const titleSize = 96 * scale
  const titleLineHeight = titleSize * 1.3
  const titleLines = clampLines(
    wrapCanvasText(config.title || '在左侧输入标题', maxUnits(titleSize)),
    4
  )

  const subSize = 40 * scale
  const subLineHeight = subSize * 1.7
  const subLines = clampLines(wrapCanvasText(config.body, maxUnits(subSize)), 5)

  const barHeight = 12
  const gapBarTitle = 64
  const gapTitleSub = subLines.length > 0 ? 64 : 0
  const blockHeight =
    barHeight +
    gapBarTitle +
    titleLines.length * titleLineHeight +
    gapTitleSub +
    subLines.length * subLineHeight

  // 整块略偏上，给底部标签行留出呼吸空间
  let y = Math.max(PADDING, (CARD_HEIGHT - blockHeight) / 2 - 48)

  // 标题上方的强调短条
  const barWidth = 88
  ctx.fillStyle = palette.accent
  ctx.fillRect((CARD_WIDTH - barWidth) / 2, y, barWidth, barHeight)
  y += barHeight + gapBarTitle

  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = palette.text
  setFont(ctx, titleSize, config.bold ? 800 : 700)
  for (const line of titleLines) {
    ctx.fillText(line, CARD_WIDTH / 2, y + titleLineHeight / 2)
    y += titleLineHeight
  }

  if (subLines.length > 0) {
    y += gapTitleSub
    ctx.fillStyle = palette.subText
    setFont(ctx, subSize, config.bold ? 500 : 400)
    for (const line of subLines) {
      ctx.fillText(line, CARD_WIDTH / 2, y + subLineHeight / 2)
      y += subLineHeight
    }
  }

  drawTagsRow(ctx, config.tags, {
    y: CARD_HEIGHT - 150,
    size: 34 * scale,
    align: 'center',
    maxWidth: CONTENT_WIDTH,
    color: palette.accent
  })

  if (config.footer) {
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = palette.faintText
    setFont(ctx, 28 * scale, 500)
    ctx.fillText(config.footer, CARD_WIDTH / 2, CARD_HEIGHT - 84)
  }
}

/* ---------------- 模板：清单卡 ---------------- */

function drawList(
  ctx: CanvasRenderingContext2D,
  config: CardRenderConfig,
  palette: Palette,
  scale: number
) {
  let y = PADDING + 16

  // 标题 + 左侧强调条
  const titleSize = 64 * scale
  const titleLineHeight = titleSize * 1.35
  const barWidth = 12
  const titleX = PADDING + barWidth + 32
  const titleLines = clampLines(
    wrapCanvasText(config.title || '清单标题', maxUnits(titleSize, CARD_WIDTH - PADDING - titleX)),
    2
  )

  ctx.fillStyle = palette.accent
  ctx.fillRect(PADDING, y + titleLineHeight * 0.12, barWidth, titleLines.length * titleLineHeight * 0.76)

  ctx.textAlign = 'left'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = palette.text
  setFont(ctx, titleSize, config.bold ? 800 : 700)
  for (const line of titleLines) {
    ctx.fillText(line, titleX, y + titleLineHeight / 2)
    y += titleLineHeight
  }

  // 分隔线
  y += 40
  ctx.fillStyle = withAlpha(palette.text, 0.12)
  ctx.fillRect(PADDING, y, CONTENT_WIDTH, 2)
  y += 60

  // 条目：正文按行拆分，每条前画序号圆片
  const items = config.body
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
    .slice(0, 8)

  const itemSize = 38 * scale
  const itemLineHeight = itemSize * 1.55
  const chipRadius = 27 * scale
  const textX = PADDING + chipRadius * 2 + 32
  const textWidth = CARD_WIDTH - PADDING - textX
  const bottomLimit = CARD_HEIGHT - 220

  for (let i = 0; i < items.length; i++) {
    if (y + itemLineHeight > bottomLimit) break
    const lines = clampLines(wrapCanvasText(items[i], maxUnits(itemSize, textWidth)), 3)

    // 序号圆片
    ctx.fillStyle = palette.accent
    ctx.beginPath()
    ctx.arc(PADDING + chipRadius, y + itemLineHeight / 2, chipRadius, 0, Math.PI * 2)
    ctx.fill()
    ctx.fillStyle = palette.accentText
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    setFont(ctx, 27 * scale, 700)
    ctx.fillText(String(i + 1), PADDING + chipRadius, y + itemLineHeight / 2 + 1)

    // 条目文本
    ctx.textAlign = 'left'
    ctx.fillStyle = palette.text
    setFont(ctx, itemSize, config.bold ? 600 : 400)
    for (const line of lines) {
      ctx.fillText(line, textX, y + itemLineHeight / 2)
      y += itemLineHeight
    }
    y += 28
  }

  drawTagsRow(ctx, config.tags, {
    y: CARD_HEIGHT - 148,
    size: 32 * scale,
    align: 'left',
    maxWidth: CONTENT_WIDTH,
    color: palette.accent
  })

  if (config.footer) {
    ctx.textAlign = 'left'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = palette.faintText
    setFont(ctx, 28 * scale, 500)
    ctx.fillText(config.footer, PADDING, CARD_HEIGHT - 84)
  }
}

/* ---------------- 模板：金句卡 ---------------- */

function drawQuote(
  ctx: CanvasRenderingContext2D,
  config: CardRenderConfig,
  palette: Palette,
  scale: number
) {
  // 金句取正文，正文为空时退回标题
  const quoteText = config.body.trim() || config.title || '写下你的金句'

  // 左上大引号 + 右下小引号装饰
  ctx.fillStyle = withAlpha(palette.accent, 0.9)
  ctx.textAlign = 'left'
  ctx.textBaseline = 'alphabetic'
  setFont(ctx, 280 * scale, 700, QUOTE_FONT_STACK)
  ctx.fillText('\u201C', PADDING - 16, PADDING + 200 * scale)

  ctx.fillStyle = withAlpha(palette.accent, 0.5)
  ctx.textAlign = 'right'
  setFont(ctx, 180 * scale, 700, QUOTE_FONT_STACK)
  ctx.fillText('\u201D', CARD_WIDTH - PADDING + 16, CARD_HEIGHT - PADDING + 20)

  // 居中金句
  const quoteSize = 62 * scale
  const lineHeight = quoteSize * 1.8
  const lines = clampLines(
    wrapCanvasText(quoteText, maxUnits(quoteSize, CONTENT_WIDTH - 40)),
    8
  )
  const blockHeight = lines.length * lineHeight
  let y = Math.max(PADDING + 200, (CARD_HEIGHT - blockHeight) / 2 - 20)

  ctx.textAlign = 'center'
  ctx.textBaseline = 'middle'
  ctx.fillStyle = palette.text
  setFont(ctx, quoteSize, config.bold ? 700 : 500)
  for (const line of lines) {
    ctx.fillText(line, CARD_WIDTH / 2, y + lineHeight / 2)
    y += lineHeight
  }

  // 金句下的强调短线
  y += 52
  ctx.fillStyle = palette.accent
  ctx.fillRect((CARD_WIDTH - 64) / 2, y, 64, 6)
  y += 6

  // 署名行
  if (config.footer) {
    y += 56
    ctx.textAlign = 'center'
    ctx.textBaseline = 'middle'
    ctx.fillStyle = palette.subText
    setFont(ctx, 36 * scale, 500)
    ctx.fillText(`\u2014\u2014 ${config.footer}`, CARD_WIDTH / 2, y)
  }

  drawTagsRow(ctx, config.tags, {
    y: CARD_HEIGHT - 120,
    size: 30 * scale,
    align: 'center',
    maxWidth: CONTENT_WIDTH,
    color: withAlpha(palette.accent, 0.85)
  })
}

/* ---------------- 入口 ---------------- */

/**
 * 把一张卡片绘制到 1080x1440 的 canvas 上下文
 * （调用方保证 ctx 所属 canvas 尺寸为 CARD_WIDTH x CARD_HEIGHT）
 */
export function renderCard(ctx: CanvasRenderingContext2D, config: CardRenderConfig): void {
  const palette = buildPalette(config.theme)
  const scale = FONT_SCALE_VALUES[config.fontScale]

  ctx.save()
  ctx.clearRect(0, 0, CARD_WIDTH, CARD_HEIGHT)
  ctx.fillStyle = palette.bg
  ctx.fillRect(0, 0, CARD_WIDTH, CARD_HEIGHT)

  if (config.template === 'list') {
    drawList(ctx, config, palette, scale)
  } else if (config.template === 'quote') {
    drawQuote(ctx, config, palette, scale)
  } else {
    drawPoster(ctx, config, palette, scale)
  }
  ctx.restore()
}
