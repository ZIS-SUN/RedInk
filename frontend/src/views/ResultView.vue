<template>
  <div class="container">
    <StepIndicator :current="4" />

    <div class="page-header">
      <div>
        <h1 class="page-title">创作完成</h1>
        <p class="page-subtitle">恭喜！你的小红书图文已生成完毕，共 {{ store.images.length }} 张，当前作品已保存到历史记录</p>
        <!-- 作品评分：点星保存，再点同一颗星清除 -->
        <div v-if="store.recordId" class="rating-row" role="group" aria-label="为这次生成质量打分">
          <span class="rating-label">这次生成质量</span>
          <button
            v-for="star in 5"
            :key="star"
            type="button"
            class="star-btn"
            :class="{ filled: rating !== null && star <= rating }"
            :disabled="ratingSaving"
            :aria-pressed="rating !== null && star <= rating"
            :title="rating === star ? '再点一次清除评分' : `${star} 星`"
            :aria-label="rating === star ? '清除评分' : `${star} 星`"
            @click="handleRate(star)"
          >
            <svg width="16" height="16" viewBox="0 0 24 24" :fill="rating !== null && star <= rating ? 'currentColor' : 'none'" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          </button>
        </div>
      </div>
      <div style="display: flex; gap: 12px;">
        <button class="btn btn-secondary" @click="showResetConfirm = true">
          再来一篇
        </button>
        <button class="btn btn-secondary" @click="router.push('/tools/export')">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><path d="M9 3v18"></path><path d="M3 9h6"></path></svg>
          多尺寸导出
        </button>
        <button class="btn btn-primary" @click="downloadAll" :disabled="isDownloadingAll">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          {{ isDownloadingAll ? '下载中…' : '一键下载' }}
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
                title="编辑此页文字"
                @click="openEditModal(image)"
                :disabled="regeneratingIndex !== null"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"></path></svg>
                编辑文字
              </button>
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
                class="action-link action-link--primary"
                title="下载此图"
                @click="downloadOne(image)"
              >
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
                下载
              </button>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 标题、文案、标签生成区域 -->
    <ContentDisplay />

    <ReviewPanel />

    <!-- 发布前检查：与爆款体检并列（体检管内容好不好，检查管发布合不合规） -->
    <ChecklistPanel />

    <!-- 编辑单页文字弹窗 -->
    <EditPageTextModal
      :visible="editingIndex !== null"
      :page-index="editingIndex ?? 0"
      :initial-content="editingContent"
      @cancel="editingIndex = null"
      @save="handleSaveText"
      @save-and-regenerate="handleSaveAndRegenerate"
    />

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
/* 成品展示卡：比过程页更大的圆角与静置阴影，突出"成品感" */
.image-card {
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.image-card:hover {
  box-shadow: var(--shadow-hover);
}

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

/* 作品评分：克制的星级行，复用语义 warning 色 */
.rating-row {
  display: flex;
  align-items: center;
  gap: 2px;
  margin-top: 8px;
}

.rating-label {
  font-size: 12px;
  color: var(--text-sub);
  margin-right: 6px;
}

.star-btn {
  border: none;
  background: none;
  padding: 2px;
  line-height: 0;
  cursor: pointer;
  color: var(--gray-4);
  transition: color var(--transition-fast), transform var(--transition-fast);
}

.star-btn:hover:not(:disabled) {
  color: var(--color-warning);
  transform: scale(1.12);
}

.star-btn.filled {
  color: var(--color-warning);
}

.star-btn:disabled {
  cursor: default;
  opacity: 0.6;
}

@media (prefers-reduced-motion: reduce) {
  .star-btn:hover:not(:disabled) {
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

/* 主操作（下载）：品牌色常显，形成操作层级 */
.action-link--primary {
  color: var(--primary);
  font-weight: 600;
}

.action-link--primary:hover:not(:disabled) {
  color: var(--primary-hover);
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
import { computed, onMounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore, type GeneratedImage } from '../stores/generator'
import { getHistory, regenerateImage, updateHistory, updateHistoryRating } from '../api'
import { buildEditTrace, resolveNextRating } from '../utils/contentEdit'
import ContentDisplay from '../components/result/ContentDisplay.vue'
import ReviewPanel from '../components/result/ReviewPanel.vue'
import ChecklistPanel from '../components/result/ChecklistPanel.vue'
import EditPageTextModal from '../components/result/EditPageTextModal.vue'
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

// ==================== 作品评分 ====================
// 当前评分（null 表示未评分）；挂载时从历史记录回显
const rating = ref<number | null>(null)
const ratingSaving = ref(false)

onMounted(async () => {
  if (!store.recordId) return
  const res = await getHistory(store.recordId)
  if (res.success && res.record) {
    rating.value = res.record.rating ?? null
  }
})

// 点星保存、再点同一颗星清除；乐观更新，失败回滚并提示
const handleRate = async (star: number) => {
  if (!store.recordId || ratingSaving.value) return
  const prev = rating.value
  rating.value = resolveNextRating(prev, star)
  ratingSaving.value = true
  const res = await updateHistoryRating(store.recordId, rating.value)
  ratingSaving.value = false
  if (!res.success) {
    rating.value = prev
    error.value = normalizeApiError(res.error || res.error_message || '保存评分失败', '保存评分失败')
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

const downloadOne = (image: GeneratedImage) => {
  if (image.url) {
    const link = document.createElement('a')
    const baseUrl = image.url.split('?')[0]
    link.href = baseUrl + '?thumbnail=false'
    link.download = `rednote_page_${image.index + 1}.png`
    link.click()
  }
}

// 批量下载进行中标志：无 recordId 时逐张定时下载耗时较长，防止连点叠加触发
const isDownloadingAll = ref(false)

const downloadAll = () => {
  if (store.recordId) {
    const link = document.createElement('a')
    link.href = `/api/history/${store.recordId}/download`
    link.click()
  } else {
    if (isDownloadingAll.value) return
    const downloadable = store.images.filter(image => image.url)
    if (downloadable.length === 0) return

    isDownloadingAll.value = true
    downloadable.forEach((image, index) => {
      setTimeout(() => {
        const link = document.createElement('a')
        const baseUrl = image.url.split('?')[0]
        link.href = baseUrl + '?thumbnail=false'
        link.download = `rednote_page_${image.index + 1}.png`
        link.click()
        // 最后一张触发后解除下载中状态
        if (index === downloadable.length - 1) {
          isDownloadingAll.value = false
        }
      }, index * 300)
    })
  }
}

// 重画指定索引的页面（「重新生成」按钮与编辑弹窗「保存并重画」共用）
const regeneratePage = async (index: number) => {
  if (!store.taskId || regeneratingIndex.value !== null) return

  regeneratingIndex.value = index
  try {
    // Find the page content from outline
    const pageContent = store.outline.pages.find(p => p.index === index)
    if (!pageContent) {
       error.value = normalizeApiError('无法找到对应页面的内容', '无法重新生成')
       return
    }

    // 构建上下文信息
    const context = {
      fullOutline: store.outline.raw || '',
      userTopic: store.topic || '',
      recordId: store.recordId,
      // 重绘沿用本次生成记录在 store 中的风格提示词（API 层不再兜底读 store）
      stylePrompt: store.stylePrompt
    }

    const result = await regenerateImage(store.taskId, pageContent, true, context)
    if (result.success && result.image_url) {
       const newUrl = result.image_url
       store.updateImage(index, newUrl)
    } else {
       error.value = normalizeApiError(result.error || result.error_message || '重新生成失败', '重新生成失败')
    }
  } catch (e: unknown) {
    error.value = normalizeApiError(e, '重新生成失败')
  } finally {
    regeneratingIndex.value = null
  }
}

const handleRegenerate = (image: GeneratedImage) => regeneratePage(image.index)

// ==================== 编辑文字弹窗 ====================
// 当前正在编辑的页面索引（null 表示弹窗关闭）
const editingIndex = ref<number | null>(null)

// 弹窗初始文案：取该页最新的 outline content
const editingContent = computed(() => {
  if (editingIndex.value === null) return ''
  return store.outline.pages.find(p => p.index === editingIndex.value)?.content ?? ''
})

const openEditModal = (image: GeneratedImage) => {
  // 有页面在重画时禁止打开编辑（与并发重画的互斥保持一致）
  if (regeneratingIndex.value !== null) return
  const page = store.outline.pages.find(p => p.index === image.index)
  if (!page) {
    error.value = normalizeApiError('无法找到对应页面的内容', '无法编辑')
    return
  }
  editingIndex.value = image.index
}

// 保存文案到 store，并在有历史记录时同步大纲到服务器
const savePageText = async (index: number, content: string) => {
  // 更新 store 前捕获该页原文，用于编辑留痕（AI 原文 → 用户终稿）
  const originalText = store.outline.pages.find(p => p.index === index)?.content ?? ''
  store.updatePage(index, content)
  if (store.recordId) {
    const trace = buildEditTrace(index, originalText, content, 'manual')
    // 同步失败不阻断本地编辑（store 已持久化到 localStorage）
    await updateHistory(store.recordId, {
      outline: { raw: store.outline.raw, pages: store.outline.pages },
      ...(trace ? { edit_trace: trace } : {})
    })
  }
}

const handleSaveText = async (content: string) => {
  if (editingIndex.value === null) return
  const index = editingIndex.value
  editingIndex.value = null
  await savePageText(index, content)
}

const handleSaveAndRegenerate = async (content: string) => {
  if (editingIndex.value === null) return
  const index = editingIndex.value
  editingIndex.value = null
  await savePageText(index, content)
  await regeneratePage(index)
}
</script>
