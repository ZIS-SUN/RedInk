<template>
  <!-- 历史记录卡片 -->
  <div class="gallery-card">
    <!-- 封面区域 -->
    <div class="card-cover" @click="$emit('preview', record.id)">
      <img
        v-if="record.thumbnail && record.task_id"
        :src="`/api/images/${record.task_id}/${record.thumbnail}`"
        alt="cover"
        loading="lazy"
        decoding="async"
      />
      <div v-else class="cover-placeholder">
        <span>{{ record.title.charAt(0) }}</span>
      </div>

      <!-- 悬浮操作按钮 -->
      <div class="card-overlay">
        <button class="overlay-btn" @click.stop="$emit('preview', record.id)">
          预览
        </button>
        <button class="overlay-btn primary" @click.stop="$emit('edit', record.id)">
          编辑
        </button>
      </div>

      <!-- 状态标识 -->
      <div class="status-badge" :class="record.status">
        {{ statusText }}
      </div>
    </div>

    <!-- 底部信息 -->
    <div class="card-footer">
      <div class="card-title" :title="record.title">{{ record.title }}</div>
      <div class="card-meta">
        <span>{{ record.page_count }}P</span>
        <span class="dot">·</span>
        <span>{{ formattedDate }}</span>
        <!-- 作品评分：有 rating 才显示星标 -->
        <span v-if="record.rating" class="rating-badge" :title="`已评 ${record.rating} 星`">
          <svg width="11" height="11" viewBox="0 0 24 24" fill="currentColor" stroke="currentColor" stroke-width="1" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          {{ record.rating }}
        </span>

        <!-- 常显操作区（触屏可达，不依赖 hover 遮罩） -->
        <div class="footer-actions">
          <button class="footer-edit-btn" @click.stop="$emit('edit', record.id)">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"></path>
              <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"></path>
            </svg>
            编辑
          </button>
          <button class="more-btn" @click.stop="$emit('delete', record)" title="删除" aria-label="删除">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="3 6 5 6 21 6"></polyline>
              <path d="M19 6v14a2 2 0 0 1-2 2H7a2 2 0 0 1-2-2V6m3 0V4a2 2 0 0 1 2-2h4a2 2 0 0 1 2 2v2"></path>
            </svg>
          </button>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'

/**
 * 历史记录卡片组件
 *
 * 展示单个历史记录的封面、标题、状态等信息
 * 支持预览、编辑、删除操作
 */

// 定义记录类型
interface GalleryRecord {
  id: string
  title: string
  status: string
  page_count: number
  updated_at: string
  thumbnail?: string | null
  task_id?: string | null
  /** 作品评分（1-5）；旧记录/未评分时缺失或为 null */
  rating?: number | null
}

// 定义 Props
const props = defineProps<{
  record: GalleryRecord
}>()

// 定义 Emits
defineEmits<{
  (e: 'preview', id: string): void
  (e: 'edit', id: string): void
  (e: 'delete', record: GalleryRecord): void
}>()

/**
 * 获取状态文本
 */
const statusText = computed(() => {
  const map: Record<string, string> = {
    draft: '草稿',
    completed: '已完成',
    generating: '生成中',
    partial: '部分完成',
    error: '生成失败'
  }
  return map[props.record.status] || props.record.status
})

/**
 * 格式化日期
 */
const formattedDate = computed(() => {
  const d = new Date(props.record.updated_at)
  return `${d.getMonth() + 1}/${d.getDate()}`
})
</script>

<style scoped>
/* 卡片容器 */
.gallery-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-xs);
  transition: transform var(--transition-base),
              box-shadow var(--transition-base),
              border-color var(--transition-base);
  position: relative;
  will-change: transform;
  contain: layout style paint;
}

.gallery-card:hover {
  transform: translateY(-3px) translateZ(0);
  border-color: var(--border-hover);
  box-shadow: var(--shadow-hover);
}

.gallery-card:active {
  transform: translateY(-1px) translateZ(0);
  box-shadow: var(--shadow-sm);
}

/* 封面区域 */
.card-cover {
  aspect-ratio: 3/4;
  background: var(--gray-1);
  position: relative;
  overflow: hidden;
  cursor: pointer;
}

.card-cover img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  transition: transform 0.4s var(--ease-out);
  will-change: transform;
  backface-visibility: hidden;
}

.gallery-card:hover .card-cover img {
  transform: scale(1.04) translateZ(0);
}

/* 封面占位符 */
.cover-placeholder {
  width: 100%;
  height: 100%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 48px;
  color: var(--gray-4);
  font-weight: 800;
  background: var(--gray-1);
}

/* 悬浮遮罩层 */
.card-overlay {
  position: absolute;
  inset: 0;
  background: rgba(33, 30, 27, 0.42);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  opacity: 0;
  transition: opacity var(--transition-base);
  -webkit-backdrop-filter: blur(2px);
  backdrop-filter: blur(2px);
  pointer-events: none;
  will-change: opacity;
}

.gallery-card:hover .card-overlay {
  opacity: 1;
  pointer-events: auto;
}

/* 触屏设备没有 hover：隐藏遮罩，操作依赖底部常显按钮 */
@media (hover: none) {
  .card-overlay {
    display: none;
  }
}

/* 遮罩层按钮 */
.overlay-btn {
  padding: 8px 24px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(255, 255, 255, 0.8);
  background: rgba(255, 255, 255, 0.18);
  color: white;
  font-size: 14px;
  font-family: inherit;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    transform var(--transition-fast);
  will-change: transform;
}

.overlay-btn:hover {
  background: white;
  color: var(--text-main);
  transform: translateY(-2px);
}

.overlay-btn.primary {
  background: var(--primary);
  border-color: var(--primary);
}

.overlay-btn.primary:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  color: white;
}

/* 状态标识：语义 -soft 底 + 语义色文字，细白描边使徽章浮于任意封面之上 */
.status-badge {
  position: absolute;
  top: 12px;
  left: 12px;
  padding: 4px 10px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  background: rgba(255, 255, 255, 0.92);
  color: var(--text-sub);
  -webkit-backdrop-filter: blur(4px);
  backdrop-filter: blur(4px);
  box-shadow: var(--shadow-xs), inset 0 0 0 1px rgba(255, 255, 255, 0.4);
}

.status-badge.completed {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.status-badge.draft {
  background: var(--gray-2);
  color: var(--text-sub);
}

.status-badge.generating {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.status-badge.partial {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.status-badge.error {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

/* 底部区域 */
.card-footer {
  padding: var(--space-4);
}

.card-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  margin-bottom: var(--space-2);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  color: var(--text-main);
}

.card-meta {
  display: flex;
  align-items: center;
  font-size: 12px;
  color: var(--text-secondary);
}

.dot {
  margin: 0 6px;
}

/* 作品评分星标：语义 warning 色，与状态徽章同为轻量提示 */
.rating-badge {
  display: inline-flex;
  align-items: center;
  gap: 2px;
  margin-left: 6px;
  color: var(--color-warning);
  font-weight: 600;
  font-variant-numeric: tabular-nums;
}

/* 常显操作区 */
.footer-actions {
  margin-left: auto;
  display: flex;
  align-items: center;
  gap: 6px;
}

.footer-edit-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast), box-shadow var(--transition-fast);
}

.footer-edit-btn:hover {
  border-color: var(--border-hover);
  color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-xs);
}

.more-btn {
  background: none;
  border: none;
  color: var(--text-placeholder);
  cursor: pointer;
  padding: 4px;
  border-radius: var(--radius-xs);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.more-btn:hover {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}
</style>
