<template>
  <svg
    class="compare-chart"
    :viewBox="`0 0 ${WIDTH} ${chartHeight}`"
    role="img"
    :aria-label="`${rateLabel}对比`"
    preserveAspectRatio="xMidYMid meet"
  >
    <g v-for="(row, i) in rows" :key="row.name">
      <!-- 分组名 -->
      <text
        :x="0"
        :y="rowCenterY(i) + 4"
        class="row-name"
        text-anchor="start"
      >
        {{ truncate(row.name) }}
        <title>{{ row.name }}</title>
      </text>

      <!-- 底轨 -->
      <rect
        :x="LABEL_WIDTH"
        :y="rowTopY(i)"
        :width="trackWidth"
        :height="BAR_HEIGHT"
        :rx="BAR_HEIGHT / 2"
        class="bar-track"
      />
      <!-- 数值条 -->
      <rect
        :x="LABEL_WIDTH"
        :y="rowTopY(i)"
        :width="barWidth(row)"
        :height="BAR_HEIGHT"
        :rx="BAR_HEIGHT / 2"
        class="bar-fill"
        :class="{ best: i === bestIndex }"
      >
        <title>{{ row.name }}：{{ rateLabel }} {{ row.rate }}% · {{ row.count }} 篇</title>
      </rect>

      <!-- 数值文本 -->
      <text
        :x="WIDTH"
        :y="rowCenterY(i) + 4"
        class="row-value"
        text-anchor="end"
      >
        {{ row.rate }}% · {{ row.count }} 篇
      </text>
    </g>
  </svg>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/** 对比条目：分组名 + 篇数 + 比率（百分比数值，如 5.21 表示 5.21%） */
interface CompareBarItem {
  name: string
  count: number
  rate: number
}

/**
 * 水平柱状对比图（手写 SVG，无第三方依赖）
 *
 * 用于「按平台」「按内容类型」「发布时段」等分组对比：
 * 条长 = rate / 组内最大 rate；hover 显示原生 title；
 * 比率最高的一条高亮为主色。prefers-reduced-motion 下无动画。
 */
const props = withDefaults(
  defineProps<{
    items: CompareBarItem[]
    /** 比率的展示名称（用于 title / aria），默认"互动率" */
    rateLabel?: string
  }>(),
  { rateLabel: '互动率' }
)

const WIDTH = 560
const LABEL_WIDTH = 96
const VALUE_WIDTH = 118
const BAR_HEIGHT = 12
const ROW_GAP = 30
const PAD_TOP = 8

const trackWidth = WIDTH - LABEL_WIDTH - VALUE_WIDTH

const rows = computed(() => props.items)

const chartHeight = computed(() => PAD_TOP * 2 + Math.max(rows.value.length, 1) * ROW_GAP)

const maxRate = computed(() => Math.max(...rows.value.map(r => r.rate), 0.01))

const bestIndex = computed(() => {
  let best = -1
  let bestRate = -Infinity
  rows.value.forEach((row, i) => {
    if (row.rate > bestRate) {
      bestRate = row.rate
      best = i
    }
  })
  return best
})

function rowTopY(index: number): number {
  return PAD_TOP + index * ROW_GAP + (ROW_GAP - BAR_HEIGHT) / 2 - 4
}

function rowCenterY(index: number): number {
  return rowTopY(index) + BAR_HEIGHT / 2
}

function barWidth(row: CompareBarItem): number {
  if (row.rate <= 0) return 0
  return Math.max((row.rate / maxRate.value) * trackWidth, BAR_HEIGHT)
}

function truncate(name: string): string {
  return name.length > 6 ? `${name.slice(0, 6)}…` : name
}
</script>

<style scoped>
.compare-chart {
  display: block;
  width: 100%;
  height: auto;
}

.row-name {
  font-size: 12px;
  font-weight: 600;
  fill: var(--text-main, #211e1b);
}

.row-value {
  font-size: 12px;
  fill: var(--text-sub);
  font-variant-numeric: tabular-nums;
}

.bar-track {
  fill: var(--gray-1);
}

.bar-fill {
  fill: var(--color-info);
  transition: width 0.4s var(--ease-out, ease-out);
}

.bar-fill.best {
  fill: var(--primary);
}

.bar-fill:hover {
  opacity: 0.85;
}

@media (prefers-reduced-motion: reduce) {
  .bar-fill {
    transition: none;
  }
}
</style>
