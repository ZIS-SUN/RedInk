<template>
  <div class="container">
    <StepIndicator :current="3" />

    <div class="page-header">
      <div>
        <h1 class="page-title">{{ isDone ? '生成完成' : '正在生成' }}</h1>
        <p class="page-subtitle">
          <span v-if="isGenerating">{{ phaseText }} · 已完成 {{ store.progress.current }} / 共 {{ store.progress.total }} 张<template v-if="etaText"> · {{ etaText }}</template></span>
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
        <button class="btn btn-secondary" @click="router.push('/outline')">
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

      <!-- 生成中的等待预期提示：告知单张耗时正常范围，降低"卡死"焦虑 -->
      <p v-if="isGenerating" class="progress-hint">
        出图较慢属正常，单张约 1 分钟，可在此页等待或稍后到「我的创作」查看
      </p>

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
              class="fade-in"
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

          <!-- 生成中/重试中状态：shimmer + spinner + 单图伪进度条 + 已用时长 -->
          <div v-else-if="image.status === 'generating' || image.status === 'retrying'" class="image-placeholder shimmer">
            <div class="spinner"></div>
            <div class="status-text">{{ image.status === 'retrying' ? '重新生成中…' : '生成中...' }}</div>
            <div class="mini-progress">
              <div class="mini-progress-bar" :style="{ width: percentFor(image) + '%' }" />
            </div>
            <div v-if="elapsedTextFor(image)" class="status-text">{{ elapsedTextFor(image) }}</div>
          </div>

          <!-- 排队中状态：中性占位，不带 spinner，避免"全部在转圈"的假象 -->
          <div v-else-if="image.status === 'queued'" class="image-placeholder queued-placeholder">
            <div class="status-text">排队中…</div>
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
          <div v-else class="image-placeholder shimmer">
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
import { useGenerationProgress } from '../composables/useGenerationProgress'
import { useImageRetry } from '../composables/useImageRetry'
import type { AppError } from '../utils/errors'
import { notifyDesktop } from '../utils/desktopNotify'

const router = useRouter()
const store = useGeneratorStore()
// 当前应用的风格（来自风格模板库），用于风格提示条
const { activeStyle } = useStyleLibrary()

const error = ref<AppError | null>(null)

const isGenerating = computed(() => store.progress.status === 'generating')

// 实时进度数据源：500ms 节拍器驱动的平滑百分比 / 剩余时间 / 单图已用时长
const {
  overallPercentValue,
  etaText,
  phaseText,
  percentFor,
  elapsedTextFor,
  stop: stopProgressTicker
} = useGenerationProgress()

// 总进度改用平滑估算值：已完成数 + 进行中图片的伪进度，不再长时间停在 0%
const progressPercent = overallPercentValue

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
    queued: '排队中',
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
  cancelAutoRedirect,
  cleanupGenerationRunner,
  startGenerationFlow
} = useGenerationRunner(hasFailedImages, setError)

// 完成后取消 runner 内部的 1 秒强制跳转，改为用户显式点击「查看结果」。
// 注意只取消跳转定时器，不能调用 cleanupGenerationRunner：
// 后者会把组件标记为已卸载，导致后续真实的 SSE 错误被静默吞掉
watch(isDone, (done) => {
  if (done) {
    cancelAutoRedirect()
  }
}, { immediate: true })

// ==================== 桌面原生通知（浏览器环境自动降级为 no-op） ====================
// 同一次生成只通知一次；重新开始生成/重试后允许再次通知
const notifiedDone = ref(false)
const notifiedFailed = ref(false)

watch(isDone, (done) => {
  if (done && !notifiedDone.value) {
    notifiedDone.value = true
    notifyDesktop('红墨 RedInk', `全部 ${store.progress.total} 张图片生成完成 ✅`)
  }
})

watch(
  () => hasFailedImages.value && store.progress.status === 'error',
  (failed) => {
    if (failed && !notifiedFailed.value) {
      notifiedFailed.value = true
      notifyDesktop('红墨 RedInk', `有 ${failedCount.value} 张图片生成失败，可在应用内重试`)
    }
  }
)

watch([isGenerating, isRetrying], ([generating, retrying]) => {
  if (generating || retrying) {
    notifiedDone.value = false
    notifiedFailed.value = false
  }
})

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
onUnmounted(() => {
  cleanupGenerationRunner()
  stopProgressTicker()
})
</script>

<style scoped>
/* 当前风格提示条 */
.style-hint {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-width: 100%;
  margin-bottom: var(--space-4);
  padding: 8px 16px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  color: var(--color-info);
  background: var(--color-info-soft);
}

.style-hint.inactive {
  color: var(--text-sub);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
}

.style-hint-colors {
  display: inline-flex;
  gap: 4px;
}

.style-hint-color {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(33, 30, 27, 0.1);
}

.style-hint-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.style-hint-link:hover {
  text-decoration: underline;
}

/* 生成中的等待预期提示 */
.progress-hint {
  margin-top: var(--space-2);
  font-size: var(--font-size-caption);
  color: var(--text-sub);
}

.success-banner {
  margin-top: 18px;
  display: flex;
  align-items: center;
  gap: 10px;
  padding: var(--space-3) var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-success-soft);
  color: var(--color-success);
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

/* 完成图片淡入：挂载即播放 */
.image-preview img.fade-in {
  animation: img-fade-in 0.4s var(--ease-out);
}

@keyframes img-fade-in {
  from {
    opacity: 0;
  }
  to {
    opacity: 1;
  }
}

.image-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: rgba(33, 30, 27, 0.5);
  display: flex;
  align-items: center;
  justify-content: center;
  opacity: 0;
  transition: opacity var(--transition-fast);
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
  background: var(--bg-card);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 13px;
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
  transition: background var(--transition-fast), color var(--transition-fast),
    transform var(--transition-fast);
}

.overlay-btn:hover {
  background: var(--primary);
  color: white;
  transform: translateY(-1px);
}

.overlay-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.image-placeholder {
  aspect-ratio: 3/4;
  background: var(--gray-1);
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
  flex: 1; /* 填充卡片剩余空间 */
  min-height: 240px; /* 确保有最小高度 */
}

/* 骨架 shimmer：纯 CSS 高光扫过，让等待中的卡片有"正在工作"的呼吸感 */
.image-placeholder.shimmer {
  position: relative;
  overflow: hidden;
}

.image-placeholder.shimmer::before {
  content: '';
  position: absolute;
  inset: 0;
  background: linear-gradient(
    100deg,
    transparent 30%,
    rgba(255, 255, 255, 0.6) 50%,
    transparent 70%
  );
  transform: translateX(-100%);
  animation: shimmer-sweep 2s var(--ease-out) infinite;
  pointer-events: none;
}

@keyframes shimmer-sweep {
  to {
    transform: translateX(100%);
  }
}

/* 排队中：中性静态占位，与"正在工作"的 shimmer 区分开 */
.queued-placeholder {
  background: var(--gray-1);
}

/* 单张图片的伪进度条 */
.mini-progress {
  width: 60%;
  max-width: 160px;
  height: 4px;
  background: var(--gray-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.mini-progress-bar {
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-full);
  transition: width 0.5s var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .image-placeholder.shimmer::before {
    animation: none;
    display: none;
  }

  /* 减少动态：进度条宽度不做过渡，图片不做淡入 */
  .progress-bar,
  .mini-progress-bar {
    transition: none;
  }

  .image-preview img.fade-in {
    animation: none;
  }
}

.error-placeholder {
  background: var(--color-danger-soft);
}

.error-icon {
  width: 40px;
  height: 40px;
  border-radius: var(--radius-full);
  background: var(--color-danger);
  color: white;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
}

.status-text {
  font-size: var(--font-size-caption);
  color: var(--text-sub);
}

.image-error-text {
  max-width: 85%;
  color: var(--color-danger);
  font-size: 12px;
  line-height: 1.45;
  display: -webkit-box;
  -webkit-line-clamp: 3;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.retry-btn {
  margin-top: var(--space-2);
  padding: 6px 16px;
  background: var(--primary);
  color: white;
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  font-size: 12px;
  transition: background var(--transition-fast), transform var(--transition-fast);
}

.retry-btn:hover {
  background: var(--primary-hover);
  transform: translateY(-1px);
}

.retry-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
}

.image-footer {
  padding: var(--space-3);
  border-top: 1px solid var(--border-color);
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
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 11px;
  padding: 3px 8px;
  border-radius: var(--radius-xs);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.footer-regen-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-fade);
}

.status-badge {
  font-size: 10px;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
}

.status-badge.done {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.status-badge.generating,
.status-badge.retrying {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.status-badge.queued {
  background: var(--gray-1);
  color: var(--text-sub);
}

.status-badge.error {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.spinner {
  width: 24px;
  height: 24px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: var(--radius-full);
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

  /* 生成中 subtitle 内容变长（阶段 · 进度 · 剩余时间），允许换行不溢出 */
  .page-subtitle {
    white-space: normal;
    word-break: break-word;
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
