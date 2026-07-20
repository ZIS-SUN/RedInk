import type { AnalyticsTimeSlot } from '../api/analytics'

/**
 * 内容日历「最佳发布时段」推荐的纯函数工具
 *
 * 时段名称与后端 analytics 的 _TIME_SLOTS 划分一一对应：
 * 早晨 6-9 / 上午 9-12 / 午间 12-14 / 下午 14-18 / 晚间 18-22 / 深夜 22-6
 */

/** 时段名 -> 建议发布时间（该时段的起始整点，HH:MM） */
const SLOT_START_TIMES: Record<string, string> = {
  '早晨 6-9': '06:00',
  '上午 9-12': '09:00',
  '午间 12-14': '12:00',
  '下午 14-18': '14:00',
  '晚间 18-22': '18:00',
  '深夜 22-6': '22:00'
}

/**
 * 把时段名映射为建议的发布时间（时段起始整点）。
 * 未知时段返回 null。
 */
export function slotToSuggestedTime(slotName: string): string | null {
  return SLOT_START_TIMES[slotName] ?? null
}

/**
 * 从时段统计中挑出平均互动率最高的时段。
 * 列表为空（或非数组）返回 null；并列时取靠前的（后端按固定时段顺序输出）。
 */
export function pickBestTimeSlot(slots: AnalyticsTimeSlot[] | undefined | null): AnalyticsTimeSlot | null {
  if (!Array.isArray(slots) || slots.length === 0) return null
  let best = slots[0]
  for (const slot of slots) {
    if ((slot.avg_engagement ?? 0) > (best.avg_engagement ?? 0)) best = slot
  }
  return best
}
