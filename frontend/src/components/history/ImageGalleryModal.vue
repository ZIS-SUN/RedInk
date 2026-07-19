<template>
  <!-- 图片画廊模态框 -->
  <div v-if="visible && record" class="modal-fullscreen" @click="$emit('close')">
    <div class="modal-body" @click.stop>
      <!-- 头部区域 -->
      <div class="modal-header">
        <div style="flex: 1;">
          <!-- 标题区域 -->
          <div class="title-section">
            <h3
              class="modal-title"
              :class="{ 'collapsed': !titleExpanded && record.title.length > 80 }"
            >
              {{ record.title }}
            </h3>
            <button
              v-if="record.title.length > 80"
              class="title-expand-btn"
              @click="titleExpanded = !titleExpanded"
            >
              {{ titleExpanded ? '收起' : '展开' }}
            </button>
          </div>

          <div class="modal-meta">
            <span>{{ record.outline.pages.length }} 张图片 · {{ formattedDate }}</span>
            <button
              class="view-outline-btn"
              @click="$emit('showOutline')"
              title="查看完整大纲"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path>
                <polyline points="14 2 14 8 20 8"></polyline>
                <line x1="16" y1="13" x2="8" y2="13"></line>
                <line x1="16" y1="17" x2="8" y2="17"></line>
              </svg>
              查看大纲
            </button>
          </div>
        </div>

        <div class="header-actions">
          <button class="btn download-btn" @click="$emit('downloadAll')">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path>
              <polyline points="7 10 12 15 17 10"></polyline>
              <line x1="12" y1="15" x2="12" y2="3"></line>
            </svg>
            打包下载
          </button>
          <button class="close-icon" @click="$emit('close')">×</button>
        </div>
      </div>

      <!-- 图片网格 -->
      <div class="modal-gallery-grid">
        <div
          v-for="(img, idx) in record.images.generated"
          :key="idx"
          class="modal-img-item"
        >
          <div
            class="modal-img-preview"
            v-if="img"
            :class="{ 'regenerating': regeneratingImages.has(idx) }"
          >
            <img
              :src="`/api/images/${record.images.task_id}/${img}`"
              loading="lazy"
              decoding="async"
              @error="onImgError"
            />
            <div class="modal-img-overlay">
              <button
                class="modal-overlay-btn"
                @click="$emit('regenerate', idx)"
                :disabled="regeneratingImages.has(idx)"
              >
                <svg class="regenerate-icon" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 4v6h-6"></path>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>
                {{ regeneratingImages.has(idx) ? '重新生成中…' : '重新生成' }}
              </button>
            </div>
          </div>
          <div class="placeholder" v-else>等待生成…</div>

          <div class="img-footer">
            <span>第 {{ idx + 1 }} 页</span>
            <span v-if="img" class="footer-links">
              <!-- 常显重新生成入口（触屏可达） -->
              <button
                class="regen-link"
                :disabled="regeneratingImages.has(idx)"
                @click="$emit('regenerate', idx)"
              >
                {{ regeneratingImages.has(idx) ? '重新生成中…' : '重新生成' }}
              </button>
              <span
                class="download-link"
                @click="$emit('download', img, idx)"
              >
                下载
              </span>
            </span>
          </div>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'

/**
 * 图片画廊模态框组件
 *
 * 功能：
 * - 展示历史记录的所有生成图片
 * - 支持重新生成单张图片
 * - 支持下载单张/全部图片
 * - 可展开查看完整大纲
 */

// 定义记录类型
interface ViewingRecord {
  id: string
  title: string
  updated_at: string
  outline: {
    raw: string
    pages: Array<{ type: string; content: string }>
  }
  images: {
    task_id: string
    generated: string[]
  }
}

// 定义 Props
const props = defineProps<{
  visible: boolean
  record: ViewingRecord | null
  regeneratingImages: Set<number>
}>()

// 定义 Emits
defineEmits<{
  (e: 'close'): void
  (e: 'showOutline'): void
  (e: 'downloadAll'): void
  (e: 'download', filename: string, index: number): void
  (e: 'regenerate', index: number): void
}>()

// 标题展开状态
const titleExpanded = ref(false)

// 图片加载失败兜底占位（任务目录被清理时避免裸 404 图标）
const FALLBACK_IMG =
  'data:image/svg+xml;utf8,' +
  encodeURIComponent(
    '<svg xmlns="http://www.w3.org/2000/svg" width="300" height="400" viewBox="0 0 300 400"><rect width="300" height="400" fill="#f5f5f5"/><text x="150" y="190" text-anchor="middle" font-size="16" fill="#999" font-family="sans-serif">图片加载失败</text><text x="150" y="216" text-anchor="middle" font-size="12" fill="#bbb" font-family="sans-serif">文件可能已被清理</text></svg>'
  )

function onImgError(e: Event) {
  const img = e.target as HTMLImageElement
  if (img.src !== FALLBACK_IMG) {
    img.src = FALLBACK_IMG
  }
}

// 格式化日期
const formattedDate = computed(() => {
  if (!props.record) return ''
  const d = new Date(props.record.updated_at)
  return `${d.getMonth() + 1}/${d.getDate()}`
})
</script>

<style scoped>
/* 全屏模态框遮罩 */
.modal-fullscreen {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.72);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 999;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-7);
  animation: overlay-fade 0.2s var(--ease-out);
}

/* 模态框主体 */
.modal-body {
  background: var(--bg-card);
  width: 100%;
  max-width: 1000px;
  height: 90vh;
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  display: flex;
  flex-direction: column;
  overflow: hidden;
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

/* 头部区域 */
.modal-header {
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  flex-shrink: 0;
  gap: var(--space-5);
}

/* 标题区域 */
.title-section {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-1);
}

.modal-title {
  flex: 1;
  margin: 0;
  font-size: 18px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  line-height: 1.4;
  color: var(--text-main);
  word-break: break-word;
  transition: max-height var(--transition-slow);
}

.modal-title.collapsed {
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
  text-overflow: ellipsis;
}

.title-expand-btn {
  flex-shrink: 0;
  padding: 2px 8px;
  background: var(--gray-2);
  border: none;
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-size: 11px;
  font-family: inherit;
  color: var(--text-sub);
  transition: background var(--transition-fast), color var(--transition-fast);
  margin-top: 2px;
}

.title-expand-btn:hover {
  background: var(--gray-3);
  color: var(--text-main);
}

/* 元信息 */
.modal-meta {
  font-size: 12px;
  color: var(--text-secondary);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-2);
}

/* 查看大纲按钮 */
.view-outline-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 4px 10px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xs);
  cursor: pointer;
  font-size: 12px;
  font-family: inherit;
  color: var(--text-sub);
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.view-outline-btn:hover {
  background: var(--gray-1);
  color: var(--text-main);
  border-color: var(--border-hover);
}

/* 头部操作区 */
.header-actions {
  display: flex;
  gap: var(--space-3);
  align-items: center;
}

.download-btn {
  padding: 8px 16px;
  font-size: 14px;
  display: flex;
  align-items: center;
  gap: 6px;
  border: 1px solid var(--border-hover);
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.download-btn:hover {
  background: var(--gray-0);
  border-color: var(--gray-5);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.download-btn:active {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

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

/* 图片网格 */
.modal-gallery-grid {
  flex: 1;
  overflow-y: auto;
  padding: var(--space-5);
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(200px, 1fr));
  gap: var(--space-5);
}

/* 单个图片项 */
.modal-img-item {
  display: flex;
  flex-direction: column;
}

/* 图片预览容器 */
.modal-img-preview {
  position: relative;
  width: 100%;
  aspect-ratio: 3/4;
  overflow: hidden;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  contain: layout style paint;
}

.modal-img-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

/* 悬浮遮罩 */
.modal-img-overlay {
  position: absolute;
  inset: 0;
  background: rgba(33, 30, 27, 0.48);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast);
  pointer-events: none;
  will-change: opacity;
}

.modal-img-preview:hover .modal-img-overlay {
  opacity: 1;
  pointer-events: auto;
}

/* 触屏设备没有 hover：隐藏遮罩，操作依赖底部常显按钮 */
@media (hover: none) {
  .modal-img-overlay {
    display: none;
  }
}

/* 重绘中状态 */
.modal-img-preview.regenerating .modal-img-overlay {
  opacity: 1;
  pointer-events: auto;
}

.modal-img-preview.regenerating .regenerate-icon {
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 遮罩层按钮 */
.modal-overlay-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  font-size: 13px;
  font-family: inherit;
  font-weight: 500;
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
  transition: background var(--transition-fast), color var(--transition-fast),
    transform var(--transition-fast), box-shadow var(--transition-fast);
  will-change: transform;
}

.modal-overlay-btn:hover {
  background: var(--primary);
  color: white;
  transform: translateY(-1px);
  box-shadow: var(--shadow-md);
}

.modal-overlay-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

/* 占位符 */
.placeholder {
  width: 100%;
  aspect-ratio: 3/4;
  background: var(--gray-1);
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-sm);
  display: flex;
  align-items: center;
  justify-content: center;
  color: var(--text-secondary);
  font-size: 14px;
}

/* 图片底部信息 */
.img-footer {
  margin-top: var(--space-2);
  display: flex;
  justify-content: space-between;
  font-size: 12px;
  color: var(--text-secondary);
}

.footer-links {
  display: inline-flex;
  align-items: center;
  gap: 10px;
}

.regen-link {
  border: none;
  background: none;
  padding: 0;
  font-size: 12px;
  font-family: inherit;
  color: var(--text-sub);
  cursor: pointer;
  transition: color var(--transition-fast);
}

.regen-link:hover:not(:disabled) {
  color: var(--primary);
}

.regen-link:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.download-link {
  cursor: pointer;
  color: var(--primary);
  transition: color var(--transition-fast);
}

.download-link:hover {
  color: var(--primary-hover);
}

/* 响应式：移动端改为底部抽屉，最大化利用屏幕 */
@media (max-width: 768px) {
  .modal-fullscreen {
    padding: 0;
    align-items: flex-end;
  }

  .modal-body {
    max-width: none;
    height: 94vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    animation: sheet-up 0.25s var(--ease-out);
  }

  .modal-header {
    padding: var(--space-4) var(--space-5);
  }

  .modal-gallery-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: var(--space-3);
    padding: var(--space-3);
  }
}

@keyframes sheet-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
