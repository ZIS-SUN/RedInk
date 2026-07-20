/**
 * 生成进度估算的纯函数集合
 *
 * 背景：单张图片生成约 60~90 秒（平均约 80s），一套图串行生成。
 * 这些函数把「已用时间 + 预期时长」换算成平滑的进度百分比和剩余时间估算，
 * 避免进度条长时间停在 0% 造成"卡死"错觉。
 */

/** 单张图片的默认预期生成时长（毫秒），无历史样本时使用 */
export const DEFAULT_IMAGE_DURATION_MS = 80_000

/**
 * 根据已完成图片的耗时样本估算单张预期时长
 * @param samples 已完成图片的耗时样本（毫秒），<=0 的样本会被过滤
 * @param fallback 无有效样本时的兜底值
 */
export function expectedDurationMs(samples: number[], fallback = DEFAULT_IMAGE_DURATION_MS): number {
  const valid = samples.filter(s => s > 0)
  if (valid.length === 0) return fallback
  return valid.reduce((sum, s) => sum + s, 0) / valid.length
}

/**
 * 单张图片的伪进度百分比（0~97）
 * - 预期时长内线性走到 90
 * - 超出预期后缓慢爬升：90 + 7 * (1 - exp(-(elapsed-expected)/expected))，上限 97
 * @param elapsedMs 已用时间（毫秒），<=0 返回 0
 * @param expectedMs 预期时长（毫秒）
 */
export function singleImagePercent(elapsedMs: number, expectedMs: number): number {
  if (elapsedMs <= 0) return 0
  if (expectedMs <= 0) return 97
  if (elapsedMs <= expectedMs) {
    return (elapsedMs / expectedMs) * 90
  }
  const overshoot = (elapsedMs - expectedMs) / expectedMs
  return Math.min(97, 90 + 7 * (1 - Math.exp(-overshoot)))
}

/**
 * 整体进度百分比：(已完成数 + Σ进行中图片的完成比例) / 总数 * 100
 * 未全部完成时上限 99.5，done === total 时返回 100
 * @param doneCount 已完成图片数
 * @param total 总图片数，<=0 返回 0
 * @param activeFractions 各进行中图片的完成比例（0~1）
 */
export function overallPercent(doneCount: number, total: number, activeFractions: number[]): number {
  if (total <= 0) return 0
  if (doneCount === total) return 100
  const activeSum = activeFractions.reduce((sum, f) => sum + f, 0)
  const percent = ((doneCount + activeSum) / total) * 100
  return Math.min(99.5, percent)
}

/**
 * 串行假设下的剩余时间估算（毫秒）
 * 进行中的图片按 max(预期 - 已用, 8% 预期) 计（快到点也留一点余量），排队图片按整张预期计
 * @param queuedCount 排队中的图片数
 * @param activeElapsedMs 各进行中图片的已用时间（毫秒）
 * @param expectedMs 单张预期时长（毫秒）
 */
export function estimateRemainingMs(queuedCount: number, activeElapsedMs: number[], expectedMs: number): number {
  const activeRemaining = activeElapsedMs.reduce(
    (sum, elapsed) => sum + Math.max(expectedMs - elapsed, 0.08 * expectedMs),
    0
  )
  return activeRemaining + queuedCount * expectedMs
}

/**
 * 把毫秒格式化为中文时长文案："3 分 20 秒" / "45 秒"
 * 向上取整秒；>=60s 用 分+秒（秒为 0 时只显示分）
 */
export function formatDuration(ms: number): string {
  const totalSeconds = Math.max(0, Math.ceil(ms / 1000))
  if (totalSeconds < 60) {
    return `${totalSeconds} 秒`
  }
  const minutes = Math.floor(totalSeconds / 60)
  const seconds = totalSeconds % 60
  return seconds === 0 ? `${minutes} 分` : `${minutes} 分 ${seconds} 秒`
}
