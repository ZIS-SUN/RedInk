<template>
  <svg
    class="trend-chart"
    :viewBox="`0 0 ${WIDTH} ${HEIGHT}`"
    role="img"
    aria-label="按月趋势：曝光量与平均互动率"
    preserveAspectRatio="xMidYMid meet"
  >
    <!-- 横向网格线 + 左轴（曝光）刻度 -->
    <g v-for="tick in viewTicks" :key="'g' + tick.y">
      <line
        :x1="PAD_LEFT"
        :y1="tick.y"
        :x2="WIDTH - PAD_RIGHT"
        :y2="tick.y"
        class="grid-line"
      />
      <text :x="PAD_LEFT - 8" :y="tick.y + 4" class="axis-label" text-anchor="end">
        {{ tick.label }}
      </text>
    </g>

    <!-- 曝光面积 + 折线 -->
    <path v-if="areaPath" :d="areaPath" class="views-area" />
    <path v-if="linePath" :d="linePath" class="views-line" />

    <!-- 互动率折线（第二序列，按自身最大值归一化） -->
    <path v-if="ratePath" :d="ratePath" class="rate-line" />

    <!-- 数据点（hover 显示数值 title） -->
    <g v-for="p in chartPoints" :key="'v' + p.month">
      <circle :cx="p.x" :cy="p.viewsY" r="4" class="views-dot">
        <title>{{ p.month }} 曝光 {{ formatNumber(p.views) }}（{{ p.count }} 条）</title>
      </circle>
      <circle :cx="p.x" :cy="p.rateY" r="3.5" class="rate-dot">
        <title>{{ p.month }} 平均互动率 {{ p.rate }}%</title>
      </circle>
      <!-- 透明命中区，扩大 hover 面积 -->
      <rect
        :x="p.x - hitWidth / 2"
        :y="PAD_TOP"
        :width="hitWidth"
        :height="plotHeight"
        fill="transparent"
      >
        <title>{{ p.month }}：曝光 {{ formatNumber(p.views) }} · 互动率 {{ p.rate }}% · {{ p.count }} 条</title>
      </rect>
    </g>

    <!-- X 轴月份标签（数量多时抽样显示） -->
    <text
      v-for="p in xLabels"
      :key="'x' + p.month"
      :x="p.x"
      :y="HEIGHT - 8"
      class="axis-label"
      text-anchor="middle"
    >
      {{ p.month }}
    </text>
  </svg>

  <div class="trend-legend" aria-hidden="true">
    <span class="legend-item"><span class="legend-swatch views"></span>曝光 / 播放</span>
    <span class="legend-item"><span class="legend-swatch rate"></span>平均互动率</span>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { AnalyticsTrendPoint } from '../../api/analytics'

/**
 * 按月趋势折线 + 面积图（手写 SVG，无第三方依赖）
 *
 * - 序列一：曝光量（面积 + 折线，主色）
 * - 序列二：当月平均互动率 = engagements / views * 100（按自身最大值归一化的第二条线）
 * - hover 数据点显示原生 title；prefers-reduced-motion 下无动画
 */
const props = defineProps<{
  /** stats.trend：按月升序的趋势点 */
  points: AnalyticsTrendPoint[]
}>()

const WIDTH = 640
const HEIGHT = 260
const PAD_LEFT = 56
const PAD_RIGHT = 16
const PAD_TOP = 16
const PAD_BOTTOM = 34

const plotWidth = WIDTH - PAD_LEFT - PAD_RIGHT
const plotHeight = HEIGHT - PAD_TOP - PAD_BOTTOM

interface ChartPoint {
  month: string
  count: number
  views: number
  /** 当月平均互动率（百分比，两位小数） */
  rate: number
  x: number
  viewsY: number
  rateY: number
}

const chartPoints = computed<ChartPoint[]>(() => {
  const points = props.points
  if (points.length === 0) return []

  const maxViews = Math.max(...points.map(p => p.views), 1)
  const rates = points.map(p => (p.views > 0 ? (p.engagements / p.views) * 100 : 0))
  const maxRate = Math.max(...rates, 0.01)

  return points.map((p, i) => {
    const x =
      points.length === 1
        ? PAD_LEFT + plotWidth / 2
        : PAD_LEFT + (i / (points.length - 1)) * plotWidth
    return {
      month: p.month,
      count: p.count,
      views: p.views,
      rate: Math.round(rates[i] * 100) / 100,
      x,
      viewsY: PAD_TOP + plotHeight * (1 - p.views / maxViews),
      rateY: PAD_TOP + plotHeight * (1 - rates[i] / maxRate)
    }
  })
})

/** 每个数据点的透明 hover 命中区宽度 */
const hitWidth = computed(() => {
  const n = chartPoints.value.length
  if (n <= 1) return plotWidth
  return plotWidth / (n - 1)
})

const linePath = computed(() => {
  const pts = chartPoints.value
  if (pts.length < 2) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.viewsY.toFixed(1)}`).join(' ')
})

const areaPath = computed(() => {
  const pts = chartPoints.value
  if (pts.length < 2) return ''
  const bottom = PAD_TOP + plotHeight
  const line = pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.viewsY.toFixed(1)}`).join(' ')
  return `${line} L${pts[pts.length - 1].x.toFixed(1)},${bottom} L${pts[0].x.toFixed(1)},${bottom} Z`
})

const ratePath = computed(() => {
  const pts = chartPoints.value
  if (pts.length < 2) return ''
  return pts.map((p, i) => `${i === 0 ? 'M' : 'L'}${p.x.toFixed(1)},${p.rateY.toFixed(1)}`).join(' ')
})

/** 左轴（曝光）网格刻度：0 / 50% / 100% 三档 */
const viewTicks = computed(() => {
  const maxViews = Math.max(...props.points.map(p => p.views), 1)
  return [0, 0.5, 1].map(ratio => ({
    y: PAD_TOP + plotHeight * (1 - ratio),
    label: formatNumber(Math.round(maxViews * ratio))
  }))
})

/** X 轴标签：最多显示 8 个，多了按步长抽样（首尾必显示） */
const xLabels = computed(() => {
  const pts = chartPoints.value
  const maxLabels = 8
  if (pts.length <= maxLabels) return pts
  const step = Math.ceil(pts.length / maxLabels)
  return pts.filter((_, i) => i % step === 0 || i === pts.length - 1)
})

function formatNumber(value: number): string {
  if (value >= 100000000) return `${Math.round((value / 100000000) * 10) / 10}亿`
  if (value >= 10000) return `${Math.round((value / 10000) * 10) / 10}万`
  return value.toLocaleString('zh-CN')
}
</script>

<style scoped>
.trend-chart {
  display: block;
  width: 100%;
  height: auto;
}

.grid-line {
  stroke: var(--gray-2);
  stroke-width: 1;
}

.axis-label {
  font-size: 11px;
  fill: var(--text-sub);
}

.views-line {
  fill: none;
  stroke: var(--primary);
  stroke-width: 2;
  stroke-linecap: round;
  stroke-linejoin: round;
}

.views-area {
  fill: var(--primary-fade, rgba(239, 42, 69, 0.08));
  stroke: none;
}

.rate-line {
  fill: none;
  stroke: var(--color-info);
  stroke-width: 2;
  stroke-dasharray: 5 4;
  stroke-linecap: round;
}

.views-dot {
  fill: var(--primary);
  stroke: var(--bg-card, #fff);
  stroke-width: 1.5;
  transition: r 0.15s var(--ease-out, ease-out);
}

.rate-dot {
  fill: var(--color-info);
  stroke: var(--bg-card, #fff);
  stroke-width: 1.5;
  transition: r 0.15s var(--ease-out, ease-out);
}

.views-dot:hover,
.rate-dot:hover {
  r: 6;
}

/* 图例 */
.trend-legend {
  display: flex;
  gap: 16px;
  margin-top: 8px;
  font-size: 12px;
  color: var(--text-sub);
}

.legend-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.legend-swatch {
  display: inline-block;
  width: 14px;
  height: 3px;
  border-radius: var(--radius-full);
}

.legend-swatch.views {
  background: var(--primary);
}

.legend-swatch.rate {
  background: var(--color-info);
}

@media (prefers-reduced-motion: reduce) {
  .views-dot,
  .rate-dot {
    transition: none;
  }
}
</style>
