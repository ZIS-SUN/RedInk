<template>
  <div class="container insight-container">
    <!-- 头部 -->
    <div class="tool-header">
      <div class="brand-pill">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>
        评论洞察选题挖掘
      </div>
      <h1 class="page-title">评论区就是你的选题金矿</h1>
      <p class="page-subtitle">粘贴一批粉丝评论（每行一条），AI 聚类出粉丝真实痛点，附原评论证据与频次估计，并为每个痛点生成可直接开写的选题</p>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <label class="field-label" for="insight-comments">粉丝评论（每行一条，最多 {{ MAX_COMMENTS }} 条）</label>
      <textarea
        id="insight-comments"
        v-model="commentsInput"
        class="comments-input"
        rows="8"
        maxlength="5000"
        placeholder="把粉丝评论粘贴到这里，一行一条，例如：&#10;博主用的是什么相机呀？新手预算两千求推荐&#10;为什么我照着调参数还是拍得很丑&#10;蹲一个系统的入门系列！"
        @keydown.enter.meta.prevent="handleGenerate"
        @keydown.enter.ctrl.prevent="handleGenerate"
      ></textarea>
      <p class="comments-hint" :class="{ overflow: isOverflow }">
        已识别 {{ parsedComments.length }} 条评论<template v-if="isOverflow">，超出上限，仅分析前 {{ MAX_COMMENTS }} 条</template>
      </p>

      <div class="field-group">
        <label class="field-label" for="insight-niche">我的赛道（选填，帮 AI 聚焦）</label>
        <input
          id="insight-niche"
          v-model="niche"
          class="niche-input"
          type="text"
          maxlength="100"
          placeholder="例如：健身减脂、职场干货、摄影教学……"
        />
      </div>

      <button
        type="button"
        class="btn btn-primary generate-btn"
        :disabled="loading || parsedComments.length === 0"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '正在挖掘痛点与选题…' : '挖掘痛点与选题' }}
      </button>
    </div>

    <!-- 历史记录（本地存档） -->
    <div v-if="archive.length > 0" class="card history-card">
      <button type="button" class="history-toggle" @click="showArchive = !showArchive">
        <span class="history-title">历史记录（{{ archive.length }}）</span>
        <svg
          class="history-chevron"
          :class="{ open: showArchive }"
          width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true"
        ><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <ul v-if="showArchive" class="history-list">
        <li v-for="entry in archive" :key="entry.id">
          <button type="button" class="history-item" @click="restoreFromArchive(entry)">
            <span class="history-summary">{{ archiveSummary(entry) }}</span>
            <span class="history-time">{{ formatTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && painPoints.length === 0" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 2" :key="n" class="skeleton-card">
        <div class="sk-head-row">
          <span class="sk-line sk-theme"></span>
          <span class="sk-badge"></span>
        </div>
        <span class="sk-line sk-wide"></span>
        <span class="sk-line sk-narrow"></span>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="painPoints.length > 0" class="result-section">
      <div class="result-toolbar">
        <span class="result-count">
          从 {{ commentCount }} 条评论中挖出 {{ painPoints.length }} 个痛点、{{ totalTopics }} 条选题
        </span>
      </div>

      <div class="pain-list">
        <div
          v-for="(point, pi) in painPoints"
          :key="`${pi}-${point.theme}`"
          class="pain-card"
          :style="{ '--i': pi }"
        >
          <!-- 痛点头部 -->
          <div class="pain-head">
            <div class="pain-title-row">
              <span class="pain-index">痛点 {{ pi + 1 }}</span>
              <h2 class="pain-theme">{{ point.theme }}</h2>
            </div>
            <span class="freq-badge" :title="'AI 估计约有 ' + point.frequency + ' 条评论与该痛点相关'">
              约 {{ point.frequency }} 条提及
            </span>
          </div>
          <p v-if="point.summary" class="pain-summary">{{ point.summary }}</p>

          <!-- 原评论证据 -->
          <div v-if="point.evidence.length > 0" class="evidence-block">
            <p class="evidence-label">粉丝原话</p>
            <blockquote
              v-for="(quote, qi) in point.evidence"
              :key="qi"
              class="evidence-quote"
            >{{ quote }}</blockquote>
          </div>

          <!-- 选题条目 -->
          <div class="topic-list">
            <div
              v-for="(topic, ti) in point.topics"
              :key="`${ti}-${topic.title}`"
              class="topic-item"
            >
              <div class="topic-main">
                <div class="topic-top">
                  <span class="format-badge">{{ topic.format }}</span>
                  <p class="topic-title">{{ topic.title }}</p>
                  <span class="heat-chip" :class="heatClass(topic.heat)">热度 {{ topic.heat }}</span>
                </div>
                <p v-if="topic.angle" class="topic-angle">{{ topic.angle }}</p>
                <div v-if="topic.tags.length > 0" class="topic-tags">
                  <span v-for="tag in topic.tags" :key="tag" class="tag-item">#{{ tag }}</span>
                </div>
              </div>
              <div class="topic-actions">
                <button
                  type="button"
                  class="use-btn"
                  @click="handleUse(topic)"
                >
                  去创作
                </button>
                <button
                  type="button"
                  class="copy-btn"
                  :class="{ copied: copiedKey === `${pi}-${ti}` }"
                  @click="handleCopy(topic, `${pi}-${ti}`)"
                >
                  {{ copiedKey === `${pi}-${ti}` ? '已复制' : '复制' }}
                </button>
                <template v-if="addedKeys.has(`${pi}-${ti}`)">
                  <button type="button" class="calendar-btn added" disabled>已加入 ✓</button>
                  <RouterLink class="calendar-link" to="/tools/calendar">去日历看看</RouterLink>
                </template>
                <button
                  v-else
                  type="button"
                  class="calendar-btn"
                  @click="openCalendarDialog(topic, `${pi}-${ti}`)"
                >
                  加入日历
                </button>
              </div>
            </div>
          </div>
        </div>
      </div>

      <p class="result-disclaimer">* 频次与热度均为 AI 基于评论内容的主观估计，仅供选题参考，非平台实时数据</p>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>
      </div>
      <p class="empty-title">{{ hasGenerated ? '没有挖出有效的痛点' : '还没有洞察结果' }}</p>
      <p class="empty-desc">{{ hasGenerated ? '多粘贴一些评论，或填上你的赛道再试试吧' : '把粉丝评论粘贴到上方（一行一条），点「挖掘痛点与选题」，选中的选题可一键进入创作' }}</p>
      <p v-if="!hasGenerated" class="empty-example">评论越多，痛点聚类越准，建议 10 条以上</p>
    </div>

    <!-- 加入日历弹窗 -->
    <AddToCalendarDialog
      v-if="calendarTarget"
      :idea="calendarTarget"
      @close="closeCalendarDialog"
      @added="onCalendarAdded"
    />

    <ErrorCard
      v-if="error"
      class="insight-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { mineInsights, type InsightTopicIdea, type PainPoint } from '../api/insight'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  addArchiveEntry,
  createInsightArchiveEntry,
  loadInsightArchive,
  saveInsightArchive,
  type InsightArchiveEntry,
} from '../utils/ideaArchive'
import ErrorCard from '../components/common/ErrorCard.vue'
import AddToCalendarDialog from '../components/common/AddToCalendarDialog.vue'

const MAX_COMMENTS = 50

const router = useRouter()
const store = useGeneratorStore()

const commentsInput = ref('')
const niche = ref('')
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const painPoints = ref<PainPoint[]>([])
const commentCount = ref(0)
const copiedKey = ref('')

// 本地存档（最近 10 次挖掘结果）
const archive = ref<InsightArchiveEntry[]>(loadInsightArchive())
const showArchive = ref(false)

// 加入日历：当前弹窗对应的选题 + 已加入的选题位置键（`${痛点序号}-${选题序号}`）
const calendarTarget = ref<InsightTopicIdea | null>(null)
const calendarTargetKey = ref('')
const addedKeys = ref<Set<string>>(new Set())

let copyTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})

const parsedComments = computed(() =>
  commentsInput.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
)

const isOverflow = computed(() => parsedComments.value.length > MAX_COMMENTS)

const totalTopics = computed(() =>
  painPoints.value.reduce((sum, p) => sum + p.topics.length, 0)
)

function heatClass(heat: number): string {
  if (heat >= 85) return 'heat-high'
  if (heat >= 70) return 'heat-mid'
  return 'heat-low'
}

async function handleGenerate() {
  if (parsedComments.value.length === 0 || loading.value) return

  loading.value = true
  error.value = null

  const usedComments = parsedComments.value.slice(0, MAX_COMMENTS)

  try {
    const result = await mineInsights({
      comments: usedComments,
      niche: niche.value
    })

    if (result.success && result.pain_points) {
      painPoints.value = result.pain_points
      commentCount.value = result.comment_count ?? usedComments.length
      hasGenerated.value = true
      addedKeys.value = new Set()
      recordArchive(usedComments, result.pain_points)
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '评论洞察挖掘失败',
        '评论洞察挖掘失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '评论洞察挖掘失败')
  } finally {
    loading.value = false
  }
}

// ==================== 本地存档 ====================

function recordArchive(usedComments: string[], resultPainPoints: PainPoint[]) {
  if (resultPainPoints.length === 0) return
  const entry = createInsightArchiveEntry({
    niche: niche.value.trim(),
    comments: usedComments,
    commentCount: commentCount.value,
    painPoints: resultPainPoints,
  })
  archive.value = addArchiveEntry(archive.value, entry)
  saveInsightArchive(archive.value)
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: InsightArchiveEntry) {
  if (loading.value) return
  commentsInput.value = entry.comments.join('\n')
  niche.value = entry.niche
  painPoints.value = entry.painPoints
  commentCount.value = entry.commentCount
  hasGenerated.value = true
  addedKeys.value = new Set()
  error.value = null
}

function formatTime(timestamp: number): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

/** 存档条目摘要：赛道（如有）+ 评论数 + 痛点数 */
function archiveSummary(entry: InsightArchiveEntry): string {
  const parts = []
  if (entry.niche) parts.push(entry.niche)
  parts.push(`${entry.commentCount} 条评论`)
  parts.push(`${entry.painPoints.length} 个痛点`)
  return parts.join(' · ')
}

// ==================== 加入内容日历 ====================

function openCalendarDialog(item: InsightTopicIdea, key: string) {
  calendarTarget.value = item
  calendarTargetKey.value = key
}

function closeCalendarDialog() {
  calendarTarget.value = null
  calendarTargetKey.value = ''
}

function onCalendarAdded() {
  if (calendarTargetKey.value) {
    addedKeys.value.add(calendarTargetKey.value)
  }
  closeCalendarDialog()
}

/**
 * 把选题用于创作：把标题、切入角度、建议标签组合成更丰富的主题文本
 * 写入 generator store，跳回首页创作流程（空字段跳过对应行）——
 * 与选题灵感工具的「用这个选题创作」机制完全一致
 */
function handleUse(item: InsightTopicIdea) {
  const lines = [item.title]
  if (item.angle.trim()) {
    lines.push(`切入角度：${item.angle.trim()}`)
  }
  if (item.tags.length > 0) {
    lines.push(`建议标签：${item.tags.join(' ')}`)
  }
  store.setTopic(lines.join('\n'))
  router.push('/')
}

async function handleCopy(item: InsightTopicIdea, key: string) {
  const text = item.tags.length > 0
    ? `${item.title}\n${item.tags.map(t => `#${t}`).join(' ')}`
    : item.title

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
</script>

<style scoped>
.insight-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px 60px;
}

/* ── 头部 ───────────────────────── */
.tool-header {
  text-align: center;
  padding: 28px 16px 8px;
  animation: fadeIn 0.5s var(--ease-out);
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
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: var(--tracking-tighter);
  color: var(--text-main);
  margin: 0 0 10px;
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-sub);
  margin: 0 0 24px;
  line-height: 1.6;
}

/* ── 输入卡片（基于全局 .card，内距走 --space-6） ───────────────────── */
.input-card {
  padding: var(--space-6);
  margin-bottom: 0;
  animation: fadeIn 0.5s var(--ease-out);
}

.field-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 10px;
}

.comments-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  line-height: 1.6;
  resize: vertical;
  min-height: 150px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    background var(--transition-fast);
  background: var(--gray-1);
}

.comments-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: var(--shadow-focus);
}

.comments-hint {
  margin: 8px 2px 0;
  font-size: 13px;
  color: var(--text-sub);
}

.comments-hint.overflow {
  color: var(--color-warning);
}

.field-group {
  margin-top: 18px;
}

.niche-input {
  width: 100%;
  box-sizing: border-box;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    background var(--transition-fast);
  background: var(--gray-1);
}

.niche-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: var(--shadow-focus);
}

/* 生成按钮基于全局 .btn btn-primary，仅覆盖布局 */
.generate-btn {
  margin-top: 22px;
  width: 100%;
}

/* ── 历史记录（本地存档，样式参照对标拆解的历史区） ── */
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

/* ── 加载骨架（纯 CSS shimmer） ───── */
.skeleton-section {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  box-shadow: var(--shadow-xs);
}

.sk-head-row {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
}

.sk-line,
.sk-badge {
  display: block;
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-line {
  height: 14px;
  border-radius: var(--radius-full);
}

.sk-theme { width: 42%; height: 18px; }
.sk-wide { width: 78%; }
.sk-narrow { width: 55%; }

.sk-badge {
  flex-shrink: 0;
  width: 82px;
  height: 22px;
  border-radius: var(--radius-full);
}

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* ── 结果区 ─────────────────────── */
.result-section {
  margin-top: 28px;
  animation: fadeIn 0.4s var(--ease-out);
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 12px;
  padding: 0 4px;
}

.result-count {
  font-size: 14px;
  color: var(--text-sub);
}

.pain-list {
  display: flex;
  flex-direction: column;
  gap: 16px;
}

/* ── 痛点分组卡片 ───────────────── */
.pain-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base), border-color var(--transition-base);
  animation: fadeIn 0.4s var(--ease-out) both;
  animation-delay: calc(min(var(--i, 0), 8) * 50ms);
}

.pain-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.pain-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: 10px;
}

.pain-title-row {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  min-width: 0;
}

.pain-index {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--primary);
  color: #fff;
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.pain-theme {
  margin: 0;
  font-size: 16.5px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.5;
  word-break: break-word;
}

.freq-badge {
  flex-shrink: 0;
  padding: 3px 12px;
  border-radius: var(--radius-full);
  background: var(--primary-fade);
  color: var(--primary);
  font-size: 12.5px;
  font-weight: 600;
  white-space: nowrap;
}

.pain-summary {
  margin: 8px 0 0;
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.65;
  word-break: break-word;
}

/* ── 原评论证据 ─────────────────── */
.evidence-block {
  margin-top: 12px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  background: var(--gray-1);
}

.evidence-label {
  margin: 0 0 8px;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  letter-spacing: 0.5px;
}

.evidence-quote {
  margin: 0 0 6px;
  padding: 0 0 0 10px;
  border-left: 3px solid var(--primary);
  font-size: 13.5px;
  color: var(--text-main);
  line-height: 1.6;
  word-break: break-word;
}

.evidence-quote:last-child {
  margin-bottom: 0;
}

/* ── 选题条目 ───────────────────── */
.topic-list {
  margin-top: 14px;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.topic-item {
  display: flex;
  align-items: stretch;
  gap: 12px;
  padding: 12px 14px;
  border: 1px dashed var(--border-color);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.topic-item:hover {
  border-color: var(--border-hover);
  background: var(--gray-1);
}

.topic-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.topic-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
  flex-wrap: wrap;
}

.format-badge {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.topic-title {
  margin: 0;
  flex: 1;
  min-width: 60%;
  font-size: 14.5px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.55;
  word-break: break-word;
}

.heat-chip {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  border: 1px solid;
}

.heat-chip.heat-high {
  border-color: var(--primary);
  color: var(--primary);
}

.heat-chip.heat-mid {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.heat-chip.heat-low {
  border-color: var(--border-hover);
  color: var(--text-sub);
}

.topic-angle {
  margin: 0;
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.6;
  word-break: break-word;
}

.topic-tags {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.tag-item {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 500;
}

.topic-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 6px;
}

.use-btn {
  padding: 5px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--primary);
  background: var(--primary);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
  cursor: pointer;
  transition: background var(--transition-fast), border-color var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
  white-space: nowrap;
}

.use-btn:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.use-btn:active {
  background: var(--primary-active);
  border-color: var(--primary-active);
  transform: translateY(0);
  box-shadow: none;
}

.copy-btn {
  padding: 5px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
  white-space: nowrap;
}

.copy-btn:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.copy-btn:active {
  transform: translateY(0);
  box-shadow: none;
}

.copy-btn.copied {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.calendar-btn {
  padding: 5px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
  white-space: nowrap;
}

.calendar-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.calendar-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.calendar-btn.added {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
  cursor: default;
}

.calendar-link {
  font-size: 12px;
  color: var(--primary);
  text-align: center;
  text-decoration: none;
  white-space: nowrap;
}

.calendar-link:hover {
  text-decoration: underline;
}

.result-disclaimer {
  margin: 16px 4px 0;
  font-size: 12.5px;
  color: var(--text-sub);
  opacity: 0.8;
}

/* ── 空态 / 错误 ────────────────── */
.empty-state {
  margin-top: 32px;
  text-align: center;
  padding: var(--space-5) 16px;
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

.insight-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
}

/* ── 移动端适配 ─────────────────── */
@media (max-width: 640px) {
  .insight-container {
    padding: 12px 12px 48px;
  }

  .tool-header {
    padding-top: 16px;
  }

  .page-title {
    font-size: 22px;
  }

  .page-subtitle {
    font-size: 13.5px;
  }

  .input-card {
    padding: 18px 16px;
    border-radius: var(--radius-lg);
  }

  .pain-card {
    padding: 14px;
  }

  .pain-head {
    flex-wrap: wrap;
  }

  .topic-item {
    flex-wrap: wrap;
  }

  .topic-main {
    flex-basis: 100%;
  }

  .topic-actions {
    flex-direction: row;
    width: 100%;
    justify-content: flex-end;
    padding-top: 8px;
    border-top: 1px dashed var(--border-color);
  }
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

/* 降低动效偏好：关闭入场、stagger 与 shimmer */
@media (prefers-reduced-motion: reduce) {
  .tool-header,
  .input-card,
  .result-section,
  .pain-card,
  .empty-state,
  .insight-error {
    animation: none;
  }

  .sk-line,
  .sk-badge {
    animation: none;
    background: var(--gray-2);
  }

  .use-btn,
  .use-btn:hover,
  .copy-btn,
  .copy-btn:hover {
    transform: none;
  }
}
</style>
