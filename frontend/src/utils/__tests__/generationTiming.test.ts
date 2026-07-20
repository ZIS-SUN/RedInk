import { describe, expect, it } from 'vitest'
import {
  DEFAULT_IMAGE_DURATION_MS,
  estimateRemainingMs,
  expectedDurationMs,
  formatDuration,
  overallPercent,
  singleImagePercent
} from '../generationTiming'

describe('expectedDurationMs', () => {
  it('空样本时使用默认兜底值', () => {
    expect(expectedDurationMs([])).toBe(DEFAULT_IMAGE_DURATION_MS)
  })

  it('空样本时使用自定义兜底值', () => {
    expect(expectedDurationMs([], 60_000)).toBe(60_000)
  })

  it('有样本时取平均', () => {
    expect(expectedDurationMs([60_000, 90_000])).toBe(75_000)
  })

  it('过滤 <=0 的无效样本', () => {
    expect(expectedDurationMs([0, -100, 80_000])).toBe(80_000)
  })

  it('全部样本无效时回退到兜底值', () => {
    expect(expectedDurationMs([0, -1])).toBe(DEFAULT_IMAGE_DURATION_MS)
  })
})

describe('singleImagePercent', () => {
  it('elapsed <= 0 返回 0', () => {
    expect(singleImagePercent(0, 80_000)).toBe(0)
    expect(singleImagePercent(-1000, 80_000)).toBe(0)
  })

  it('预期时长内线性走到 90', () => {
    expect(singleImagePercent(40_000, 80_000)).toBeCloseTo(45)
    expect(singleImagePercent(80_000, 80_000)).toBeCloseTo(90)
  })

  it('刚超出预期时从 90 缓慢爬升', () => {
    const percent = singleImagePercent(81_000, 80_000)
    expect(percent).toBeGreaterThan(90)
    expect(percent).toBeLessThan(97)
  })

  it('大幅超出预期时上限 97', () => {
    expect(singleImagePercent(80_000 * 100, 80_000)).toBeLessThanOrEqual(97)
    expect(singleImagePercent(80_000 * 100, 80_000)).toBeCloseTo(97, 1)
  })

  it('爬升是单调递增的', () => {
    const p1 = singleImagePercent(90_000, 80_000)
    const p2 = singleImagePercent(160_000, 80_000)
    expect(p2).toBeGreaterThan(p1)
  })
})

describe('overallPercent', () => {
  it('total <= 0 返回 0', () => {
    expect(overallPercent(0, 0, [])).toBe(0)
    expect(overallPercent(0, -1, [])).toBe(0)
  })

  it('无进行中图片时按完成数计算', () => {
    expect(overallPercent(2, 5, [])).toBeCloseTo(40)
  })

  it('进行中图片的完成比例计入总进度', () => {
    expect(overallPercent(2, 5, [0.5])).toBeCloseTo(50)
  })

  it('未全部完成时上限 99.5', () => {
    expect(overallPercent(4, 5, [0.99, 0.99])).toBe(99.5)
  })

  it('done === total 时补满到 100', () => {
    expect(overallPercent(5, 5, [])).toBe(100)
  })
})

describe('estimateRemainingMs', () => {
  const expected = 80_000

  it('无进行中、无排队时为 0', () => {
    expect(estimateRemainingMs(0, [], expected)).toBe(0)
  })

  it('进行中图片按剩余预期时间计', () => {
    expect(estimateRemainingMs(0, [30_000], expected)).toBe(50_000)
  })

  it('进行中图片超时后保留 8% 预期作为最小剩余', () => {
    expect(estimateRemainingMs(0, [200_000], expected)).toBeCloseTo(0.08 * expected)
  })

  it('排队图片按整张预期时长计', () => {
    expect(estimateRemainingMs(3, [], expected)).toBe(3 * expected)
  })

  it('串行叠加：进行中 + 排队', () => {
    expect(estimateRemainingMs(2, [30_000], expected)).toBe(50_000 + 2 * expected)
  })
})

describe('formatDuration', () => {
  it('小于 60 秒只显示秒', () => {
    expect(formatDuration(45_000)).toBe('45 秒')
    expect(formatDuration(59_000)).toBe('59 秒')
  })

  it('向上取整秒', () => {
    expect(formatDuration(44_100)).toBe('45 秒')
    // 59.001s 向上取整到 60s，落入分钟格式
    expect(formatDuration(59_001)).toBe('1 分')
  })

  it('恰好 60 秒显示为 1 分', () => {
    expect(formatDuration(60_000)).toBe('1 分')
  })

  it('61 秒显示为 1 分 1 秒', () => {
    expect(formatDuration(61_000)).toBe('1 分 1 秒')
  })

  it('200 秒显示为 3 分 20 秒', () => {
    expect(formatDuration(200_000)).toBe('3 分 20 秒')
  })

  it('0 或负数显示为 0 秒', () => {
    expect(formatDuration(0)).toBe('0 秒')
    expect(formatDuration(-500)).toBe('0 秒')
  })
})
