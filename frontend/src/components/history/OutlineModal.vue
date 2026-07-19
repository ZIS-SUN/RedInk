<template>
  <!-- 大纲查看模态框 -->
  <div v-if="visible && pages" class="outline-modal-overlay" @click="$emit('close')">
    <div class="outline-modal-content" @click.stop>
      <div class="outline-modal-header">
        <h3>完整大纲</h3>
        <button class="close-icon" @click="$emit('close')">×</button>
      </div>
      <div class="outline-modal-body">
        <div v-for="(page, idx) in pages" :key="idx" class="outline-page-card">
          <div class="outline-page-card-header">
            <span class="page-badge">P{{ idx + 1 }}</span>
            <span class="page-type-badge" :class="page.type">{{ getPageTypeName(page.type) }}</span>
            <span class="word-count">{{ page.content.length }} 字</span>
          </div>
          <div class="outline-page-card-content">{{ page.content }}</div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
/**
 * 大纲查看模态框组件
 *
 * 以卡片形式展示大纲的每一页内容，包含：
 * - 页码标识
 * - 页面类型（封面/内容/总结）
 * - 字数统计
 * - 完整内容
 */

// 定义页面类型
interface Page {
  type: 'cover' | 'content' | 'summary'
  content: string
}

// 定义 Props
defineProps<{
  visible: boolean
  pages: Page[] | null
}>()

// 定义 Emits
defineEmits<{
  (e: 'close'): void
}>()

/**
 * 获取页面类型的中文名称
 */
function getPageTypeName(type: string): string {
  const names: Record<string, string> = {
    cover: '封面',
    content: '内容',
    summary: '总结'
  }
  return names[type] || '内容'
}
</script>

<style scoped>
/* 模态框遮罩层 */
.outline-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.6);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-7);
  animation: overlay-fade 0.2s var(--ease-out);
}

/* 模态框内容容器 */
.outline-modal-content {
  background: var(--bg-card);
  width: 100%;
  max-width: 800px;
  max-height: 85vh;
  border-radius: var(--radius-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
  box-shadow: var(--shadow-lg);
  animation: modal-pop 0.2s var(--ease-out);
}

@keyframes overlay-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.97) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

/* 模态框头部 */
.outline-modal-header {
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
  flex-shrink: 0;
}

.outline-modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

/* 关闭按钮 */
.close-icon {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 2px 6px;
  line-height: 1;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-icon:hover {
  color: var(--text-main);
  background: var(--gray-2);
}

/* 模态框主体（可滚动） */
.outline-modal-body {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  background: var(--gray-1);
}

/* 大纲页面卡片 */
.outline-page-card {
  background: var(--bg-card);
  border-radius: var(--radius-md);
  padding: var(--space-5);
  margin-bottom: var(--space-4);
  border: 1px solid var(--border-color);
  transition: box-shadow var(--transition-base), border-color var(--transition-base);
  box-shadow: var(--shadow-xs);
}

.outline-page-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--border-hover);
}

.outline-page-card:last-child {
  margin-bottom: 0;
}

/* 卡片头部 */
.outline-page-card-header {
  display: flex;
  align-items: center;
  gap: 10px;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-4);
  border-bottom: 1px solid var(--border-color);
}

/* 页码标识 */
.page-badge {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  min-width: 36px;
  height: 24px;
  padding: 0 8px;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: var(--radius-xs);
  font-size: 12px;
  font-weight: 700;
  font-family: var(--font-mono);
}

/* 页面类型标识：语义 -soft 底 + 语义色文字 */
.page-type-badge {
  display: inline-flex;
  align-items: center;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 600;
  background: var(--gray-2);
  color: var(--text-sub);
}

.page-type-badge.cover {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.page-type-badge.content {
  background: var(--gray-2);
  color: var(--text-sub);
}

.page-type-badge.summary {
  background: var(--color-success-soft);
  color: var(--color-success);
}

/* 字数统计 */
.word-count {
  margin-left: auto;
  font-size: 11px;
  color: var(--text-secondary);
}

/* 卡片内容 */
.outline-page-card-content {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-sub);
  white-space: pre-wrap;
  word-break: break-word;
  font-family: var(--font-sans);
}

/* 响应式布局：移动端改为底部抽屉 */
@media (max-width: 768px) {
  .outline-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .outline-modal-content {
    max-width: none;
    max-height: 90vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    animation: sheet-up 0.25s var(--ease-out);
  }

  .outline-modal-header {
    padding: var(--space-4) var(--space-5);
  }

  .outline-modal-body {
    padding: var(--space-4) var(--space-5);
  }
}

@keyframes sheet-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
