/**
 * 多尺寸导出核心工具（纯前端 Canvas 实现）
 *
 * 职责：
 * - 提供各平台预设尺寸（小红书 / 方形 / 抖音竖版 / 公众号头图 / B站封面）
 * - 纯函数计算 contain / cover 布局矩形（可在 node 环境单测）
 * - 将图片渲染到目标尺寸 canvas：留白（纯色 / 原图高斯模糊铺底）或裁切填满
 * - 可选文字水印（五种位置，默认右下角，向后兼容旧调用）
 * - 导出 PNG Blob 与触发浏览器下载
 *
 * 注意：本模块不依赖任何 store / api，调用方在运行时传入图片地址即可。
 * 同源图片（/api/images/...）可直接 drawImage；跨域地址会尝试
 * crossOrigin='anonymous' 加载并在失败时回退，避免 canvas 被污染导致导出失败。
 */

/** 适配策略：contain-完整显示留白，cover-裁切填满 */
export type FitMode = 'contain' | 'cover'

/** contain 模式下的留白背景 */
export type BackgroundOption =
  | { type: 'color'; color: string }
  | { type: 'blur'; blurRadius?: number }

/** 水印位置（五选一） */
export type WatermarkPosition =
  | 'top-left'
  | 'top-right'
  | 'bottom-left'
  | 'bottom-right'
  | 'bottom-center'

/** 水印配置（文字水印，默认右下角） */
export interface WatermarkOptions {
  text: string
  /** 字号（px），默认按画布宽度自适应；显式指定时优先于 sizeRatio */
  fontSize?: number
  /** 透明度 0~1，默认 0.5 */
  opacity?: number
  /** 颜色，默认白色（带深色描影保证可读） */
  color?: string
  /** 距边缘边距（px），默认 = 字号 */
  margin?: number
  /** 位置，默认 'bottom-right'（保持原行为） */
  position?: WatermarkPosition
  /** 字号占画布宽度比例（如 0.035 = 3.5%），fontSize 未指定时生效 */
  sizeRatio?: number
  /** 是否绘制深色描影（浅色水印建议开启），默认 true（保持原行为） */
  shadow?: boolean
}

/** 单次导出参数 */
export interface ExportRenderOptions {
  width: number
  height: number
  fit: FitMode
  /** 仅 contain 模式生效，默认白色背景 */
  background?: BackgroundOption
  watermark?: WatermarkOptions
}

/** 平台尺寸预设 */
export interface SizePreset {
  id: string
  /** 中文名称，用于 UI 展示 */
  label: string
  /** 比例描述，如 3:4 */
  ratio: string
  width: number
  height: number
}

/** 内置平台预设尺寸 */
export const SIZE_PRESETS: SizePreset[] = [
  { id: 'xhs-3-4', label: '小红书', ratio: '3:4', width: 1080, height: 1440 },
  { id: 'square-1-1', label: '方形', ratio: '1:1', width: 1080, height: 1080 },
  { id: 'douyin-9-16', label: '抖音/视频号竖版', ratio: '9:16', width: 1080, height: 1920 },
  { id: 'mp-banner', label: '公众号头图', ratio: '2.35:1', width: 900, height: 383 },
  { id: 'bili-cover', label: 'B站封面', ratio: '16:9', width: 1146, height: 717 }
]

/** 布局矩形（目标画布坐标系） */
export interface LayoutRect {
  x: number
  y: number
  width: number
  height: number
}

/**
 * contain 布局：图片完整显示、居中，短边方向留白
 * 纯函数，便于单测
 */
export function computeContainRect(
  srcWidth: number,
  srcHeight: number,
  dstWidth: number,
  dstHeight: number
): LayoutRect {
  if (srcWidth <= 0 || srcHeight <= 0 || dstWidth <= 0 || dstHeight <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 }
  }
  const scale = Math.min(dstWidth / srcWidth, dstHeight / srcHeight)
  const width = Math.round(srcWidth * scale)
  const height = Math.round(srcHeight * scale)
  return {
    x: Math.round((dstWidth - width) / 2),
    y: Math.round((dstHeight - height) / 2),
    width,
    height
  }
}

/**
 * cover 布局：图片放大到铺满画布、居中，超出部分被画布裁掉
 * 返回的矩形可能超出画布（x/y 为负），配合 drawImage 直接绘制即可
 * 纯函数，便于单测
 */
export function computeCoverRect(
  srcWidth: number,
  srcHeight: number,
  dstWidth: number,
  dstHeight: number
): LayoutRect {
  if (srcWidth <= 0 || srcHeight <= 0 || dstWidth <= 0 || dstHeight <= 0) {
    return { x: 0, y: 0, width: 0, height: 0 }
  }
  const scale = Math.max(dstWidth / srcWidth, dstHeight / srcHeight)
  const width = Math.round(srcWidth * scale)
  const height = Math.round(srcHeight * scale)
  return {
    x: Math.round((dstWidth - width) / 2),
    y: Math.round((dstHeight - height) / 2),
    width,
    height
  }
}

/** 默认水印字号：按画布宽度自适应，限制在 14~64px */
export function computeDefaultWatermarkFontSize(canvasWidth: number): number {
  return Math.min(64, Math.max(14, Math.round(canvasWidth * 0.03)))
}

/** 按占宽比例计算水印字号（小/中/大 ≈ 2.5%/3.5%/5%），限制在 12~160px */
export function computeWatermarkFontSize(canvasWidth: number, ratio: number): number {
  return Math.min(160, Math.max(12, Math.round(canvasWidth * ratio)))
}

/** 水印锚点：坐标 + 文字对齐方式（纯函数，便于单测） */
export interface WatermarkAnchor {
  x: number
  y: number
  textAlign: CanvasTextAlign
  textBaseline: CanvasTextBaseline
}

/** 按位置计算水印锚点，默认右下角 */
export function computeWatermarkAnchor(
  position: WatermarkPosition,
  dstWidth: number,
  dstHeight: number,
  margin: number
): WatermarkAnchor {
  switch (position) {
    case 'top-left':
      return { x: margin, y: margin, textAlign: 'left', textBaseline: 'top' }
    case 'top-right':
      return { x: dstWidth - margin, y: margin, textAlign: 'right', textBaseline: 'top' }
    case 'bottom-left':
      return { x: margin, y: dstHeight - margin, textAlign: 'left', textBaseline: 'bottom' }
    case 'bottom-center':
      return {
        x: Math.round(dstWidth / 2),
        y: dstHeight - margin,
        textAlign: 'center',
        textBaseline: 'bottom'
      }
    case 'bottom-right':
    default:
      return { x: dstWidth - margin, y: dstHeight - margin, textAlign: 'right', textBaseline: 'bottom' }
  }
}

/** 高斯模糊铺底的默认模糊半径：按画布短边自适应 */
export function computeDefaultBlurRadius(dstWidth: number, dstHeight: number): number {
  return Math.min(60, Math.max(16, Math.round(Math.min(dstWidth, dstHeight) * 0.03)))
}

/**
 * 生成导出文件名，如 rednote_封面_1080x1920.png
 * 会剔除文件名中的非法字符
 */
export function buildExportFilename(
  sourceName: string,
  preset: Pick<SizePreset, 'width' | 'height'>
): string {
  const safe = sourceName
    .replace(/\.[a-zA-Z0-9]+$/, '') // 去掉扩展名
    .replace(/[\\/:*?"<>|\s]+/g, '_')
    .slice(0, 60) || 'image'
  return `${safe}_${preset.width}x${preset.height}.png`
}

/**
 * 加载图片。远程地址优先尝试 crossOrigin='anonymous'（避免污染 canvas），
 * 失败后回退为普通加载（同源场景本身不会污染）。
 */
export function loadImage(src: string): Promise<HTMLImageElement> {
  const isRemote = /^https?:\/\//.test(src)
  const attempt = (useCrossOrigin: boolean) =>
    new Promise<HTMLImageElement>((resolve, reject) => {
      const img = new Image()
      if (useCrossOrigin) img.crossOrigin = 'anonymous'
      img.onload = () => resolve(img)
      img.onerror = () => reject(new Error(`图片加载失败: ${src}`))
      img.src = src
    })

  if (!isRemote) return attempt(false)
  return attempt(true).catch(() => attempt(false))
}

/** 从 File/Blob 创建可绘制的 HTMLImageElement（内部使用 object URL 并自动释放） */
export async function loadImageFromBlob(blob: Blob): Promise<HTMLImageElement> {
  const url = URL.createObjectURL(blob)
  try {
    return await loadImage(url)
  } finally {
    // 图片 decode 完成后即可释放 object URL（img 已持有位图）
    URL.revokeObjectURL(url)
  }
}

/** 绘制高斯模糊铺底（cover 铺满 + 轻微放大避免边缘发虚露底） */
function drawBlurBackground(
  ctx: CanvasRenderingContext2D,
  image: HTMLImageElement | HTMLCanvasElement,
  srcWidth: number,
  srcHeight: number,
  dstWidth: number,
  dstHeight: number,
  blurRadius: number
) {
  const rect = computeCoverRect(srcWidth, srcHeight, dstWidth, dstHeight)
  // 放大一点，让 blur 的透明边缘落在画布外
  const pad = blurRadius * 2
  const scaleX = (rect.width + pad * 2) / rect.width
  const scaleY = (rect.height + pad * 2) / rect.height
  const w = rect.width * scaleX
  const h = rect.height * scaleY
  const x = rect.x - (w - rect.width) / 2
  const y = rect.y - (h - rect.height) / 2

  ctx.save()
  if (typeof ctx.filter === 'string') {
    ctx.filter = `blur(${blurRadius}px)`
    ctx.drawImage(image, x, y, w, h)
  } else {
    // 兼容不支持 ctx.filter 的环境：缩小再放大近似模糊
    const small = document.createElement('canvas')
    const factor = 16
    small.width = Math.max(1, Math.round(dstWidth / factor))
    small.height = Math.max(1, Math.round(dstHeight / factor))
    const sctx = small.getContext('2d')
    if (sctx) {
      sctx.drawImage(image, 0, 0, small.width, small.height)
      ctx.imageSmoothingEnabled = true
      ctx.drawImage(small, x, y, w, h)
    } else {
      ctx.drawImage(image, x, y, w, h)
    }
  }
  ctx.restore()

  // 轻微压暗，让前景图与模糊底有层次
  ctx.save()
  ctx.fillStyle = 'rgba(0, 0, 0, 0.08)'
  ctx.fillRect(0, 0, dstWidth, dstHeight)
  ctx.restore()
}

/** 绘制文字水印（位置可配，默认右下角） */
function drawWatermark(
  ctx: CanvasRenderingContext2D,
  options: WatermarkOptions,
  dstWidth: number,
  dstHeight: number
) {
  const text = options.text.trim()
  if (!text) return

  const fontSize =
    options.fontSize ??
    (options.sizeRatio != null
      ? computeWatermarkFontSize(dstWidth, options.sizeRatio)
      : computeDefaultWatermarkFontSize(dstWidth))
  const opacity = options.opacity ?? 0.5
  const color = options.color ?? '#FFFFFF'
  const margin = options.margin ?? fontSize
  const anchor = computeWatermarkAnchor(options.position ?? 'bottom-right', dstWidth, dstHeight, margin)

  ctx.save()
  ctx.globalAlpha = Math.min(1, Math.max(0, opacity))
  ctx.font = `600 ${fontSize}px -apple-system, "PingFang SC", "Microsoft YaHei", sans-serif`
  ctx.textAlign = anchor.textAlign
  ctx.textBaseline = anchor.textBaseline
  if (options.shadow ?? true) {
    // 深色描影保证浅色背景下依然可读
    ctx.shadowColor = 'rgba(0, 0, 0, 0.45)'
    ctx.shadowBlur = Math.max(2, Math.round(fontSize / 8))
    ctx.shadowOffsetY = 1
  }
  ctx.fillStyle = color
  ctx.fillText(text, anchor.x, anchor.y)
  ctx.restore()
}

/**
 * 核心渲染：把图片按指定策略绘制到目标尺寸 canvas
 * @param image 已加载完成的图片（或 canvas）
 * @param options 目标尺寸 / 策略 / 背景 / 水印
 * @returns 渲染好的 canvas（可继续转 blob 或展示预览）
 */
export function renderToCanvas(
  image: HTMLImageElement | HTMLCanvasElement,
  options: ExportRenderOptions
): HTMLCanvasElement {
  const srcWidth = image instanceof HTMLCanvasElement ? image.width : image.naturalWidth
  const srcHeight = image instanceof HTMLCanvasElement ? image.height : image.naturalHeight
  const { width: dstWidth, height: dstHeight, fit } = options

  const canvas = document.createElement('canvas')
  canvas.width = dstWidth
  canvas.height = dstHeight
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法创建 canvas 2d 上下文')

  ctx.imageSmoothingEnabled = true
  ctx.imageSmoothingQuality = 'high'

  if (fit === 'cover') {
    const rect = computeCoverRect(srcWidth, srcHeight, dstWidth, dstHeight)
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height)
  } else {
    const background = options.background ?? { type: 'color', color: '#FFFFFF' }
    if (background.type === 'blur') {
      const blurRadius = background.blurRadius ?? computeDefaultBlurRadius(dstWidth, dstHeight)
      drawBlurBackground(ctx, image, srcWidth, srcHeight, dstWidth, dstHeight, blurRadius)
    } else {
      ctx.fillStyle = background.color
      ctx.fillRect(0, 0, dstWidth, dstHeight)
    }
    const rect = computeContainRect(srcWidth, srcHeight, dstWidth, dstHeight)
    ctx.drawImage(image, rect.x, rect.y, rect.width, rect.height)
  }

  if (options.watermark) {
    drawWatermark(ctx, options.watermark, dstWidth, dstHeight)
  }

  return canvas
}

/** canvas 转 PNG Blob（canvas 被跨域污染时会抛错，由调用方兜底提示） */
export function canvasToBlob(canvas: HTMLCanvasElement, type: string = 'image/png'): Promise<Blob> {
  return new Promise<Blob>((resolve, reject) => {
    try {
      canvas.toBlob(blob => {
        if (blob) resolve(blob)
        else reject(new Error('canvas 导出失败（图片可能跨域被污染）'))
      }, type)
    } catch (e) {
      reject(e instanceof Error ? e : new Error('canvas 导出失败'))
    }
  })
}

/**
 * 一步到位：加载图片地址（或本地 Blob）并按参数导出 PNG Blob
 */
export async function exportImageToBlob(
  source: string | Blob,
  options: ExportRenderOptions
): Promise<Blob> {
  const image =
    typeof source === 'string' ? await loadImage(source) : await loadImageFromBlob(source)
  const canvas = renderToCanvas(image, options)
  return canvasToBlob(canvas)
}

/** 触发浏览器下载一个 Blob */
export function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob)
  const link = document.createElement('a')
  link.href = url
  link.download = filename
  document.body.appendChild(link)
  link.click()
  document.body.removeChild(link)
  // 延迟释放，避免部分浏览器下载尚未开始就失效
  setTimeout(() => URL.revokeObjectURL(url), 10_000)
}
