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
  padding: 4px 6px;
  border-radius: 8px;
  cursor: default;
  color: var(--text-placeholder, #bbb);
}

.step-item.done {
  color: var(--text-sub, #666);
  cursor: pointer;
}

.step-item.done:hover {
  color: var(--primary, #ff2442);
  background: rgba(255, 36, 66, 0.05);
}

.step-item.active {
  color: var(--text-main, #1a1a1a);
}

.step-dot {
  width: 22px;
  height: 22px;
  border-radius: 50%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 600;
  flex-shrink: 0;
  background: #f0f0f0;
  color: var(--text-sub, #666);
}

.step-item.done .step-dot {
  background: var(--color-success-soft, #f6ffed);
  color: var(--color-success, #52c41a);
}

.step-item.active .step-dot {
  background: var(--primary, #ff2442);
  color: white;
}

.step-label {
  font-size: 13px;
  font-weight: 600;
  white-space: nowrap;
}

.step-line {
  flex: 1;
  min-width: 16px;
  max-width: 80px;
  height: 2px;
  border-radius: 1px;
  background: var(--border-color, #eee);
}

.step-line.done {
  background: var(--color-success, #52c41a);
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
