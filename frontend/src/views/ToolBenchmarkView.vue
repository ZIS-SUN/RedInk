<template>
  <div class="container benchmark-container">
    <div class="benchmark-header">
      <h1 class="page-title">对标拆解</h1>
      <p class="page-subtitle">粘贴一篇对标爆款，AI 拆解它为什么火，并提炼可复用的套路模板</p>
    </div>

    <!-- 输入区 -->
    <div class="card benchmark-card">
      <!-- 输入模式切换 -->
      <div class="mode-tabs" role="tablist">
        <button
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'paste' }"
          role="tab"
          :aria-selected="mode === 'paste'"
          @click="mode = 'paste'"
        >
          粘贴内容
        </button>
        <button
          type="button"
          class="mode-tab"
          :class="{ active: mode === 'url' }"
          role="tab"
          :aria-selected="mode === 'url'"
          @click="mode = 'url'"
        >
          网页链接
        </button>
      </div>

      <div v-if="mode === 'paste'" class="input-area">
        <label class="field-label" for="benchmark-input">对标内容（标题 + 正文）</label>
        <textarea
          id="benchmark-input"
          v-model="content"
          class="benchmark-textarea"
          rows="9"
          placeholder="把你看到的爆款内容完整粘贴到这里（建议包含标题和正文）…"
        ></textarea>
      </div>

      <div v-else class="input-area">
        <label class="field-label" for="benchmark-url-input">对标内容链接</label>
        <input
          id="benchmark-url-input"
          v-model="url"
          type="url"
          class="topic-input"
          placeholder="粘贴文章链接，如 https://example.com/article"
          :disabled="loading"
          @keyup.enter="handleAnalyze"
        />
        <p class="input-hint">
          支持公开可访问的文章页面。小红书 / 抖音等 App 内的内容通常无法直接抓取，建议切到「粘贴内容」复制正文
        </p>
      </div>

      <div class="field-block">
        <label class="field-label" for="my-topic-input">
          我的主题（可选）
          <span class="field-hint">填写后，AI 会按同样的套路帮你写一篇原创仿写草稿</span>
        </label>
        <input
          id="my-topic-input"
          v-model="myTopic"
          class="topic-input"
          type="text"
          placeholder="例如：新手如何 30 天学会做短视频"
        />
      </div>

      <div class="submit-row">
        <button
          type="button"
          class="btn btn-primary benchmark-btn"
          :disabled="loading || !!sending || !canAnalyze"
          @click="handleAnalyze"
        >
          <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
          {{ loading ? '拆解中…' : '开始拆解' }}
        </button>
      </div>
    </div>

    <!-- 最近拆解（本地历史） -->
    <div v-if="history.length > 0" class="card history-card">
      <button type="button" class="history-toggle" @click="showHistory = !showHistory">
        <span class="history-title">最近拆解（{{ history.length }}）</span>
        <svg
          class="history-chevron"
          :class="{ open: showHistory }"
          width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true"
        ><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <ul v-if="showHistory" class="history-list">
        <li v-for="entry in history" :key="entry.id">
          <button type="button" class="history-item" @click="restoreFromHistory(entry)">
            <span class="history-summary">{{ entry.summary }}</span>
            <span class="history-time">{{ formatTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架 -->
    <div v-if="loading" class="skeleton-section" aria-hidden="true">
      <div class="card skeleton-card">
        <div class="sk-row">
          <span class="sk-line sk-badge"></span>
          <span class="sk-line sk-btn"></span>
        </div>
        <template v-for="n in 3" :key="n">
          <span class="sk-line sk-label"></span>
          <span class="sk-line"></span>
          <span class="sk-line sk-short"></span>
        </template>
      </div>
    </div>

    <!-- 拆解结果区 -->
    <div v-if="analysis" class="results-section">
      <div class="card result-card">
        <div class="result-header">
          <span class="section-badge">拆解结果</span>
          <button
            type="button"
            class="btn btn-secondary copy-btn"
            :class="{ copied: copiedKey === 'analysis' }"
            @click="copyAnalysis"
          >
            {{ copiedKey === 'analysis' ? '已复制 ✓' : '复制全部' }}
          </button>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🪝 钩子类型</h3>
          <p class="analysis-text">{{ analysis.hook }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">⚡ 开头如何抓人</h3>
          <p class="analysis-text">{{ analysis.opening }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🧱 内容结构</h3>
          <ol class="structure-list">
            <li v-for="(step, index) in analysis.structure" :key="index" class="structure-item">
              {{ step }}
            </li>
          </ol>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">💗 情绪价值</h3>
          <p class="analysis-text">{{ analysis.emotion }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🎯 目标受众</h3>
          <p class="analysis-text">{{ analysis.audience }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🔥 爆点要素</h3>
          <ul class="viral-list">
            <li v-for="(element, index) in analysis.viral_elements" :key="index" class="viral-item">
              {{ element }}
            </li>
          </ul>
        </div>

        <div class="analysis-item template-item">
          <div class="template-header">
            <h3 class="analysis-label">📋 可复用套路模板</h3>
            <button
              type="button"
              class="btn btn-secondary copy-btn"
              :class="{ copied: copiedKey === 'template' }"
              @click="copyTemplate"
            >
              {{ copiedKey === 'template' ? '已复制 ✓' : '复制模板' }}
            </button>
          </div>
          <p class="analysis-text template-text">{{ analysis.reusable_template }}</p>
        </div>

        <!-- 一键送创作 -->
        <div class="creation-bar">
          <button
            v-if="draft"
            type="button"
            class="btn btn-primary creation-btn"
            :disabled="loading || !!sending"
            @click="sendDraftToCreation"
          >
            <span v-if="sending === 'draft'" class="spinner-sm" aria-hidden="true"></span>
            {{ sending === 'draft' ? '正在生成大纲…' : '用仿写草稿创作' }}
          </button>
          <button
            v-if="analysis.reusable_template"
            type="button"
            class="btn creation-btn"
            :class="draft ? 'btn-secondary' : 'btn-primary'"
            :disabled="loading || !!sending"
            @click="openTopicDialog"
          >
            <span v-if="sending === 'template'" class="spinner-sm" aria-hidden="true"></span>
            {{ sending === 'template' ? '正在生成大纲…' : '以此结构创作我的主题' }}
          </button>
        </div>
        <p class="creation-tip">送创作后会自动转成图文大纲，进入创作中心继续编辑和生成图片</p>
      </div>

      <!-- 仿写草稿区 -->
      <div v-if="draft" class="card result-card">
        <div class="result-header">
          <span class="section-badge draft-badge">仿写草稿</span>
          <button
            type="button"
            class="btn btn-secondary copy-btn"
            :class="{ copied: copiedKey === 'draft' }"
            @click="copyDraft"
          >
            {{ copiedKey === 'draft' ? '已复制 ✓' : '复制草稿' }}
          </button>
        </div>
        <p class="draft-text">{{ draft }}</p>
        <p class="draft-tip">草稿按对标套路生成、内容原创，建议在此基础上加入你的真实经历后再发布</p>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>
      </div>
      <p class="empty-title">还没有拆解结果</p>
      <p class="empty-desc">把一篇你觉得好的爆款内容粘贴到上方，点「开始拆解」，AI 会告诉你它为什么火</p>
      <p class="empty-example">拆解维度：钩子 · 结构 · 情绪 · 受众 · 爆点 · 可复用模板</p>
    </div>

    <!-- 「以此结构创作」主题输入弹窗 -->
    <div v-if="topicDialogVisible" class="topic-dialog-mask" @click.self="closeTopicDialog">
      <div class="card topic-dialog" role="dialog" aria-modal="true" aria-labelledby="topic-dialog-title">
        <h3 id="topic-dialog-title" class="topic-dialog-title">以此结构创作我的主题</h3>
        <p class="topic-dialog-desc">AI 会严格按刚拆解出的爆款结构模板，围绕你的主题生成图文大纲</p>
        <input
          ref="topicDialogInputEl"
          v-model="topicDialogInput"
          class="topic-input"
          type="text"
          placeholder="例如：新手如何 30 天学会做短视频"
          @keyup.enter="confirmTemplateCreation"
        />
        <div class="topic-dialog-actions">
          <button type="button" class="btn btn-secondary" @click="closeTopicDialog">取消</button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!topicDialogInput.trim()"
            @click="confirmTemplateCreation"
          >
            开始创作
          </button>
        </div>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      class="benchmark-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleAnalyze"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { analyzeBenchmark, type BenchmarkAnalysis } from '../api/benchmark'
import { linkToOutline } from '../api/link'
import type { Page } from '../api/types'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  addEntry,
  createEntry,
  loadHistory,
  saveHistory,
  type BenchmarkHistoryEntry,
} from '../utils/benchmarkHistory'
import ErrorCard from '../components/common/ErrorCard.vue'

const router = useRouter()
const store = useGeneratorStore()

const mode = ref<'paste' | 'url'>('paste')
const content = ref('')
const url = ref('')
const myTopic = ref('')
const analysis = ref<BenchmarkAnalysis | null>(null)
const draft = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const copiedKey = ref('')

// 送创作加载态：'' 空闲 | 'draft' 仿写草稿 | 'template' 结构模板
const sending = ref<'' | 'draft' | 'template'>('')

// 「以此结构创作」主题弹窗
const topicDialogVisible = ref(false)
const topicDialogInput = ref('')
const topicDialogInputEl = ref<HTMLInputElement | null>(null)

// 本地历史
const history = ref<BenchmarkHistoryEntry[]>(loadHistory())
const showHistory = ref(false)

let copyTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})

const canAnalyze = computed(() =>
  mode.value === 'paste' ? !!content.value.trim() : !!url.value.trim()
)

async function handleAnalyze() {
  if (!canAnalyze.value || loading.value || sending.value) return

  loading.value = true
  error.value = null
  analysis.value = null
  draft.value = ''

  const input = mode.value === 'paste' ? content.value.trim() : url.value.trim()

  try {
    const result = await analyzeBenchmark({
      content: mode.value === 'paste' ? input : undefined,
      url: mode.value === 'url' ? input : undefined,
      myTopic: myTopic.value.trim() || undefined,
    })

    if (result.success && result.analysis) {
      analysis.value = result.analysis
      draft.value = result.draft || ''
      recordHistory(input, result.analysis, result.draft || '')
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '对标拆解失败', '对标拆解失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '对标拆解失败')
  } finally {
    loading.value = false
  }
}

// ==================== 本地历史 ====================

function recordHistory(input: string, resultAnalysis: BenchmarkAnalysis, resultDraft: string) {
  const entry = createEntry({
    input,
    analysis: resultAnalysis,
    draft: resultDraft,
    myTopic: myTopic.value.trim(),
  })
  history.value = addEntry(history.value, entry)
  saveHistory(history.value)
}

/** 点击历史条目：回填结果区，不重新调 AI */
function restoreFromHistory(entry: BenchmarkHistoryEntry) {
  if (loading.value || sending.value) return
  analysis.value = entry.analysis
  draft.value = entry.draft
  if (entry.myTopic) myTopic.value = entry.myTopic
  error.value = null
}

function formatTime(timestamp: number): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ==================== 一键送创作 ====================

/**
 * 长文本 → 大纲 → 写入 store → 跳转创作中心（照抄 ToolLinkView.sendToCreation 模式）
 */
async function sendTextToCreation(text: string, fallbackTopic: string, kind: 'draft' | 'template') {
  if (loading.value || sending.value) return

  sending.value = kind
  error.value = null

  try {
    const result = await linkToOutline({ text })

    if (result.success && result.pages && result.pages.length > 0) {
      const pages: Page[] = result.pages
      pages.forEach((page, i) => {
        page.index = i
      })
      const raw = pages.map(page => page.content).join('\n\n<page>\n\n')

      store.setTopic((fallbackTopic || result.topic || '对标仿创').trim())
      store.setOutline(raw, pages)
      // 清空旧的历史记录 ID，让大纲页为本次内容创建新的历史记录
      store.setRecordId(null)

      router.push('/outline')
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成大纲失败',
        '生成大纲失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成大纲失败')
  } finally {
    sending.value = ''
  }
}

/** 「用仿写草稿创作」：把 draft 转成大纲后进入创作流程 */
function sendDraftToCreation() {
  if (!draft.value) return
  sendTextToCreation(draft.value, myTopic.value.trim(), 'draft')
}

function openTopicDialog() {
  if (loading.value || sending.value) return
  topicDialogInput.value = myTopic.value.trim()
  topicDialogVisible.value = true
  nextTick(() => topicDialogInputEl.value?.focus())
}

function closeTopicDialog() {
  topicDialogVisible.value = false
}

/** 「以此结构创作我的主题」：主题 + 套路模板拼成长文，转大纲后进入创作流程 */
function confirmTemplateCreation() {
  const topic = topicDialogInput.value.trim()
  if (!topic || !analysis.value?.reusable_template) return

  topicDialogVisible.value = false
  const text = [
    '请严格按以下爆款结构模板创作：',
    `主题：${topic}`,
    `结构模板：\n${analysis.value.reusable_template}`,
  ].join('\n\n')

  sendTextToCreation(text, topic, 'template')
}

// ==================== 复制 ====================

async function copyText(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 剪贴板 API 不可用时（如非 https）降级为手动选区复制
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedKey.value = key
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedKey.value = '' }, 1500)
}

function copyAnalysis() {
  if (!analysis.value) return
  const a = analysis.value
  const lines = [
    `【钩子类型】\n${a.hook}`,
    `【开头如何抓人】\n${a.opening}`,
    `【内容结构】\n${a.structure.map((s, i) => `${i + 1}. ${s}`).join('\n')}`,
    `【情绪价值】\n${a.emotion}`,
    `【目标受众】\n${a.audience}`,
    `【爆点要素】\n${a.viral_elements.map(v => `- ${v}`).join('\n')}`,
    `【可复用套路模板】\n${a.reusable_template}`
  ]
  copyText(lines.join('\n\n'), 'analysis')
}

function copyTemplate() {
  if (!analysis.value) return
  copyText(analysis.value.reusable_template, 'template')
}

function copyDraft() {
  if (!draft.value) return
  copyText(draft.value, 'draft')
}
</script>

<style scoped>
.benchmark-container {
  max-width: 860px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.benchmark-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

.benchmark-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

/* 输入模式切换（与链接转图文页保持一致的视觉） */
.mode-tabs {
  display: flex;
  gap: var(--space-2);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: var(--space-3);
}

.mode-tab {
  padding: 8px 18px;
  border: none;
  background: transparent;
  border-radius: var(--radius-full);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.mode-tab:hover {
  color: var(--text-main);
  background: var(--gray-1);
}

.mode-tab.active {
  background: var(--primary-fade);
  color: var(--primary);
}

.input-area {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.input-hint {
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.6;
  margin: 0;
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.field-hint {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-sub);
  margin-left: 8px;
}

.benchmark-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  resize: vertical;
  min-height: 180px;
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.benchmark-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.benchmark-textarea::placeholder {
  color: var(--text-placeholder);
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.topic-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--text-main);
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.topic-input::placeholder {
  color: var(--text-placeholder);
}

.submit-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.benchmark-btn {
  min-width: 180px;
}

/* 最近拆解（本地历史） */
.history-card {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
}

.history-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: none;
  background: transparent;
  padding: 4px 0;
  cursor: pointer;
  color: var(--text-main);
}

.history-title {
  font-size: 14px;
  font-weight: 600;
}

.history-chevron {
  color: var(--text-sub);
  transition: transform var(--transition-fast);
}

.history-chevron.open {
  transform: rotate(180deg);
}

.history-list {
  list-style: none;
  padding: 0;
  margin: var(--space-3) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 280px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-1);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.history-item:hover {
  border-color: var(--primary);
  background: var(--primary-fade);
}

.history-summary {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-sub);
}

/* 加载骨架（纯 CSS shimmer） */
.skeleton-section {
  margin-top: var(--space-5);
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.sk-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-2);
}

.sk-line {
  display: block;
  height: 14px;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-badge { width: 84px; height: 24px; }
.sk-btn { width: 92px; height: 32px; border-radius: var(--radius-md); }
.sk-label { width: 120px; height: 16px; margin-top: var(--space-2); }
.sk-short { width: 55%; }

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* 结果区 */
.results-section {
  margin-top: var(--space-5);
}

.result-card {
  animation: fadeIn 0.4s var(--ease-out) both;
  margin-bottom: var(--space-4);
}

/* 仿写草稿卡片跟随拆解卡片错峰入场 */
.result-card + .result-card {
  animation-delay: 90ms;
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.section-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.draft-badge {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.copy-btn {
  padding: 8px 18px;
  font-size: 14px;
  white-space: nowrap;
}

.copy-btn.copied {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
}

.analysis-item {
  margin-bottom: var(--space-4);
}

.analysis-item:last-child {
  margin-bottom: 0;
}

.analysis-label {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-2);
}

.analysis-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.structure-list {
  padding-left: 22px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.structure-item {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
}

.viral-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.viral-item {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  padding: 10px 14px;
  background: var(--gray-1);
  border-radius: var(--radius-sm);
}

.template-item {
  padding: var(--space-4);
  background: var(--primary-fade);
  border-radius: var(--radius-md);
}

.template-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.template-header .analysis-label {
  margin-bottom: 0;
}

.template-text {
  font-weight: 500;
}

/* 一键送创作 */
.creation-bar {
  display: flex;
  justify-content: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
  flex-wrap: wrap;
}

.creation-btn {
  min-width: 200px;
}

.creation-tip {
  margin-top: var(--space-2);
  text-align: center;
  font-size: 13px;
  color: var(--text-sub);
}

.draft-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.draft-tip {
  margin-top: var(--space-3);
  font-size: 13px;
  color: var(--text-sub);
}

/* 「以此结构创作」主题弹窗 */
.topic-dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 16px;
  animation: fadeIn 0.2s var(--ease-out);
}

.topic-dialog {
  width: min(480px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.topic-dialog-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
}

.topic-dialog-desc {
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.6;
  margin: 0;
}

.topic-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* 空/初始态 */
.empty-state {
  margin-top: var(--space-6);
  text-align: center;
  padding: var(--space-4) 16px;
  animation: fadeIn 0.4s var(--ease-out);
}

.empty-icon {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-full);
  background: var(--primary-fade);
  color: var(--primary);
  margin-bottom: var(--space-4);
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0 0 6px;
}

.empty-desc {
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.7;
  margin: 0;
}

.empty-example {
  display: inline-block;
  margin: var(--space-4) 0 0;
  padding: 6px 14px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.benchmark-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 降低动效偏好：关闭入场与 shimmer */
@media (prefers-reduced-motion: reduce) {
  .result-card,
  .empty-state,
  .benchmark-error,
  .topic-dialog-mask {
    animation: none;
  }

  .sk-line {
    animation: none;
    background: var(--gray-2);
  }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .benchmark-container {
    padding-top: 12px;
  }

  .card {
    padding: var(--space-5);
  }

  .benchmark-btn,
  .creation-btn {
    width: 100%;
  }

  .result-header,
  .template-header {
    flex-wrap: wrap;
  }
}
</style>
