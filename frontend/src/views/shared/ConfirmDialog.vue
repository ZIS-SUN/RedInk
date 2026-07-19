<template>
  <Teleport to="body">
    <div v-if="visible" class="confirm-overlay" @click.self="$emit('cancel')">
      <div class="confirm-dialog" role="alertdialog" aria-modal="true" :aria-label="title">
        <div class="confirm-icon" :class="{ danger }">
          <svg v-if="danger" width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10.29 3.86 1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          <svg v-else width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="16" x2="12" y2="12"></line><line x1="12" y1="8" x2="12.01" y2="8"></line></svg>
        </div>
        <h3 class="confirm-title">{{ title }}</h3>
        <p class="confirm-message">{{ message }}</p>
        <div class="confirm-actions">
          <button type="button" class="confirm-btn cancel" @click="$emit('cancel')">
            {{ cancelText || '取消' }}
          </button>
          <button
            type="button"
            class="confirm-btn confirm"
            :class="{ danger }"
            @click="$emit('confirm')"
          >
            {{ confirmText || '确定' }}
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 视图层通用确认弹窗，替代原生 confirm()，与产品视觉保持一致。
 */
defineProps<{
  visible: boolean
  title: string
  message: string
  confirmText?: string
  cancelText?: string
  /** 危险操作（删除等），确认按钮显示为红色 */
  danger?: boolean
}>()

defineEmits<{
  (e: 'confirm'): void
  (e: 'cancel'): void
}>()
</script>

<style scoped>
.confirm-overlay {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
}

.confirm-dialog {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-6) var(--space-5) var(--space-5);
  width: 100%;
  max-width: 380px;
  text-align: center;
  box-shadow: var(--shadow-lg);
  animation: confirm-pop 0.2s var(--ease-out);
}

@keyframes confirm-pop {
  from { opacity: 0; transform: scale(0.97) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.confirm-icon {
  width: 44px;
  height: 44px;
  border-radius: var(--radius-full);
  margin: 0 auto var(--space-4);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-info-soft);
  color: var(--color-info);
}

.confirm-icon.danger {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.confirm-title {
  margin: 0 0 var(--space-2);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.confirm-message {
  margin: 0 0 var(--space-5);
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-sub);
  white-space: pre-line;
}

.confirm-actions {
  display: flex;
  gap: var(--space-3);
}

.confirm-btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  letter-spacing: var(--tracking-tight);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.confirm-btn.cancel {
  border: 1px solid var(--border-hover);
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.confirm-btn.cancel:hover {
  background: var(--gray-0);
  border-color: var(--gray-5);
}

.confirm-btn.confirm {
  border: none;
  background: var(--primary);
  color: white;
  box-shadow: var(--shadow-xs), 0 4px 12px var(--primary-fade);
}

.confirm-btn.confirm:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.confirm-btn.confirm:active {
  background: var(--primary-active);
  transform: translateY(0);
}

.confirm-btn.confirm.danger {
  background: var(--color-danger);
  box-shadow: var(--shadow-xs), 0 4px 12px var(--color-danger-soft);
}

.confirm-btn.confirm.danger:hover {
  background: var(--color-danger);
  box-shadow: var(--shadow-sm), 0 6px 16px var(--color-danger-soft);
}
</style>
