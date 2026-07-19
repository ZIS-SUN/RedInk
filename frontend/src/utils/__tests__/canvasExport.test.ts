import { describe, expect, it } from 'vitest'
import {
  SIZE_PRESETS,
  buildExportFilename,
  computeContainRect,
  computeCoverRect,
  computeDefaultBlurRadius,
  computeDefaultWatermarkFontSize
} from '../canvasExport'

describe('computeContainRect', () => {
  it('横图放进竖版画布：宽度贴边，上下留白居中', () => {
    // 2000x1000 -> 1080x1920
    const rect = computeContainRect(2000, 1000, 1080, 1920)
    expect(rect.width).toBe(1080)
    expect(rect.height).toBe(540)
    expect(rect.x).toBe(0)
    expect(rect.y).toBe(690) // (1920-540)/2
  })

  it('竖图放进横版画布：高度贴边，左右留白居中', () => {
    // 1080x1440 -> 1146x717
    const rect = computeContainRect(1080, 1440, 1146, 717)
    expect(rect.height).toBe(717)
    expect(rect.width).toBe(538) // round(1080 * 717/1440)
    expect(rect.y).toBe(0)
    expect(rect.x).toBe(304) // round((1146-538)/2)
  })

  it('同比例时铺满整个画布', () => {
    const rect = computeContainRect(540, 960, 1080, 1920)
    expect(rect).toEqual({ x: 0, y: 0, width: 1080, height: 1920 })
  })

  it('非法输入返回空矩形', () => {
    expect(computeContainRect(0, 100, 1080, 1920)).toEqual({ x: 0, y: 0, width: 0, height: 0 })
    expect(computeContainRect(100, 100, -1, 1920)).toEqual({ x: 0, y: 0, width: 0, height: 0 })
  })
})

describe('computeCoverRect', () => {
  it('横图填满竖版画布：高度贴边，左右超出（x 为负）', () => {
    // 2000x1000 -> 1080x1920
    const rect = computeCoverRect(2000, 1000, 1080, 1920)
    expect(rect.height).toBe(1920)
    expect(rect.width).toBe(3840) // 2000 * 1920/1000
    expect(rect.y).toBe(0)
    expect(rect.x).toBe(-1380) // (1080-3840)/2
  })

  it('竖图填满横幅画布：宽度贴边，上下超出（y 为负）', () => {
    // 1080x1440 -> 900x383
    const rect = computeCoverRect(1080, 1440, 900, 383)
    expect(rect.width).toBe(900)
    expect(rect.height).toBe(1200) // 1440 * 900/1080
    expect(rect.x).toBe(0)
    expect(rect.y).toBe(-408) // Math.round((383-1200)/2)，round 向正无穷取整
  })

  it('同比例时正好铺满不裁切', () => {
    const rect = computeCoverRect(540, 960, 1080, 1920)
    expect(rect).toEqual({ x: 0, y: 0, width: 1080, height: 1920 })
  })

  it('cover 结果始终覆盖整个画布', () => {
    for (const preset of SIZE_PRESETS) {
      const rect = computeCoverRect(1080, 1440, preset.width, preset.height)
      expect(rect.x).toBeLessThanOrEqual(0)
      expect(rect.y).toBeLessThanOrEqual(0)
      expect(rect.x + rect.width).toBeGreaterThanOrEqual(preset.width)
      expect(rect.y + rect.height).toBeGreaterThanOrEqual(preset.height)
    }
  })
})

describe('computeDefaultWatermarkFontSize', () => {
  it('按画布宽度 3% 计算并限制在 14~64px', () => {
    expect(computeDefaultWatermarkFontSize(1080)).toBe(32)
    expect(computeDefaultWatermarkFontSize(100)).toBe(14)
    expect(computeDefaultWatermarkFontSize(10000)).toBe(64)
  })
})

describe('computeDefaultBlurRadius', () => {
  it('按短边 3% 计算并限制在 16~60px', () => {
    expect(computeDefaultBlurRadius(1080, 1920)).toBe(32)
    expect(computeDefaultBlurRadius(200, 200)).toBe(16)
    expect(computeDefaultBlurRadius(9000, 9000)).toBe(60)
  })
})

describe('buildExportFilename', () => {
  it('去掉扩展名并附加目标尺寸', () => {
    expect(buildExportFilename('photo.jpg', { width: 1080, height: 1920 }))
      .toBe('photo_1080x1920.png')
  })

  it('清理非法字符与空白', () => {
    expect(buildExportFilename('我的 图片/v2:final?.png', { width: 900, height: 383 }))
      .toBe('我的_图片_v2_final__900x383.png')
  })

  it('空名称回退为 image', () => {
    expect(buildExportFilename('.png', { width: 1080, height: 1080 }))
      .toBe('image_1080x1080.png')
  })

  it('预设尺寸符合规格', () => {
    const byId = Object.fromEntries(SIZE_PRESETS.map(p => [p.id, p]))
    expect(byId['xhs-3-4']).toMatchObject({ width: 1080, height: 1440 })
    expect(byId['square-1-1']).toMatchObject({ width: 1080, height: 1080 })
    expect(byId['douyin-9-16']).toMatchObject({ width: 1080, height: 1920 })
    expect(byId['mp-banner']).toMatchObject({ width: 900, height: 383 })
    expect(byId['bili-cover']).toMatchObject({ width: 1146, height: 717 })
  })
})
