<template>
  <div class="container home-container">
    <!-- 图片网格轮播背景 -->
    <ShowcaseBackground />

    <!-- 未配置 AI 服务商引导（检测失败或已配置时不渲染） -->
    <SetupGuideBanner />

    <!-- 继续上次创作横幅：store 已持久化未完成流程，这里给一个安静的回访入口 -->
    <div v-if="showResumeBanner" class="resume-banner" role="status">
      <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
      <span class="resume-banner-text">
        你有一篇未完成的创作<strong>《{{ resumeTopic }}》</strong>
      </span>
      <div class="resume-banner-actions">
        <button type="button" class="resume-banner-btn primary" @click="resumeUnfinished">继续编辑</button>
        <button type="button" class="resume-banner-btn" @click="dismissResumeBanner">关闭</button>
      </div>
    </div>

    <!-- Hero Area -->
    <div class="hero-section">
      <div class="hero-content">
        <div class="brand-pill">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
          AI 驱动的红墨创作助手
        </div>
        <div class="platform-slogan">
          让传播不再需要门槛，让创作从未如此简单
        </div>
        <h1 class="page-title">灵感一触即发</h1>
        <p class="page-subtitle">输入你的创意主题，让 AI 帮你生成爆款标题、正文和封面图</p>
      </div>

      <!-- 主题输入组合框 -->
      <ComposerInput
        ref="composerRef"
        v-model="topic"
        :loading="loading"
        @generate="handleGenerate"
        @imagesChange="handleImagesChange"
      />

      <!-- 流式生成预览：实时滚动展示已生成的大纲文本 -->
      <div
        v-if="loading && streamingText"
        ref="streamPreviewEl"
        class="stream-preview"
        role="status"
        aria-live="polite"
        aria-label="大纲生成中"
      >
        <pre class="stream-preview-text">{{ streamingText }}</pre>
        <span class="stream-cursor" aria-hidden="true"></span>
      </div>

      <!-- 示例主题：一键填入输入框，帮新手迈出第一步 -->
      <div class="topic-chips" role="list" aria-label="示例主题">
        <button
          v-for="example in EXAMPLE_TOPICS"
          :key="example"
          type="button"
          class="topic-chip"
          role="listitem"
          @click="applyExampleTopic(example)"
        >
          {{ example }}
        </button>
      </div>

      <!-- 品牌人设选择器（可选） -->
      <div v-if="brands.length > 0" class="brand-select-row">
        <label class="brand-select-label" for="brand-select">品牌人设（可选）</label>
        <select
          id="brand-select"
          class="brand-select"
          :value="store.brandId"
          @change="handleBrandChange"
        >
          <option value="">不使用</option>
          <option v-for="brand in brands" :key="brand.id" :value="brand.id">
            {{ brand.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- 最近作品：有历史记录才渲染，安静的回访入口 -->
    <div v-if="recentRecords.length > 0" class="recent-works">
      <div class="recent-works-head">
        <h2 class="recent-works-title">最近作品</h2>
        <router-link to="/history" class="recent-works-more">查看全部</router-link>
      </div>
      <div class="recent-works-grid">
        <div
          v-for="record in recentRecords"
          :key="record.id"
          class="recent-card"
          role="link"
          tabindex="0"
          @click="router.push(`/history/${record.id}`)"
          @keydown.enter="router.push(`/history/${record.id}`)"
        >
          <div class="recent-thumb">
            <img
              v-if="record.thumbnail && record.task_id"
              :src="`/api/images/${record.task_id}/${record.thumbnail}`"
              alt=""
              loading="lazy"
              decoding="async"
            />
            <span v-else class="recent-thumb-placeholder">{{ record.title.charAt(0) }}</span>
          </div>
          <div class="recent-card-info">
            <div class="recent-card-title" :title="record.title">{{ record.title }}</div>
            <div class="recent-card-meta">
              <span class="recent-status" :class="record.status">{{ statusLabel(record.status) }}</span>
              <span>{{ formatRecentDate(record.updated_at) }}</span>
            </div>
          </div>
        </div>
      </div>
    </div>

    <!-- 版权信息：中性、安静，不打扰创作 -->
    <div class="page-footer">
      <div class="footer-copyright">
        © 2025 <a href="https://github.com/HisMax/RedInk" target="_blank" rel="noopener noreferrer">RedInk</a> by 默子 (Histone)
      </div>
      <div class="footer-license">
        Licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-NC-SA 4.0</a>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      class="home-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { nextTick, ref, watch, onMounted, onUnmounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import {
  generateOutline,
  generateOutlineStream,
  shouldFallbackToNonStream,
  createHistory,
  getHistoryList,
  type HistoryRecord,
  type OutlineResponse
} from '../api'
import { isAbortError } from '../api/client'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'

// 引入组件
import ShowcaseBackground from '../components/home/ShowcaseBackground.vue'
import ComposerInput from '../components/home/ComposerInput.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import SetupGuideBanner from '../components/common/SetupGuideBanner.vue'

const router = useRouter()
const store = useGeneratorStore()

// 状态
const topic = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const composerRef = ref<InstanceType<typeof ComposerInput> | null>(null)

// 流式生成：已收到的大纲文本（实时滚动展示）与预览容器引用
const streamingText = ref('')
const streamPreviewEl = ref<HTMLElement | null>(null)

// 流式请求的取消控制器（卸载时 abort，参照 useGenerationRunner 的 abort 模式）
let abortController: AbortController | null = null

// 上传的图片文件
const uploadedImageFiles = ref<File[]>([])

// 品牌档案列表（用于品牌人设选择器）
const brands = ref<BrandKit[]>([])

// 示例主题：点击即填入输入框
const EXAMPLE_TOPICS = [
  '秋冬显瘦穿搭公式',
  '新手化妆避坑指南',
  '周末城市漫步路线',
  '打工人快手早餐',
  '平价护肤红黑榜',
  '居家收纳神器测评'
]

// 最近作品（最多 3 条；为空则整个区块不渲染）
const recentRecords = ref<HistoryRecord[]>([])

// ==================== 主题草稿防抖入 store ====================

// 主题草稿的防抖定时器：输入停顿 300ms 后写入 store（store 有 localStorage 持久化）
let topicDraftTimer: number | null = null

// 输入主题实时防抖同步到 store，切页/刷新后草稿不丢。
// 挂载回填、点示例等场景 topic 与 store 已一致，写入前比对可避免循环与冗余持久化
watch(topic, (value) => {
  if (topicDraftTimer !== null) {
    clearTimeout(topicDraftTimer)
  }
  topicDraftTimer = window.setTimeout(() => {
    topicDraftTimer = null
    if (store.topic !== value) {
      store.setTopic(value)
    }
  }, 300)
})

// ==================== 继续上次创作横幅 ====================

// 「关闭」仅本次会话隐藏横幅（不清 store 数据），刷新新会话仍会提示
const RESUME_BANNER_DISMISS_KEY = 'resume-banner-dismissed'

/**
 * 是否展示「继续上次创作」横幅：
 * store 已恢复到中途阶段（stage 非 input）且确有内容（大纲页或图片）时提示
 */
function canShowResumeBanner(): boolean {
  try {
    if (sessionStorage.getItem(RESUME_BANNER_DISMISS_KEY) === '1') return false
  } catch {
    // sessionStorage 不可用时按未关闭处理
  }
  if (store.stage === 'input') return false
  return store.outline.pages.length > 0 || store.images.length > 0
}

const showResumeBanner = ref(canShowResumeBanner())

// 横幅标题取挂载时的快照：F12 的草稿防抖会实时改写 store.topic，
// 避免用户在输入框打新主题时横幅里的《标题》跟着变
const resumeTopic = ref(store.topic || '未命名主题')

/**
 * 按持久化的阶段跳回未完成的创作流程
 */
function resumeUnfinished() {
  const hasPages = store.outline.pages.length > 0
  const hasImages = store.images.length > 0
  if (store.stage === 'result' && hasImages) {
    router.push('/result')
  } else if (store.stage === 'generating' && hasPages) {
    router.push('/generate')
  } else if (hasPages) {
    router.push('/outline')
  } else if (hasImages) {
    router.push('/result')
  }
}

/**
 * 关闭横幅：sessionStorage 标记本次会话不再提示，store 数据保持不动
 */
function dismissResumeBanner() {
  try {
    sessionStorage.setItem(RESUME_BANNER_DISMISS_KEY, '1')
  } catch {
    // 存储失败仅影响"刷新后仍隐藏"，本次隐藏依然生效
  }
  showResumeBanner.value = false
}

// 从大纲页「上一步」返回时，回填之前输入的主题
onMounted(() => {
  if (store.topic && !topic.value) {
    topic.value = store.topic
  }
  loadBrands()
  loadRecentWorks()
})

/**
 * 点击示例主题：填入输入框并同步到 store
 */
function applyExampleTopic(example: string) {
  topic.value = example
  store.setTopic(example)
}

/**
 * 拉取最近 3 条历史记录；加载失败静默（区块不渲染）
 */
async function loadRecentWorks() {
  try {
    const res = await getHistoryList(1, 3)
    if (res.success) {
      recentRecords.value = res.records.slice(0, 3)
    }
  } catch {
    // 静默失败：首页不因历史接口异常报错
  }
}

/**
 * 历史记录状态 → 中文徽标文案
 */
function statusLabel(status: string): string {
  const map: Record<string, string> = {
    draft: '草稿',
    generating: '生成中',
    partial: '部分完成',
    completed: '已完成',
    error: '失败'
  }
  return map[status] || status
}

/**
 * 最近作品的更新时间（M/D）
 */
function formatRecentDate(dateStr: string): string {
  const d = new Date(dateStr)
  return `${d.getMonth() + 1}/${d.getDate()}`
}

/**
 * 拉取品牌档案列表并确定默认选中项：
 * - store 中已持久化的 brandId 仍有效时沿用
 * - 否则默认选中当前启用档案；没有启用档案则为「不使用」
 * 拉取失败静默忽略（选择器不显示，行为与无品牌一致）
 */
async function loadBrands() {
  const result = await getBrandList()
  if (!result.success) return

  brands.value = result.brands

  const hasBrand = (id: string) => result.brands.some(b => b.id === id)
  if (store.brandId && hasBrand(store.brandId)) return

  if (result.active_id && hasBrand(result.active_id)) {
    store.setBrandId(result.active_id)
  } else {
    store.setBrandId('')
  }
}

/**
 * 品牌人设选择变化时写入 store
 */
function handleBrandChange(event: Event) {
  store.setBrandId((event.target as HTMLSelectElement).value)
}

/**
 * 处理图片变化
 */
function handleImagesChange(images: File[]) {
  uploadedImageFiles.value = images
}

/**
 * 流式增量到达时更新预览文本，并把预览区滚动到底部
 */
function handleStreamDelta(fullText: string) {
  streamingText.value = fullText
  nextTick(() => {
    const el = streamPreviewEl.value
    if (el) el.scrollTop = el.scrollHeight
  })
}

/**
 * 生成大纲：无图时优先走 SSE 流式接口（首字 1-3 秒可见），
 * 带图片、或流式接口不可用/网络异常时自动回退到既有非流式接口（用户无感）
 */
async function handleGenerate() {
  if (loading.value) return
  if (!topic.value.trim()) return

  loading.value = true
  error.value = null
  streamingText.value = ''
  abortController = new AbortController()

  try {
    const imageFiles = uploadedImageFiles.value
    const trimmedTopic = topic.value.trim()
    const brandId = store.brandId || undefined
    // 目标搜索词（搜索埋词）：未填写时不传该参数，请求体保持向后兼容
    const seoKeywords = store.seoKeywords.length > 0 ? [...store.seoKeywords] : undefined

    let result: OutlineResponse & { has_images?: boolean }
    if (imageFiles.length > 0) {
      // 流式版只支持无图路径：带图片直接走既有非流式接口
      result = await generateOutline(trimmedTopic, imageFiles, brandId, seoKeywords)
    } else {
      try {
        result = await generateOutlineStream(
          trimmedTopic,
          brandId,
          { onDelta: handleStreamDelta },
          { signal: abortController.signal },
          seoKeywords
        )
      } catch (err) {
        // 离开页面导致的主动取消：静默结束，不回退也不报错
        if (isAbortError(err)) return
        if (!shouldFallbackToNonStream(err)) throw err
        // 流式不可用（后端不支持/网络异常/断流）：无感回退非流式
        streamingText.value = ''
        result = await generateOutline(trimmedTopic, undefined, brandId, seoKeywords)
      }
    }

    if (result.success && result.pages) {
      // 设置主题和大纲到 store
      store.setTopic(topic.value.trim())
      store.setOutline(result.outline || '', result.pages)

      // 大纲生成成功后，立即创建历史记录
      // 这样即使用户刷新页面或关闭浏览器，大纲也不会丢失
      try {
        const historyResult = await createHistory(
          topic.value.trim(),
          {
            raw: result.outline || '',
            pages: result.pages
          }
        )

        // 保存历史记录 ID 到 store，后续生成正文和图片时会使用
        if (historyResult.success && historyResult.record_id) {
          store.setRecordId(historyResult.record_id)
        } else {
          // 创建历史记录失败，记录错误但不阻断流程
          console.error('创建历史记录失败:', historyResult.error || '未知错误')
          store.setRecordId(null)
        }
      } catch (err: unknown) {
        // 创建历史记录异常，记录错误但不阻断流程
        console.error('创建历史记录异常:', err instanceof Error ? err.message : err)
        store.setRecordId(null)
      }

      // 保存用户上传的图片到 store
      if (imageFiles.length > 0) {
        store.userImages = imageFiles
      } else {
        store.userImages = []
      }

      // 清理 ComposerInput 的预览
      composerRef.value?.clearPreviews()
      uploadedImageFiles.value = []

      router.push('/outline')
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '生成大纲失败', '生成大纲失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成大纲失败')
  } finally {
    loading.value = false
    streamingText.value = ''
    abortController = null
  }
}

// 卸载时中止流式 fetch，避免回调操作已卸载的组件；
// 并把防抖窗口内未落盘的主题草稿立即写入 store，避免最后几个字丢失
// （trim 后相同则跳过：生成成功时已写入 trim 值，不用未 trim 草稿覆盖它）
onUnmounted(() => {
  abortController?.abort()
  abortController = null
  if (topicDraftTimer !== null) {
    clearTimeout(topicDraftTimer)
    topicDraftTimer = null
    if (store.topic !== topic.value && store.topic !== topic.value.trim()) {
      store.setTopic(topic.value)
    }
  }
})
</script>

<style scoped>
.home-container {
  max-width: 1100px;
  padding-top: 10px;
  position: relative;
  z-index: 1;
}

/* 继续上次创作横幅：浅底小字的回访入口，不与 hero 主输入框争夺注意力 */
.resume-banner {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-3);
  padding: 10px 14px;
  background: var(--primary-fade);
  border: 1px solid var(--primary-light);
  border-radius: var(--radius-md);
  color: var(--text-sub);
  font-size: var(--font-size-caption);
  animation: fadeIn 0.4s var(--ease-out);
}

.resume-banner svg {
  flex-shrink: 0;
  color: var(--primary);
}

.resume-banner-text {
  flex: 1;
  min-width: 0;
  line-height: 1.5;
}

.resume-banner-text strong {
  color: var(--text-main);
  font-weight: 600;
  word-break: break-all;
}

.resume-banner-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.resume-banner-btn {
  padding: 4px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast),
    border-color var(--transition-fast);
}

.resume-banner-btn:hover {
  color: var(--text-main);
  border-color: var(--border-hover);
}

.resume-banner-btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.resume-banner-btn.primary:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

/* Hero Section */
.hero-section {
  text-align: center;
  margin-bottom: var(--space-7);
  padding: var(--space-7) var(--space-8);
  animation: fadeIn 0.6s var(--ease-out);
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.hero-content {
  margin-bottom: var(--space-6);
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 16px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
  margin-bottom: var(--space-4);
  letter-spacing: 0.02em;
}

/* 流式生成预览：轻量卡片，与 composer 的 loading 设计融合 */
.stream-preview {
  margin-top: var(--space-3);
  max-height: 220px;
  overflow-y: auto;
  padding: var(--space-3) var(--space-4);
  text-align: left;
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  animation: fadeIn 0.3s var(--ease-out);
}

.stream-preview-text {
  display: inline;
  margin: 0;
  font-family: inherit;
  font-size: var(--font-size-caption);
  line-height: 1.7;
  color: var(--text-sub);
  white-space: pre-wrap;
  word-break: break-word;
}

/* 生成中的闪烁光标，提示内容仍在持续输出 */
.stream-cursor {
  display: inline-block;
  width: 2px;
  height: 1em;
  margin-left: 2px;
  vertical-align: text-bottom;
  background: var(--primary);
  animation: streamBlink 1s steps(2, start) infinite;
}

@keyframes streamBlink {
  to {
    visibility: hidden;
  }
}

/* 示例主题 chips：浅色圆角，移动端可横向滚动 */
.topic-chips {
  display: flex;
  flex-wrap: wrap;
  justify-content: center;
  gap: var(--space-2);
  margin-top: var(--space-4);
}

.topic-chip {
  padding: 6px 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  background: var(--gray-1);
  color: var(--text-sub);
  font-size: var(--font-size-caption);
  font-family: inherit;
  white-space: nowrap;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.topic-chip:hover {
  background: var(--primary-fade);
  color: var(--primary);
  border-color: var(--primary-fade);
}

/* 最近作品区：安静、克制的回访入口 */
.recent-works {
  margin-top: var(--space-6);
  margin-bottom: var(--space-5);
  animation: fadeIn 0.6s var(--ease-out);
}

.recent-works-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  margin-bottom: var(--space-3);
}

.recent-works-title {
  margin: 0;
  font-size: var(--font-size-body);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-sub);
}

.recent-works-more {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.recent-works-more:hover {
  color: var(--primary);
}

.recent-works-grid {
  display: grid;
  grid-template-columns: repeat(3, 1fr);
  gap: var(--space-3);
}

.recent-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.recent-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.recent-card:focus-visible {
  outline: none;
  box-shadow: var(--shadow-focus);
}

.recent-thumb {
  width: 48px;
  height: 64px;
  flex-shrink: 0;
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--gray-1);
  display: flex;
  align-items: center;
  justify-content: center;
}

.recent-thumb img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.recent-thumb-placeholder {
  font-size: 20px;
  font-weight: 700;
  color: var(--gray-5);
}

.recent-card-info {
  min-width: 0;
}

.recent-card-title {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
  margin-bottom: var(--space-1);
}

.recent-card-meta {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 12px;
  color: var(--text-secondary);
}

.recent-status {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  background: var(--gray-2);
  color: var(--text-sub);
}

.recent-status.completed {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.recent-status.generating {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.recent-status.partial {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.recent-status.error {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

/* 品牌人设选择器 */
.brand-select-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.brand-select-label {
  font-size: 14px;
  color: var(--text-sub);
}

.brand-select {
  padding: 8px 12px;
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.brand-select:hover {
  border-color: var(--border-hover);
}

.brand-select:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
  outline: none;
}

/* 标语作为标题上方的 kicker：更轻更安静，让大标题成为绝对主角 */
.platform-slogan {
  font-size: var(--font-size-body);
  font-weight: 500;
  color: var(--text-secondary);
  margin-bottom: var(--space-4);
  line-height: 1.6;
  letter-spacing: var(--tracking-tight);
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: var(--space-3);
}

/* Page Footer：安静的品牌落款 */
.page-footer {
  text-align: center;
  padding: var(--space-5) 0 var(--space-4);
  margin-top: var(--space-5);
}

.footer-copyright {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin-bottom: var(--space-1);
}

.footer-copyright a {
  color: var(--text-sub);
  text-decoration: none;
  font-weight: 500;
  transition: color var(--transition-fast);
}

.footer-copyright a:hover {
  color: var(--primary);
  text-decoration: underline;
}

.footer-license {
  font-size: var(--font-size-caption);
  /* --text-placeholder 对画布对比度仅 1.93:1，提升到三级文本色保证可读 */
  color: var(--text-secondary);
}

.footer-license a {
  color: var(--text-secondary);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.footer-license a:hover {
  color: var(--primary);
}

.home-error {
  position: fixed;
  bottom: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .hero-section,
  .home-error,
  .recent-works,
  .resume-banner,
  .stream-preview,
  .stream-cursor {
    animation: none;
  }

  .recent-card:hover {
    transform: none;
  }
}

/* 移动端：留白收敛，保持呼吸感不溢出 */
@media (max-width: 640px) {
  .hero-section {
    padding: var(--space-6) var(--space-4);
    margin-bottom: var(--space-6);
  }

  /* 示例主题改为单行横向滚动 */
  .topic-chips {
    flex-wrap: nowrap;
    justify-content: flex-start;
    overflow-x: auto;
    -webkit-overflow-scrolling: touch;
    scrollbar-width: none;
    padding-bottom: var(--space-1);
  }

  .topic-chips::-webkit-scrollbar {
    display: none;
  }

  .recent-works-grid {
    grid-template-columns: 1fr;
  }
}
</style>
