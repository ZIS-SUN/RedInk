import { describe, expect, it } from 'vitest'
import {
  SAFE_ZONE_SCHEMES,
  SAFE_ZONE_SETTINGS_KEY,
  clamp01,
  defaultSafeZoneSettings,
  getSafeZoneScheme,
  loadSafeZoneSettings,
  parseSafeZoneSettings,
  saveSafeZoneSettings,
  toPixelRect,
  type SafeZoneSettings
} from '../safeZone'
import type { StorageLike } from '../watermarkSettings'

/** 内存版 StorageLike，用于测试 load/save */
function memoryStorage(
  initial: Record<string, string> = {}
): StorageLike & { data: Record<string, string> } {
  const data = { ...initial }
  return {
    data,
    getItem: (key: string) => (key in data ? data[key] : null),
    setItem: (key: string, value: string) => {
      data[key] = value
    }
  }
}

describe('SAFE_ZONE_SCHEMES 数据合法性', () => {
  it('至少覆盖抖音竖屏 / 小红书 / B站封面三个方案', () => {
    const ids = SAFE_ZONE_SCHEMES.map(s => s.presetId)
    expect(ids).toContain('douyin-9-16')
    expect(ids).toContain('xhs-3-4')
    expect(ids).toContain('bili-cover')
  })

  it('所有区域坐标均在 0~1 且不超出画布', () => {
    for (const scheme of SAFE_ZONE_SCHEMES) {
      for (const region of scheme.regions) {
        expect(region.x).toBeGreaterThanOrEqual(0)
        expect(region.y).toBeGreaterThanOrEqual(0)
        expect(region.w).toBeGreaterThan(0)
        expect(region.h).toBeGreaterThan(0)
        expect(region.x + region.w).toBeLessThanOrEqual(1)
        expect(region.y + region.h).toBeLessThanOrEqual(1)
        expect(region.label).toBeTruthy()
      }
    }
  })

  it('区域 key 全局唯一', () => {
    const keys = SAFE_ZONE_SCHEMES.flatMap(s => s.regions.map(r => r.key))
    expect(new Set(keys).size).toBe(keys.length)
  })
})

describe('getSafeZoneScheme', () => {
  it('已知 preset 返回对应方案', () => {
    expect(getSafeZoneScheme('douyin-9-16')?.label).toContain('抖音')
    expect(getSafeZoneScheme('xhs-3-4')?.regions).toHaveLength(1)
    expect(getSafeZoneScheme('bili-cover')?.regions[0].key).toBe('bili-duration')
  })

  it('无数据的尺寸（如 1:1 / 公众号头图）返回 null', () => {
    expect(getSafeZoneScheme('square-1-1')).toBeNull()
    expect(getSafeZoneScheme('mp-banner')).toBeNull()
    expect(getSafeZoneScheme('unknown')).toBeNull()
  })
})

describe('clamp01', () => {
  it('区间内原样返回', () => {
    expect(clamp01(0)).toBe(0)
    expect(clamp01(0.5)).toBe(0.5)
    expect(clamp01(1)).toBe(1)
  })

  it('越界钳制到 0~1，非数值回退 0', () => {
    expect(clamp01(-0.2)).toBe(0)
    expect(clamp01(1.5)).toBe(1)
    expect(clamp01(NaN)).toBe(0)
    expect(clamp01(Infinity)).toBe(0)
  })
})

describe('toPixelRect 相对坐标换算', () => {
  it('按目标尺寸线性换算并取整', () => {
    // 抖音右侧操作栏 × 1080x1920
    expect(toPixelRect({ x: 0.85, y: 0.35, w: 0.15, h: 0.5 }, 1080, 1920)).toEqual({
      x: 918,
      y: 672,
      width: 162,
      height: 960
    })
  })

  it('整幅宽度的区域铺满 x 轴', () => {
    const rect = toPixelRect({ x: 0, y: 0.78, w: 1, h: 0.22 }, 1080, 1920)
    expect(rect.x).toBe(0)
    expect(rect.width).toBe(1080)
    expect(rect.y + rect.height).toBe(1920)
  })

  it('小尺寸预览画布下同比例换算', () => {
    // 预览高 220 时的小红书底部标题区
    const rect = toPixelRect({ x: 0, y: 0.86, w: 1, h: 0.14 }, 165, 220)
    expect(rect).toEqual({ x: 0, y: Math.round(0.86 * 220), width: 165, height: Math.round(0.14 * 220) })
  })

  it('越界比例钳制在画布内', () => {
    const rect = toPixelRect({ x: 0.9, y: -0.5, w: 0.5, h: 2 }, 1000, 1000)
    expect(rect.x + rect.width).toBeLessThanOrEqual(1000)
    expect(rect.y).toBe(0)
    expect(rect.height).toBeLessThanOrEqual(1000)
  })

  it('目标尺寸非法时返回零矩形', () => {
    expect(toPixelRect({ x: 0, y: 0, w: 1, h: 1 }, 0, 1920)).toEqual({
      x: 0,
      y: 0,
      width: 0,
      height: 0
    })
    expect(toPixelRect({ x: 0, y: 0, w: 1, h: 1 }, 1080, NaN)).toEqual({
      x: 0,
      y: 0,
      width: 0,
      height: 0
    })
  })
})

describe('parseSafeZoneSettings', () => {
  it('null / 空串返回默认值（默认关）', () => {
    expect(parseSafeZoneSettings(null)).toEqual({ enabled: false })
    expect(parseSafeZoneSettings('')).toEqual(defaultSafeZoneSettings())
  })

  it('损坏 JSON 整体丢弃回默认值', () => {
    expect(parseSafeZoneSettings('{not json')).toEqual(defaultSafeZoneSettings())
    expect(parseSafeZoneSettings('[true]')).toEqual(defaultSafeZoneSettings())
    expect(parseSafeZoneSettings('"str"')).toEqual(defaultSafeZoneSettings())
  })

  it('合法设置原样解析', () => {
    expect(parseSafeZoneSettings(JSON.stringify({ enabled: true }))).toEqual({ enabled: true })
    expect(parseSafeZoneSettings(JSON.stringify({ enabled: false }))).toEqual({ enabled: false })
  })

  it('enabled 非布尔时回退默认值', () => {
    expect(parseSafeZoneSettings(JSON.stringify({ enabled: 'yes' }))).toEqual(
      defaultSafeZoneSettings()
    )
    expect(parseSafeZoneSettings(JSON.stringify({ other: 1 }))).toEqual(defaultSafeZoneSettings())
  })
})

describe('loadSafeZoneSettings / saveSafeZoneSettings', () => {
  it('storage 为空时返回默认值', () => {
    expect(loadSafeZoneSettings(null)).toEqual(defaultSafeZoneSettings())
  })

  it('save 后 load 能还原', () => {
    const storage = memoryStorage()
    const settings: SafeZoneSettings = { enabled: true }
    saveSafeZoneSettings(settings, storage)
    expect(storage.data[SAFE_ZONE_SETTINGS_KEY]).toBeTruthy()
    expect(loadSafeZoneSettings(storage)).toEqual(settings)
  })

  it('storage 里是损坏数据时 load 回默认值', () => {
    const storage = memoryStorage({ [SAFE_ZONE_SETTINGS_KEY]: '{{{' })
    expect(loadSafeZoneSettings(storage)).toEqual(defaultSafeZoneSettings())
  })

  it('getItem / setItem 抛异常时安全降级', () => {
    const storage: StorageLike = {
      getItem: () => {
        throw new Error('denied')
      },
      setItem: () => {
        throw new Error('denied')
      }
    }
    expect(loadSafeZoneSettings(storage)).toEqual(defaultSafeZoneSettings())
    expect(() => saveSafeZoneSettings(defaultSafeZoneSettings(), storage)).not.toThrow()
  })
})
