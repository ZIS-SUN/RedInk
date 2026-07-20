import type { HotspotNode, HotspotType } from '../api/hotspot'

/**
 * 热点节点图层的纯函数工具
 *
 * - 图层开关偏好的 localStorage 读写
 * - 日历网格查询区间计算（与 ToolCalendarView 月历格子的补位逻辑一致）
 * - 节点按日期分组、未来 N 天节点排序、倒计时与备稿窗口提示
 * - 「生成节点选题」的选题请求文本拼装
 */

/** 图层开关偏好的 localStorage key */
export const HOTSPOT_LAYER_STORAGE_KEY = 'redink_hotspot_layer_enabled'

/** 节点类型 -> 中文标签 */
const TYPE_LABELS: Record<HotspotType, string> = {
  festival: '节日',
  ecommerce: '电商',
  season: '季节'
}

export function hotspotTypeLabel(type: HotspotType): string {
  return TYPE_LABELS[type] ?? type
}

/**
 * 读取图层开关偏好，默认开启。
 * storage 读取异常（如隐私模式禁用）时回退默认值。
 */
export function loadHotspotLayerEnabled(storage: Pick<Storage, 'getItem'> = localStorage): boolean {
  try {
    return storage.getItem(HOTSPOT_LAYER_STORAGE_KEY) !== '0'
  } catch {
    return true
  }
}

/** 保存图层开关偏好（写入失败静默忽略，不影响本次会话内的开关状态） */
export function saveHotspotLayerEnabled(
  enabled: boolean,
  storage: Pick<Storage, 'setItem'> = localStorage
): void {
  try {
    storage.setItem(HOTSPOT_LAYER_STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    // localStorage 不可用时静默
  }
}

/** 把 YYYY-MM-DD 解析为本地时区 Date（避免 new Date(str) 的 UTC 偏移） */
function parseDate(dateStr: string): Date {
  const [y, m, d] = dateStr.split('-').map(Number)
  return new Date(y, m - 1, d)
}

/** 本地时区的 YYYY-MM-DD */
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

/** 日期字符串加 n 天，返回 YYYY-MM-DD */
export function addDays(dateStr: string, n: number): string {
  const d = parseDate(dateStr)
  d.setDate(d.getDate() + n)
  return toDateStr(d)
}

/** dateStr 距 todayStr 的天数（未来为正、过去为负、当天为 0） */
export function daysUntil(dateStr: string, todayStr: string): number {
  const diff = parseDate(dateStr).getTime() - parseDate(todayStr).getTime()
  return Math.round(diff / 86_400_000)
}

/**
 * 月历网格（周一开始、含前后月补位）的起止日期，
 * 与 ToolCalendarView 的 calendarCells 补位逻辑保持一致。
 */
export function calendarGridRange(month: string): { start: string; end: string } {
  const [year, m] = month.split('-').map(Number)
  const first = new Date(year, m - 1, 1)
  const leading = (first.getDay() + 6) % 7
  const start = new Date(year, m - 1, 1 - leading)
  const total = Math.ceil((leading + new Date(year, m, 0).getDate()) / 7) * 7
  const end = new Date(start.getFullYear(), start.getMonth(), start.getDate() + total - 1)
  return { start: toDateStr(start), end: toDateStr(end) }
}

/** 按日期分组，供月历叠加图层渲染 */
export function groupHotspotsByDate(hotspots: HotspotNode[]): Record<string, HotspotNode[]> {
  const map: Record<string, HotspotNode[]> = {}
  for (const node of hotspots) {
    if (!map[node.date]) map[node.date] = []
    map[node.date].push(node)
  }
  return map
}

/**
 * 未来 days 天内（含今天）的节点，按临近程度升序（同日按名称稳定排序）。
 */
export function upcomingHotspots(
  hotspots: HotspotNode[],
  todayStr: string,
  days = 30
): HotspotNode[] {
  return hotspots
    .filter(node => {
      const diff = daysUntil(node.date, todayStr)
      return diff >= 0 && diff <= days
    })
    .sort((a, b) => (a.date === b.date ? a.name.localeCompare(b.name) : a.date < b.date ? -1 : 1))
}

/** 倒计时文案：今天 / 明天 / 还有 N 天 */
export function countdownText(node: HotspotNode, todayStr: string): string {
  const diff = daysUntil(node.date, todayStr)
  if (diff <= 0) return '就是今天'
  if (diff === 1) return '明天'
  return `还有 ${diff} 天`
}

/**
 * 备稿窗口提示：
 * - 距节点天数 <= 建议备稿天数：窗口已开启，提示抓紧备稿
 * - 尚未进入窗口：提示还有几天进入备稿期
 */
export function prepWindowText(node: HotspotNode, todayStr: string): string {
  const diff = daysUntil(node.date, todayStr)
  if (diff <= 0) return '今日节点，适合发布收尾内容'
  if (diff <= node.prep_days) {
    return `备稿窗口已开启（建议提前 ${node.prep_days} 天备稿）`
  }
  return `${diff - node.prep_days} 天后进入备稿期（建议提前 ${node.prep_days} 天）`
}

/**
 * 拼装「生成节点选题」的选题请求文本：节点名称 + 平台侧重提示。
 */
export function buildHotspotTopicNiche(node: HotspotNode): string {
  const hint = node.platform_hint.trim()
  return hint ? `${node.name}（${hint}）` : node.name
}
