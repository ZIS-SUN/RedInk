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
  background: rgba(0, 0, 0, 0.45);
  z-index: 1100;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.confirm-dialog {
  background: white;
  border-radius: 14px;
  padding: 28px 24px 20px;
  width: 100%;
  max-width: 380px;
  text-align: center;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
  animation: confirm-pop 0.18s ease-out;
}

@keyframes confirm-pop {
  from { opacity: 0; transform: scale(0.95) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.confirm-icon {
  width: 44px;
  height: 44px;
  border-radius: 50%;
  margin: 0 auto 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--color-info-soft, #e6f4ff);
  color: var(--color-info, #1890ff);
}

.confirm-icon.danger {
  background: var(--color-danger-soft, #fff1f0);
  color: var(--color-danger, #ff4d4f);
}

.confirm-title {
  margin: 0 0 8px;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

.confirm-message {
  margin: 0 0 22px;
  font-size: 14px;
  line-height: 1.6;
  color: var(--text-sub, #666);
  white-space: pre-line;
}

.confirm-actions {
  display: flex;
  gap: 12px;
}

.confirm-btn {
  flex: 1;
  padding: 10px 16px;
  border-radius: 8px;
  font-size: 14px;
  font-weight: 600;
  cursor: pointer;
  transition: all 0.2s;
}

.confirm-btn.cancel {
  border: 1px solid var(--border-color, #eee);
  background: white;
  color: var(--text-main, #1a1a1a);
}

.confirm-btn.cancel:hover {
  background: #f5f5f5;
}

.confirm-btn.confirm {
  border: none;
  background: var(--primary, #ff2442);
  color: white;
}

.confirm-btn.confirm:hover {
  opacity: 0.9;
}

.confirm-btn.confirm.danger {
  background: var(--color-danger, #ff4d4f);
}
</style>
