<template>
  <div class="container">
    <StepIndicator :current="4" />

    <div class="page-header">
      <div>
        <h1 class="page-title">创作完成</h1>
        <p class="page-subtitle">恭喜！你的小红书图文已生成完毕，共 {{ store.images.length }} 张，当前作品已保存到历史记录</p>
      </div>
      <div style="display: flex; gap: 12px;">
        <button class="btn btn-secondary" @click="showResetConfirm = true">
          再来一篇
        </button>
        <button class="btn btn-primary" @click="downloadAll">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          一键下载
        </button>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      :error="error"
      dismissible
      style="margin-bottom: 16px;"
      @dismiss="error = null"
    />

    <div class="card">
      <div class="grid-cols-4">
        <div v-for="image in store.images" :key="image.index" class="image-card group">
          <!-- Image Area -->
          <div
            v-if="image.url"
            style="position: relative; aspect-ratio: 3/4; overflow: hidden; cursor: pointer;"
            @click="viewImage(image.url)"
          >
            <img
              :src="image.url"
              :alt="`第 ${image.index + 1} 页`"
              loading="lazy"
              style="width: 100%; height: 100%; object-fit: cover; transition: transform 0.3s var(--ease-out);"
              @error="onImgError"
            />
            <!-- Regenerating Overlay -->
            <div v-if="regeneratingIndex === image.index" style="position: absolute; inset: 0; background: rgba(255,255,255,0.8); display: flex; flex-direction: column; align-items: center; justify-content: center; z-index: 10;">
               <div class="spinner" style="width: 24px; height: 24px; border-width: 2px; border-color: var(--primary); border-top-color: transparent;"></div>
               <span style="font-size: 12px; color: var(--primary); margin-top: 8px; font-weight: 600;">重新生成中…</span>
            </div>

            <!-- Hover Overlay -->
            <div v-else style="position: absolute; inset: 0; background: rgba(33,30,27,0.4); opacity: 0; transition: opacity var(--transition-fast); display: flex; align-items: center; justify-content: center; color: white; font-weight: 600;" class="hover-overlay">
              预览大图
            </div>
          </div>

          <!-- Action Bar（常显操作栏，触屏可达） -->
          <div style="padding: 12px; border-top: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: center;">
            <span style="font-size: 12px; color: var(--text-sub);">第 {{ image.index + 1 }} 页</span>
            <div style="display: flex; gap: 10px; align-items: center;">
              <button
                class="action-link"
                title="重新生成此图"
                @click="handleRegenerate(image)"
                :disabled="regeneratingIndex === image.index"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M23 4v6h-6"></path><path d="M1 20v-6h6"></path><path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"></path></svg>
                {{ regeneratingIndex === image.index ? '重新生成中…' : '重新生成' }}
              </button>
              <button
                style="border: none; background: none; color: var(--primary); cursor: pointer; font-size: 12px;"
                @click="downloadOne(image)"
              >
                下载
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 标题、文案、标签生成区域 -->
    <ContentDisplay />

    <!-- 再来一篇确认 -->
    <ConfirmDialog
      :visible="showResetConfirm"
      title="开始新的创作？"
      message="当前作品已保存到历史记录，随时可以在「我的创作」中找回。继续将清空当前工作区。"
      confirm-text="再来一篇"
      @confirm="startOver"
      @cancel="showResetConfirm = false"
    />
  </div>
</template>

<style scoped>
/* 确保图片预览区域正确填充 */
.image-card > div:first-child {
  flex: 1;
  display: flex;
  flex-direction: column;
}

.image-card:hover .hover-overlay {
  opacity: 1;
}
/* 克制的图片缩放反馈（原 1.05 过于浮夸） */
.image-card:hover img {
  transform: scale(1.02);
}

@media (prefers-reduced-motion: reduce) {
  .image-card:hover img {
    transform: none;
  }
}

.action-link {
  border: none;
  background: none;
  color: var(--text-sub);
  cursor: pointer;
  display: flex;
  align-items: center;
  gap: 4px;
  font-size: 12px;
  padding: 0;
  transition: color var(--transition-fast);
}

.action-link:hover:not(:disabled) {
  color: var(--primary);
}

.action-link:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

/* 移动端适配 */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }
}
</style>

<script setup lang="ts">
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { regenerateImage } from '../api'
import ContentDisplay from '../components/result/ContentDisplay.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import StepIndicator from './shared/StepIndicator.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import { normalizeApiError, type AppError } from '../utils/errors'

const router = useRouter()
const store = useGeneratorStore()
const regeneratingIndex = ref<number | null>(null)
const error = ref<AppError | null>(null)
const showResetConfirm = ref(false)

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

const viewImage = (url: string) => {
  const baseUrl = url.split('?')[0]
  window.open(baseUrl + '?thumbnail=false', '_blank')
}

const startOver = () => {
  showResetConfirm.value = false
  store.reset()
  router.push('/')
}

const downloadOne = (image: any) => {
  if (image.url) {
    const link = document.createElement('a')
    const baseUrl = image.url.split('?')[0]
    link.href = baseUrl + '?thumbnail=false'
    link.download = `rednote_page_${image.index + 1}.png`
    link.click()
  }
}

const downloadAll = () => {
  if (store.recordId) {
    const link = document.createElement('a')
    link.href = `/api/history/${store.recordId}/download`
    link.click()
  } else {
    store.images.forEach((image, index) => {
      if (image.url) {
        setTimeout(() => {
          const link = document.createElement('a')
          const baseUrl = image.url.split('?')[0]
          link.href = baseUrl + '?thumbnail=false'
          link.download = `rednote_page_${image.index + 1}.png`
          link.click()
        }, index * 300)
      }
    })
  }
}

const handleRegenerate = async (image: any) => {
  if (!store.taskId || regeneratingIndex.value !== null) return

  regeneratingIndex.value = image.index
  try {
    // Find the page content from outline
    const pageContent = store.outline.pages.find(p => p.index === image.index)
    if (!pageContent) {
       error.value = normalizeApiError('无法找到对应页面的内容', '无法重新生成')
       return
    }

    // 构建上下文信息
    const context = {
      fullOutline: store.outline.raw || '',
      userTopic: store.topic || '',
      recordId: store.recordId
    }

    const result = await regenerateImage(store.taskId, pageContent, true, context)
    if (result.success && result.image_url) {
       const newUrl = result.image_url
       store.updateImage(image.index, newUrl)
    } else {
       error.value = normalizeApiError(result.error || result.error_message || '重新生成失败', '重新生成失败')
    }
  } catch (e: any) {
    error.value = normalizeApiError(e, '重新生成失败')
  } finally {
    regeneratingIndex.value = null
  }
}
</script>
