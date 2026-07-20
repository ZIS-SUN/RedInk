import { describe, expect, it } from 'vitest'
import {
  WATERMARK_COLOR_VALUES,
  WATERMARK_SETTINGS_KEY,
  WATERMARK_SIZE_RATIOS,
  WATERMARK_TEXT_MAX_CHARS,
  clampOpacity,
  defaultWatermarkSettings,
  loadWatermarkSettings,
  parseWatermarkSettings,
  saveWatermarkSettings,
  type StorageLike,
  type WatermarkSettings
} from '../watermarkSettings'

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

describe('defaultWatermarkSettings', () => {
  it('默认：右下角 / 60% / 中号 / 白色 / 空文字', () => {
    expect(defaultWatermarkSettings()).toEqual({
      text: '',
      position: 'bottom-right',
      opacity: 0.6,
      size: 'medium',
      color: 'white'
    })
  })

  it('每次返回新对象（避免共享可变状态）', () => {
    expect(defaultWatermarkSettings()).not.toBe(defaultWatermarkSettings())
  })
})

describe('clampOpacity', () => {
  it('区间内原样返回', () => {
    expect(clampOpacity(0.35)).toBe(0.35)
    expect(clampOpacity(0.1)).toBe(0.1)
    expect(clampOpacity(1)).toBe(1)
  })

  it('越界钳制到 0.1~1', () => {
    expect(clampOpacity(0)).toBe(0.1)
    expect(clampOpacity(-5)).toBe(0.1)
    expect(clampOpacity(1.5)).toBe(1)
  })

  it('非数值回退默认 0.6', () => {
    expect(clampOpacity('0.8')).toBe(0.6)
    expect(clampOpacity(NaN)).toBe(0.6)
    expect(clampOpacity(undefined)).toBe(0.6)
  })
})

describe('parseWatermarkSettings', () => {
  it('null / 空串返回默认值', () => {
    expect(parseWatermarkSettings(null)).toEqual(defaultWatermarkSettings())
    expect(parseWatermarkSettings('')).toEqual(defaultWatermarkSettings())
  })

  it('损坏 JSON 整体丢弃回默认值', () => {
    expect(parseWatermarkSettings('{not json')).toEqual(defaultWatermarkSettings())
    expect(parseWatermarkSettings('[1,2]')).toEqual(defaultWatermarkSettings())
    expect(parseWatermarkSettings('"str"')).toEqual(defaultWatermarkSettings())
  })

  it('合法设置原样解析', () => {
    const settings: WatermarkSettings = {
      text: '@我的品牌',
      position: 'top-left',
      opacity: 0.3,
      size: 'large',
      color: 'red'
    }
    expect(parseWatermarkSettings(JSON.stringify(settings))).toEqual(settings)
  })

  it('单个字段非法时回退该字段默认值', () => {
    const parsed = parseWatermarkSettings(
      JSON.stringify({ text: 42, position: 'middle', size: 'xl', color: 'blue', opacity: 0.5 })
    )
    expect(parsed).toEqual({ ...defaultWatermarkSettings(), opacity: 0.5 })
  })

  it('越界参数钳制：opacity 与超长文字', () => {
    const parsed = parseWatermarkSettings(
      JSON.stringify({ text: 'x'.repeat(100), opacity: 3, position: 'bottom-center' })
    )
    expect(parsed.opacity).toBe(1)
    expect(parsed.text).toHaveLength(WATERMARK_TEXT_MAX_CHARS)
    expect(parsed.position).toBe('bottom-center')
  })
})

describe('loadWatermarkSettings / saveWatermarkSettings', () => {
  it('storage 为空时返回默认值', () => {
    expect(loadWatermarkSettings(null)).toEqual(defaultWatermarkSettings())
  })

  it('save 后 load 能还原', () => {
    const storage = memoryStorage()
    const settings: WatermarkSettings = {
      text: '@RedInk',
      position: 'bottom-center',
      opacity: 0.8,
      size: 'small',
      color: 'black'
    }
    saveWatermarkSettings(settings, storage)
    expect(storage.data[WATERMARK_SETTINGS_KEY]).toBeTruthy()
    expect(loadWatermarkSettings(storage)).toEqual(settings)
  })

  it('storage 里是损坏数据时 load 回默认值', () => {
    const storage = memoryStorage({ [WATERMARK_SETTINGS_KEY]: '{{{' })
    expect(loadWatermarkSettings(storage)).toEqual(defaultWatermarkSettings())
  })

  it('getItem 抛异常时安全降级为默认值', () => {
    const storage: StorageLike = {
      getItem: () => {
        throw new Error('denied')
      },
      setItem: () => {
        throw new Error('denied')
      }
    }
    expect(loadWatermarkSettings(storage)).toEqual(defaultWatermarkSettings())
    // setItem 抛异常时静默忽略，不应向外抛
    expect(() => saveWatermarkSettings(defaultWatermarkSettings(), storage)).not.toThrow()
  })
})

describe('字号与颜色档位映射', () => {
  it('小/中/大 ≈ 图宽 2.5%/3.5%/5%', () => {
    expect(WATERMARK_SIZE_RATIOS.small).toBeCloseTo(0.025)
    expect(WATERMARK_SIZE_RATIOS.medium).toBeCloseTo(0.035)
    expect(WATERMARK_SIZE_RATIOS.large).toBeCloseTo(0.05)
  })

  it('三种颜色均有色值', () => {
    expect(WATERMARK_COLOR_VALUES.white).toBe('#FFFFFF')
    expect(WATERMARK_COLOR_VALUES.black).toBeTruthy()
    expect(WATERMARK_COLOR_VALUES.red).toBe('#EF2A45')
  })
})
