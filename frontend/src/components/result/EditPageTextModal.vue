<template>
  <Teleport to="body">
    <div v-if="visible" class="edit-overlay" @click.self="$emit('cancel')">
      <div class="edit-dialog" role="dialog" aria-modal="true" :aria-label="`编辑第 ${pageIndex + 1} 页文字`">
        <h3 class="edit-title">编辑第 {{ pageIndex + 1 }} 页文字</h3>

        <textarea
          ref="textareaRef"
          v-model="text"
          class="edit-textarea"
          placeholder="在此输入文案..."
        />
        <div class="edit-word-count">{{ text.length }} 字</div>

        <p class="edit-hint">重画约需 1 分钟，将用新文案重新生成这张图。</p>

        <div class="edit-actions">
          <button type="button" class="edit-btn cancel" @click="$emit('cancel')">取消</button>
          <button type="button" class="edit-btn secondary" @click="$emit('save', text)">仅保存</button>
          <button type="button" class="edit-btn primary" @click="$emit('saveAndRegenerate', text)">
            保存并重画此页
          </button>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
/**
 * 结果页「编辑文字」弹窗：编辑单页大纲文案，可仅保存或保存后重画该页。
 * 视觉与 views/shared/ConfirmDialog.vue 保持一致。
 */
import { nextTick, ref, watch } from 'vue'

const props = defineProps<{
  visible: boolean
  /** 页面索引（0 起） */
  pageIndex: number
  /** 打开弹窗时的初始文案（该页 outline content） */
  initialContent: string
}>()

defineEmits<{
  (e: 'cancel'): void
  (e: 'save', content: string): void
  (e: 'saveAndRegenerate', content: string): void
}>()

const text = ref('')
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 每次打开弹窗时重置为该页最新文案，并聚焦输入框
watch(
  () => props.visible,
  async (visible) => {
    if (visible) {
      text.value = props.initialContent
      await nextTick()
      textareaRef.value?.focus()
    }
  }
)
</script>

<style scoped>
.edit-overlay {
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
  animation: edit-fade 0.2s var(--ease-out);
}

.edit-dialog {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: var(--space-6) var(--space-5) var(--space-5);
  width: 100%;
  max-width: 520px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: edit-pop 0.2s var(--ease-out);
}

@keyframes edit-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes edit-pop {
  from { opacity: 0; transform: scale(0.96) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .edit-overlay,
  .edit-dialog {
    animation: none;
  }
}

.edit-title {
  margin: 0 0 var(--space-4);
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

/* 风格参考 OutlineView 的 .textarea-paper，弹窗内加边框便于识别可编辑区 */
.edit-textarea {
  width: 100%;
  min-height: 200px;
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--gray-1);
  font-size: 16px;
  line-height: 1.7;
  color: var(--text-main);
  font-family: inherit;
  resize: vertical;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.edit-textarea::placeholder {
  color: var(--text-placeholder);
}

.edit-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.edit-word-count {
  text-align: right;
  font-size: 11px;
  color: var(--text-sub);
  margin-top: 6px;
}

.edit-hint {
  margin: var(--space-3) 0 var(--space-4);
  font-size: 12px;
  line-height: 1.6;
  color: var(--text-sub);
}

.edit-actions {
  display: flex;
  gap: var(--space-3);
}

.edit-btn {
  flex: 1;
  padding: 10px 12px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  letter-spacing: var(--tracking-tight);
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.edit-btn.cancel {
  border: 1px solid var(--border-hover);
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.edit-btn.cancel:hover {
  background: var(--gray-0);
  border-color: var(--gray-5);
}

.edit-btn.secondary {
  border: 1px solid var(--primary);
  background: var(--bg-card);
  color: var(--primary);
  box-shadow: var(--shadow-xs);
}

.edit-btn.secondary:hover {
  background: var(--primary-light);
}

.edit-btn.primary {
  flex: 1.4;
  border: none;
  background: var(--primary);
  color: white;
  box-shadow: var(--shadow-xs), 0 4px 12px var(--primary-fade);
}

.edit-btn.primary:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm), 0 6px 16px var(--primary-fade);
}

.edit-btn.primary:active {
  background: var(--primary-active);
  transform: translateY(0);
}

/* 移动端：竖排按钮避免文字挤压溢出 */
@media (max-width: 640px) {
  .edit-dialog {
    max-height: 85vh;
  }

  .edit-actions {
    flex-direction: column-reverse;
  }

  .edit-btn.primary {
    flex: 1;
  }
}
</style>
