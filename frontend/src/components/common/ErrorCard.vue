<template>
  <section v-if="normalized" class="error-card" role="alert" aria-live="polite">
    <div class="error-main">
      <div class="error-icon">!</div>
      <div class="error-content">
        <div class="error-title-row">
          <h3>{{ normalized.title }}</h3>
          <span v-if="normalized.code" class="error-code">{{ normalized.code }}</span>
        </div>
        <p class="error-detail">{{ normalized.detail }}</p>
        <p v-if="normalized.suggestion" class="error-suggestion">{{ normalized.suggestion }}</p>
        <button
          v-if="normalized.retryable"
          class="retry-btn"
          type="button"
          @click="$emit('retry')"
        >
          重试
        </button>
      </div>
      <button v-if="dismissible" class="error-close" type="button" @click="$emit('dismiss')" aria-label="关闭错误提示">
        ×
      </button>
    </div>

    <details class="error-details">
      <summary>诊断信息</summary>
      <pre>{{ diagnostics }}</pre>
      <button class="copy-btn" type="button" @click="copyDiagnostics">
        {{ copied ? '已复制' : '复制诊断信息' }}
      </button>
    </details>
  </section>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import {
  diagnosticsText,
  normalizeApiError,
  type AppError,
  type ErrorLike
} from '../../utils/errors'

const props = defineProps<{
  error: ErrorLike | null | undefined
  title?: string
  dismissible?: boolean
}>()

defineEmits<{
  (e: 'dismiss'): void
  (e: 'retry'): void
}>()

const copied = ref(false)

const normalized = computed<AppError | null>(() => {
  if (!props.error) return null
  return normalizeApiError(props.error, props.title || '操作失败')
})

const diagnostics = computed(() => normalized.value ? diagnosticsText(normalized.value) : '')

async function copyDiagnostics() {
  if (!normalized.value) return
  try {
    await navigator.clipboard.writeText(diagnostics.value)
    copied.value = true
    window.setTimeout(() => {
      copied.value = false
    }, 1600)
  } catch (error) {
    console.error('复制诊断信息失败:', error)
  }
}
</script>

<style scoped>
.error-card {
  border: 1px solid rgba(222, 59, 59, 0.25);
  background: var(--color-danger-soft);
  border-radius: var(--radius-md);
  padding: var(--space-4);
  color: var(--color-danger);
}

.error-main {
  display: flex;
  gap: var(--space-3);
  align-items: flex-start;
}

.error-icon {
  flex: 0 0 auto;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-danger);
  color: #fff;
  font-weight: 700;
  font-size: 14px;
  line-height: 1;
}

.error-content {
  flex: 1;
  min-width: 0;
}

.error-title-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.error-title-row h3 {
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--color-danger);
}

.error-code {
  font-family: var(--font-mono);
  font-size: 11px;
  color: var(--color-danger);
  background: rgba(222, 59, 59, 0.12);
  padding: 2px 6px;
  border-radius: var(--radius-xs);
}

.error-detail,
.error-suggestion {
  margin: 6px 0 0;
  font-size: 13px;
  line-height: 1.55;
  color: var(--text-sub);
}

.error-suggestion {
  color: var(--color-danger);
}

.error-close {
  border: none;
  background: transparent;
  color: var(--color-danger);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  border-radius: var(--radius-xs);
  transition: opacity var(--transition-fast);
}

.error-close:hover {
  opacity: 0.7;
}

.error-details {
  margin-top: 10px;
  padding-left: 34px;
}

.error-details summary {
  cursor: pointer;
  font-size: 12px;
  color: var(--color-danger);
  user-select: none;
}

.error-details pre {
  white-space: pre-wrap;
  word-break: break-word;
  margin: var(--space-2) 0;
  padding: 10px;
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  border: 1px solid rgba(222, 59, 59, 0.2);
  color: var(--text-sub);
  font-family: var(--font-mono);
  font-size: 11px;
  line-height: 1.45;
  max-height: 220px;
  overflow: auto;
}

.copy-btn {
  border: 1px solid rgba(222, 59, 59, 0.25);
  background: var(--bg-card);
  color: var(--color-danger);
  border-radius: var(--radius-sm);
  padding: 6px 10px;
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.copy-btn:hover {
  background: var(--gray-0);
  border-color: rgba(222, 59, 59, 0.4);
}

.retry-btn {
  margin-top: 10px;
  border: none;
  background: var(--color-danger);
  color: #fff;
  border-radius: var(--radius-sm);
  padding: 6px 16px;
  font-size: 13px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--transition-fast), transform var(--transition-fast);
}

.retry-btn:hover {
  background: var(--color-danger);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}
</style>
