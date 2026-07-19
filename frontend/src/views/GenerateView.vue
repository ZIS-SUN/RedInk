<template>
  <div class="container">
    <StepIndicator :current="3" />

    <div class="page-header">
      <div>
        <h1 class="page-title">{{ isDone ? '生成完成' : '正在生成' }}</h1>
        <p class="page-subtitle">
          <span v-if="isGenerating">正在生成第 {{ store.progress.current + 1 }} / {{ store.progress.total }} 页</span>
          <span v-else-if="hasFailedImages">{{ failedCount }} 张图片生成失败，可重新生成</span>
          <span v-else>全部 {{ store.progress.total }} 张图片生成完成</span>
        </p>
      </div>
      <div style="display: flex; gap: 10px; flex-wrap: wrap;">
        <button
          v-if="hasFailedImages && !isGenerating"
          class="btn btn-primary"
          @click="retryAllFailed"
          :disabled="isRetrying"
        >
          {{ isRetrying ? '重新生成中…' : '重新生成失败图片' }}
        </button>
        <button
          v-if="isDone"
          class="btn btn-primary"
          @click="router.push('/result')"
        >
          查看结果
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-left: 6px;"><line x1="5" y1="12" x2="19" y2="12"></line><polyline points="12 5 19 12 12 19"></polyline></svg>
        </button>
        <button class="btn" @click="router.push('/outline')" style="border:1px solid var(--border-color)">
          返回大纲
        </button>
      </div>
    </div>

    <!-- 当前风格提示条：明确本次生成使用的风格 -->
    <div class="style-hint" :class="{ inactive: !activeStyle }" role="status">
      <template v-if="activeStyle">
        <span class="style-hint-colors" aria-hidden="true">
          <span
            v-for="color in activeStyle.colors.slice(0, 3)"
            :key="color"
            class="style-hint-color"
            :style="{ background: color }"
          />
        </span>
        <span>本次生成使用风格：<strong>{{ activeStyle.name }}</strong></span>
      </template>
      <template v-else>
        <span>未应用风格，</span>
        <RouterLink to="/tools/style" class="style-hint-link">去风格模板库选择</RouterLink>
      </template>
    </div>

    <div class="card">
      <div style="margin-bottom: 20px; display: flex; justify-content: space-between; align-items: center;">
        <span style="font-weight: 600;">生成进度</span>
        <span style="color: var(--primary); font-weight: 600;">{{ Math.round(progressPercent) }}%</span>
      </div>
      <div class="progress-container">
        <div class="progress-bar" :style="{ width: progressPercent + '%' }" />
      </div>

      <!-- 成功态：显式引导查看结果，不再强制自动跳转 -->
      <div v-if="isDone" class="success-banner" role="status" aria-live="polite">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        <span>全部图片生成完成，作品已保存到历史记录</span>
        <button class="btn btn-primary success-banner-btn" @click="router.push('/result')">
          查看结果
        </button>
      </div>

      <ErrorCard
        v-if="error"
        :error="error"
        dismissible
        style="margin-top: 18px;"
        @dismiss="error = null"
      />

      <div class="grid-cols-4" style="margin-top: 40px;">
        <div v-for="image in store.images" :key="image.index" class="image-card">
          <!-- 图片展示区域 -->
          <div v-if="image.url && image.status === 'done'" class="image-preview">
            <img
              :src="image.url"
              :alt="`第 ${image.index + 1} 页`"
              loading="lazy"
              @error="onImgError"
            />
            <!-- 重新生成按钮（悬停显示，触屏设备使用底部常显按钮） -->
            <div class="image-overlay">
              <button
                class="overlay-btn"
                @click="regenerateImage(image.index)"
              >
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                  <path d="M23 4v6h-6"></path>
                  <path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path>
                </svg>
                重新生成
              </button>
            </div>
          </div>

          <!-- 生成中/重试中状态 -->
          <div v-else-if="image.status === 'generating' || image.status === 'retrying'" class="image-placeholder">
            <div class="spinner"></div>
            <div class="status-text">{{ image.status === 'retrying' ? '重新生成中…' : '生成中...' }}</div>
          </div>

          <!-- 失败状态 -->
          <div v-else-if="image.status === 'error'" class="image-placeholder error-placeholder">
            <div class="error-icon">!</div>
            <div class="status-text">生成失败</div>
            <div v-if="image.error" class="image-error-text">{{ image.error }}</div>
            <button
              class="retry-btn"
              @click="retrySingleImage(image.index)"
              :disabled="isRetrying"
            >
              重新生成
            </button>
          </div>

          <!-- 等待中状态 -->
          <div v-else class="image-placeholder">
            <div class="status-text">等待生成…</div>
          </div>

          <!-- 底部信息栏（重新生成常显，触屏可达） -->
          <div class="image-footer">
            <span class="page-label">第 {{ image.index + 1 }} 页</span>
            <div class="footer-actions">
              <button
                v-if="image.url && image.status === 'done'"
                class="footer-regen-btn"
                @click="regenerateImage(image.index)"
              >
                重新生成
              </button>
              <span class="status-badge" :class="image.status">
                {{ getStatusText(image.status) }}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 生成中离开确认 -->
    <ConfirmDialog
      :visible="showLeaveConfirm"
      title="生成还在进行中"
      message="离开本页后，生成会在后台继续，稍后可在「我的创作」中查看进度和结果。"
      confirm-text="离开本页"
      cancel-text="留在本页"
      @confirm="confirmLeave"
      @cancel="cancelLeave"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, computed, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, onBeforeRouteLeave, RouterLink } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { useStyleLibrary } from '../composables/useStyleLibrary'
import ErrorCard from '../components/common/ErrorCard.vue'
import StepIndicator from './shared/StepIndicator.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import { useGenerationRunner } from '../composables/useGenerationRunner'
import { useImageRetry } from '../composables/useImageRetry'
import type { AppError } from '../utils/errors'

const router = useRouter()
const store = useGeneratorStore()
// 当前应用的风格（来自风格模板库），用于风格提示条
const { activeStyle } = useStyleLibrary()

const error = ref<AppError | null>(null)

const isGenerating = computed(() => store.progress.status === 'generating')

const progressPercent = computed(() => {
  if (store.progress.total === 0) return 0
  return (store.progress.current / store.progress.total) * 100
})

const hasFailedImages = computed(() => store.images.some(img => img.status === 'error'))

const failedCount = computed(() => store.images.filter(img => img.status === 'error').length)

// 全部完成且无失败：展示成功态与「查看结果」按钮
const isDone = computed(() =>
  store.progress.status === 'done' &&
  store.images.length > 0 &&
  !hasFailedImages.value
)

const getStatusText = (status: string) => {
  const texts: Record<string, string> = {
    generating: '生成中',
    done: '已完成',
    error: '失败',
    retrying: '重新生成中'
  }
  return texts[status] || '等待生成'
}

function setError(nextError: AppError | null) {
  error.value = nextError
}

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

const {
  isRetrying,
  regenerateImage,
  retryAllFailed,
  retrySingleImage
} = useImageRetry(setError)

const {
  cleanupGenerationRunner,
  startGenerationFlow
} = useGenerationRunner(hasFailedImages, setError)

// 完成后取消 runner 内部的 1 秒强制跳转，改为用户显式点击「查看结果」
watch(isDone, (done) => {
  if (done) {
    cleanupGenerationRunner()
  }
}, { immediate: true })

// ==================== 生成中离开确认 ====================
const showLeaveConfirm = ref(false)
let pendingLeavePath: string | null = null
let leaveConfirmed = false

onBeforeRouteLeave((to) => {
  if (!isGenerating.value || leaveConfirmed) return true
  pendingLeavePath = to.fullPath
  showLeaveConfirm.value = true
  return false
})

function confirmLeave() {
  showLeaveConfirm.value = false
  leaveConfirmed = true
  if (pendingLeavePath) {
    router.push(pendingLeavePath)
  }
}

function cancelLeave() {
  showLeaveConfirm.value = false
  pendingLeavePath = null
}

onMounted(startGenerationFlow)
onUnmounted(cleanupGenerationRunner)
</script>

<style scoped>
/* 当前风格提示条 */
.style-hint {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  max-width: 100%;
  margin-bottom: 16px;
  padding: 8px 14px;
  border-radius: var(--radius-sm, 8px);
  font-size: 13px;
  color: var(--color-info, #3b82f6);
  background: var(--color-info-soft, #dbeafe);
}

.style-hint.inactive {
  color: var(--text-sub, #666);
  background: var(--bg-card, #fff);
  border: 1px solid var(--border-color, #eee);
}

.style-hint-colors {
  display: inline-flex;
  gap: 4px;
}

.style-hint-color {
  width: 12px;
  height: 12px;
  border-radius: 50%;
  border: 1px solid rgba(0, 0, 0, 0.08);
}

.style-hint-link {
  color: var(--primary, #ff2442);
  font-weight: 600;
  text-decoration: none;
}

.style-hint-link:hover {
  text-decoration: underline;
}

.success-banner {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 12px 16px;
  border-radius: 8px;
  background: var(--color-success-soft, #f6ffed);
  color: var(--color-success, #52c41a);
  font-size: 14px;
  font-weight: 500;
}

.success-banner-btn {
  margin-left: auto;
  padding: 6px 16px;
  font-size: 13px;
}

.image-preview {
  aspect-ratio: 3/4;
  overflow: hidden;
  position: relative;
  flex: 1; /* 填充卡片剩余空间 */
}

.image-preview img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(0, 0, 0, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity 0.2s;
}

.image-preview:hover .image-overlay {
  opacity: 1;
}

/* 触屏设备没有 hover：隐藏遮罩，操作依赖底部常显按钮 */
@media (hover: none) {
  .image-overlay {
    display: none;
  }
}

.overlay-btn {
  display: flex;
  align-items: center;
  gap: 6px;
  padding: 8px 16px;
  background: white;
  border: none;
  border-radius: 6px;
  cursor: pointer;
  font-size: 13px;
  color: #333;
  transition: all 0.2s;
}

.overlay-btn:hover {
  background: var(--primary);
  color: white;
}

.overlay-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.image-placeholder {
  aspect-ratio: 3/4;
  background: #f9f9f9;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1; /* 填充卡片剩余空间 */
  min-height: 240px; /* 确保有最小高度 */
}

.error-placeholder {
  background: var(--color-danger-soft, #fff5f5);
}

.error-icon {
  width: 40px;
  height: 40px;
  border-radius: 50%;
  background: var(--color-danger, #ff4d4f);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
}

.status-text {
  font-size: 13px;
  color: var(--text-sub);
}

.image-error-text {
  max-width: 85%;
  color: var(--color-danger, #991b1b);
  font-size: 12px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.retry-btn {
  margin-top: 8px;
  padding: 6px 16px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: 4px;
  cursor: pointer;
  font-size: 12px;
  transition: all 0.2s;
}

.retry-btn:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.retry-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.image-footer {
  padding: 12px;
  border-top: 1px solid #f0f0f0;
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.page-label {
  font-size: 12px;
  color: var(--text-sub);
}

.footer-actions {
  display: flex;
  align-items: center;
  gap: 8px;
}

.footer-regen-btn {
  border: 1px solid var(--border-color, #eee);
  background: white;
  color: var(--text-sub, #666);
  font-size: 11px;
  padding: 3px 8px;
  border-radius: 4px;
  cursor: pointer;
  transition: all 0.2s;
}

.footer-regen-btn:hover {
  border-color: var(--primary, #ff2442);
  color: var(--primary, #ff2442);
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: 4px;
}

.status-badge.done {
  background: var(--color-success-soft, #E6F7ED);
  color: var(--color-success, #52C41A);
}

.status-badge.generating,
.status-badge.retrying {
  background: var(--color-info-soft, #E6F4FF);
  color: var(--color-info, #1890FF);
}

.status-badge.error {
  background: var(--color-danger-soft, #FFF1F0);
  color: var(--color-danger, #FF4D4F);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .success-banner {
    flex-wrap: wrap;
  }

  .success-banner-btn {
    margin-left: 0;
    width: 100%;
  }
}
</style>
