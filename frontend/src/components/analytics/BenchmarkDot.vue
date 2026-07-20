<template>
  <span
    v-if="rating"
    class="benchmark-dot"
    :class="`benchmark-dot--${rating}`"
    :title="tooltip"
    role="img"
    :aria-label="ariaLabel"
  ></span>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { BenchmarkRating } from '../../api/analytics'

/**
 * 行业基准红黄绿点（B10）
 *
 * - 颜色复用项目 tone 色变量（--color-danger / warning / success）
 * - hover 通过原生 title 展示基准说明（调用方拼好 tooltip 文案）
 * - rating 为 null/undefined（无曝光数据无法评级）时不渲染
 */
const props = defineProps<{
  rating?: BenchmarkRating | null
  /** hover 显示的基准说明文案 */
  tooltip?: string
}>()

const RATING_TEXT: Record<BenchmarkRating, string> = {
  red: '低于行业基准',
  yellow: '接近行业基准',
  green: '达到行业基准'
}

const ariaLabel = computed(() => (props.rating ? RATING_TEXT[props.rating] : ''))
</script>

<style scoped>
.benchmark-dot {
  display: inline-block;
  width: 8px;
  height: 8px;
  border-radius: var(--radius-full);
  vertical-align: middle;
  cursor: help;
  flex-shrink: 0;
}

.benchmark-dot--green {
  background: var(--color-success);
}

.benchmark-dot--yellow {
  background: var(--color-warning);
}

.benchmark-dot--red {
  background: var(--color-danger);
}
</style>
