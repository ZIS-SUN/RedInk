import { describe, expect, it } from 'vitest'
import type { HotspotNode } from '../../api/hotspot'
import {
  addDays,
  buildHotspotTopicNiche,
  calendarGridRange,
  countdownText,
  daysUntil,
  groupHotspotsByDate,
  HOTSPOT_LAYER_STORAGE_KEY,
  hotspotTypeLabel,
  loadHotspotLayerEnabled,
  prepWindowText,
  saveHotspotLayerEnabled,
  upcomingHotspots
} from '../hotspotLayer'

function makeNode(overrides: Partial<HotspotNode> = {}): HotspotNode {
  return {
    id: '2026-02-14-情人节',
    name: '情人节',
    date: '2026-02-14',
    type: 'festival',
    prep_days: 10,
    platform_hint: '小红书情人节礼物攻略流量高峰提前 10 天',
    niche_hint: '礼物攻略、情感',
    ...overrides
  }
}

describe('图层开关偏好', () => {
  it('未存偏好时默认开启', () => {
    expect(loadHotspotLayerEnabled({ getItem: () => null })).toBe(true)
  })

  it('存了 0 时关闭，其他值开启', () => {
    expect(loadHotspotLayerEnabled({ getItem: () => '0' })).toBe(false)
    expect(loadHotspotLayerEnabled({ getItem: () => '1' })).toBe(true)
  })

  it('storage 抛异常时回退默认开启', () => {
    expect(loadHotspotLayerEnabled({ getItem: () => { throw new Error('blocked') } })).toBe(true)
  })

  it('保存偏好写入 0/1，写入失败静默', () => {
    const written: Record<string, string> = {}
    saveHotspotLayerEnabled(false, { setItem: (k, v) => { written[k] = v } })
    expect(written[HOTSPOT_LAYER_STORAGE_KEY]).toBe('0')
    saveHotspotLayerEnabled(true, { setItem: (k, v) => { written[k] = v } })
    expect(written[HOTSPOT_LAYER_STORAGE_KEY]).toBe('1')
    expect(() =>
      saveHotspotLayerEnabled(true, { setItem: () => { throw new Error('blocked') } })
    ).not.toThrow()
  })
})

describe('日期计算', () => {
  it('daysUntil 计算未来/过去/当天', () => {
    expect(daysUntil('2026-02-14', '2026-02-04')).toBe(10)
    expect(daysUntil('2026-02-04', '2026-02-14')).toBe(-10)
    expect(daysUntil('2026-02-14', '2026-02-14')).toBe(0)
  })

  it('daysUntil 跨月/跨年正确', () => {
    expect(daysUntil('2027-01-01', '2026-12-25')).toBe(7)
  })

  it('addDays 支持跨月进位', () => {
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01')
    expect(addDays('2026-02-01', 60)).toBe('2026-04-02')
  })

  it('calendarGridRange 与月历格子补位一致（周一开始）', () => {
    // 2026-02-01 是周日：向前补 5 天到 1/26（周一），共 5 周
    expect(calendarGridRange('2026-02')).toEqual({ start: '2026-01-26', end: '2026-03-01' })
    // 2026-06-01 是周一：无前补，共 5 周
    expect(calendarGridRange('2026-06')).toEqual({ start: '2026-06-01', end: '2026-07-05' })
  })
})

describe('分组与临近排序', () => {
  it('groupHotspotsByDate 按日期分组', () => {
    const a = makeNode()
    const b = makeNode({ id: '2026-02-14-x', name: 'x' })
    const c = makeNode({ id: '2026-02-17-春节', name: '春节', date: '2026-02-17' })
    const grouped = groupHotspotsByDate([a, b, c])
    expect(grouped['2026-02-14']).toHaveLength(2)
    expect(grouped['2026-02-17']).toHaveLength(1)
  })

  it('upcomingHotspots 只保留未来 N 天并按临近排序', () => {
    const past = makeNode({ id: 'p', date: '2026-02-01' })
    const today = makeNode({ id: 't', date: '2026-02-10' })
    const soon = makeNode({ id: 's', date: '2026-02-17' })
    const far = makeNode({ id: 'f', date: '2026-03-20' })

    const result = upcomingHotspots([far, soon, past, today], '2026-02-10', 30)
    expect(result.map(n => n.id)).toEqual(['t', 's'])
  })
})

describe('倒计时与备稿窗口提示', () => {
  it('countdownText：今天/明天/还有 N 天', () => {
    const node = makeNode()
    expect(countdownText(node, '2026-02-14')).toBe('就是今天')
    expect(countdownText(node, '2026-02-13')).toBe('明天')
    expect(countdownText(node, '2026-02-04')).toBe('还有 10 天')
  })

  it('prepWindowText：窗口内提示已开启，窗口外提示倒计时', () => {
    const node = makeNode({ prep_days: 10 })
    expect(prepWindowText(node, '2026-02-14')).toBe('今日节点，适合发布收尾内容')
    expect(prepWindowText(node, '2026-02-08')).toBe('备稿窗口已开启（建议提前 10 天备稿）')
    expect(prepWindowText(node, '2026-01-30')).toBe('5 天后进入备稿期（建议提前 10 天）')
  })
})

describe('选题请求拼装与类型标签', () => {
  it('buildHotspotTopicNiche 拼接节点名称与平台提示', () => {
    expect(buildHotspotTopicNiche(makeNode())).toBe(
      '情人节（小红书情人节礼物攻略流量高峰提前 10 天）'
    )
    expect(buildHotspotTopicNiche(makeNode({ platform_hint: '  ' }))).toBe('情人节')
  })

  it('hotspotTypeLabel 中文标签', () => {
    expect(hotspotTypeLabel('festival')).toBe('节日')
    expect(hotspotTypeLabel('ecommerce')).toBe('电商')
    expect(hotspotTypeLabel('season')).toBe('季节')
  })
})
