<template>
  <nav class="step-indicator" aria-label="创作流程步骤">
    <template v-for="(step, idx) in steps" :key="step.path">
      <button
        type="button"
        class="step-item"
        :class="{ done: idx + 1 < current, active: idx + 1 === current }"
        :disabled="idx + 1 >= current"
        :aria-current="idx + 1 === current ? 'step' : undefined"
        :title="idx + 1 < current ? `返回「${step.label}」` : step.label"
        @click="goTo(idx)"
      >
        <span class="step-dot">
          <svg v-if="idx + 1 < current" width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
          <span v-else>{{ idx + 1 }}</span>
        </span>
        <span class="step-label">{{ step.label }}</span>
      </button>
      <span
        v-if="idx < steps.length - 1"
        class="step-line"
        :class="{ done: idx + 1 < current }"
        aria-hidden="true"
      ></span>
    </template>
  </nav>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

/**
 * 核心流程 4 步进度指示器：主题 → 大纲 → 生成 → 结果
 * 已完成的步骤可点击回退。
 */

const props = defineProps<{
  /** 当前所处步骤（1-4） */
  current: number
}>()

const router = useRouter()

const steps = [
  { label: '主题', path: '/' },
  { label: '大纲', path: '/outline' },
  { label: '生成', path: '/generate' },
  { label: '结果', path: '/result' }
]

function goTo(idx: number) {
  if (idx + 1 < props.current) {
    router.push(steps[idx].path)
  }
}
</script>

<style scoped>
.step-indicator {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  margin: 0 auto 28px;
  max-width: 720px;
  padding: 0 12px;
}

.step-item {
  display: flex;
  align-items: center;
  gap: 8px;
  background: none;
  border: none;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  cursor: default;
  color: var(--text-placeholder);
  font-family: inherit;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.step-item.done {
  color: var(--text-sub);
  cursor: pointer;
}

.step-item.done:hover {
  color: var(--primary);
  background: var(--primary-fade);
}

.step-item.done:active {
  background: var(--primary-light);
}

.step-item.active {
  color: var(--text-main);
}

.step-dot {
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  flex-shrink: 0;
  background: var(--gray-2);
  color: var(--text-sub);
  transition: background var(--transition-base), color var(--transition-base),
    box-shadow var(--transition-base);
}

.step-item.done .step-dot {
  background: var(--color-success-soft);
  color: var(--color-success);
}

/* 当前步骤：主色实心 + 柔和光环，视线锚点更明确 */
.step-item.active .step-dot {
  background: var(--primary);
  color: white;
  box-shadow: 0 0 0 4px var(--primary-fade), 0 2px 8px var(--primary-fade);
}

.step-label {
  font-size: 13px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
}

.step-line {
  flex: 1;
  min-width: 16px;
  max-width: 80px;
  height: 2px;
  border-radius: var(--radius-full);
  background: var(--border-color);
  transition: background var(--transition-base);
}

.step-line.done {
  background: var(--color-success);
}

@media (max-width: 520px) {
  .step-indicator {
    gap: 4px;
  }

  .step-label {
    font-size: 12px;
  }

  .step-line {
    min-width: 8px;
  }
}
</style>
