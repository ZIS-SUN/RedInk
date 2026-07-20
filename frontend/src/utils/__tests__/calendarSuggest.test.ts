import { describe, expect, it } from 'vitest'
import { pickBestTimeSlot, slotToSuggestedTime } from '../calendarSuggest'

describe('slotToSuggestedTime', () => {
  it('六个时段各自映射到起始整点', () => {
    expect(slotToSuggestedTime('早晨 6-9')).toBe('06:00')
    expect(slotToSuggestedTime('上午 9-12')).toBe('09:00')
    expect(slotToSuggestedTime('午间 12-14')).toBe('12:00')
    expect(slotToSuggestedTime('下午 14-18')).toBe('14:00')
    expect(slotToSuggestedTime('晚间 18-22')).toBe('18:00')
    expect(slotToSuggestedTime('深夜 22-6')).toBe('22:00')
  })

  it('未知时段返回 null', () => {
    expect(slotToSuggestedTime('凌晨 0-6')).toBeNull()
    expect(slotToSuggestedTime('')).toBeNull()
    expect(slotToSuggestedTime('晚间')).toBeNull()
  })
})

describe('pickBestTimeSlot', () => {
  it('返回平均互动率最高的时段', () => {
    const best = pickBestTimeSlot([
      { name: '上午 9-12', count: 3, avg_engagement: 4.2 },
      { name: '晚间 18-22', count: 5, avg_engagement: 8.6 },
      { name: '深夜 22-6', count: 1, avg_engagement: 2.1 }
    ])
    expect(best?.name).toBe('晚间 18-22')
  })

  it('并列时取靠前的时段', () => {
    const best = pickBestTimeSlot([
      { name: '早晨 6-9', count: 2, avg_engagement: 5 },
      { name: '下午 14-18', count: 2, avg_engagement: 5 }
    ])
    expect(best?.name).toBe('早晨 6-9')
  })

  it('空列表 / undefined / null 返回 null', () => {
    expect(pickBestTimeSlot([])).toBeNull()
    expect(pickBestTimeSlot(undefined)).toBeNull()
    expect(pickBestTimeSlot(null)).toBeNull()
  })
})
