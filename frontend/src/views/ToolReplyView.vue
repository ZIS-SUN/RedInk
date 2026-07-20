<template>
  <div class="container reply-container">
    <!-- 头部 -->
    <div class="tool-header">
      <div class="brand-pill">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/></svg>
        评论区互动助手
      </div>
      <h1 class="page-title">粉丝评论，句句都有神回复</h1>
      <p class="page-subtitle">粘贴粉丝评论（每行一条），选择回复语气，AI 为每条评论生成能引导二次互动、涨粉不低俗的高互动回复</p>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <!-- 来自评论洞察的预填提示 -->
      <div v-if="handoffFromInsight" class="handoff-banner" role="status">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        已带入评论洞察的 {{ parsedComments.length }} 条评论，选好语气即可生成回复
        <button type="button" class="handoff-close" aria-label="关闭提示" @click="handoffFromInsight = false">×</button>
      </div>

      <label class="field-label" for="reply-comments">粉丝评论（每行一条，最多 20 条）</label>
      <textarea
        id="reply-comments"
        v-model="commentsInput"
        class="comments-input"
        rows="6"
        maxlength="3000"
        placeholder="把粉丝评论粘贴到这里，一行一条，例如：&#10;博主用的是什么相机呀？&#10;学到了学到了，已三连！&#10;感觉也就那样吧，没说的那么好"
        @keydown.enter.meta.prevent="handleGenerate"
        @keydown.enter.ctrl.prevent="handleGenerate"
      ></textarea>
      <p class="comments-hint" :class="{ overflow: isOverflow }">
        已识别 {{ parsedComments.length }} 条评论<template v-if="isOverflow">，超出上限，仅处理前 {{ MAX_COMMENTS }} 条</template>
      </p>

      <div class="field-group">
        <span class="field-label">回复语气</span>
        <div class="option-row">
          <button
            v-for="t in TONES"
            :key="t.value"
            type="button"
            class="option-chip"
            :class="{ active: tone === t.value }"
            @click="tone = t.value"
          >{{ t.label }}</button>
        </div>
        <p class="tone-hint">{{ activeToneHint }}</p>
      </div>

      <div class="field-group">
        <label class="pinned-toggle">
          <input v-model="includePinned" type="checkbox" class="pinned-checkbox" />
          <span class="pinned-label">同时生成一条「置顶引导评论」</span>
          <span class="pinned-desc">置顶在自己评论区，引导点赞 / 关注 / 看主页</span>
        </label>
      </div>

      <div class="field-group">
        <label class="field-label" for="brand-select">品牌人设（可选）</label>
        <select
          v-if="brands.length > 0"
          id="brand-select"
          v-model="selectedBrandId"
          class="brand-select"
        >
          <option value="">不使用品牌人设</option>
          <option v-for="b in brands" :key="b.id" :value="b.id">
            {{ b.name }}{{ b.id === activeBrandId ? '（当前启用）' : '' }}
          </option>
        </select>
        <p v-else-if="brandsLoaded" class="brand-empty-hint">
          还没有品牌档案，<RouterLink to="/tools/brand" class="brand-link">去创建</RouterLink>
        </p>
      </div>

      <button
        type="button"
        class="btn btn-primary generate-btn"
        :disabled="loading || parsedComments.length === 0"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '正在生成神回复…' : '生成神回复' }}
      </button>
    </div>

    <!-- 最近记录（本地存档） -->
    <div v-if="archive.length > 0" class="card history-card">
      <button type="button" class="history-toggle" @click="showArchive = !showArchive">
        <span class="history-title">最近记录（{{ archive.length }}）</span>
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
            <span class="history-summary">{{ entry.summary }} · {{ entry.payload.replies.length }} 条回复</span>
            <span class="history-time">{{ formatArchiveTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && replies.length === 0" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 2" :key="n" class="skeleton-card">
        <div class="sk-comment-row">
          <span class="sk-avatar"></span>
          <span class="sk-line sk-comment"></span>
        </div>
        <div class="sk-suggestion">
          <span class="sk-line sk-index"></span>
          <span class="sk-line sk-text"></span>
        </div>
        <div class="sk-suggestion">
          <span class="sk-line sk-index"></span>
          <span class="sk-line sk-text sk-text-short"></span>
        </div>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="replies.length > 0" class="result-section">
      <!-- 置顶引导评论 -->
      <div v-if="pinnedComment" class="pinned-card">
        <div class="pinned-head">
          <span class="pinned-badge">
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 17v5"/><path d="M9 10.76a2 2 0 0 1-1.11 1.79l-1.78.9A2 2 0 0 0 5 15.24V16a1 1 0 0 0 1 1h12a1 1 0 0 0 1-1v-.76a2 2 0 0 0-1.11-1.79l-1.78-.9A2 2 0 0 1 15 10.76V7a1 1 0 0 1 1-1 2 2 0 0 0 0-4H8a2 2 0 0 0 0 4 1 1 0 0 1 1 1z"/></svg>
            置顶引导评论
          </span>
          <button
            type="button"
            class="copy-btn"
            :class="{ copied: copiedText === pinnedComment }"
            @click="handleCopy(pinnedComment)"
          >
            {{ copiedText === pinnedComment ? '已复制' : '复制' }}
          </button>
        </div>
        <p class="pinned-text">{{ pinnedComment }}</p>
      </div>

      <div class="result-toolbar">
        <span class="result-count">共 {{ replies.length }} 条评论的回复建议</span>
        <button
          type="button"
          class="crosslink-btn"
          title="把这批评论带到评论洞察工具，聚类挖掘粉丝痛点与选题"
          @click="goInsightWithComments"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/><path d="M11 8v6"/><path d="M8 11h6"/></svg>
          用这批评论挖选题痛点
        </button>
      </div>

      <div class="reply-list">
        <div
          v-for="(item, i) in replies"
          :key="`${i}-${item.comment}`"
          class="reply-card"
          :style="{ '--i': i }"
        >
          <div class="comment-row">
            <span class="comment-avatar">粉</span>
            <p class="comment-text">{{ item.comment }}</p>
          </div>
          <div v-if="item.suggestions.length > 0" class="suggestion-list">
            <div
              v-for="(s, j) in item.suggestions"
              :key="j"
              class="suggestion-row"
            >
              <span class="suggestion-index">回复 {{ j + 1 }}</span>
              <p class="suggestion-text">{{ s }}</p>
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: copiedText === s }"
                @click="handleCopy(s)"
              >
                {{ copiedText === s ? '已复制' : '复制' }}
              </button>
            </div>
          </div>
          <p v-else class="suggestion-empty">这条评论没有生成有效建议，重新生成试试</p>
        </div>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M7.9 20A9 9 0 1 0 4 16.1L2 22Z"/><path d="M8 12h.01"/><path d="M12 12h.01"/><path d="M16 12h.01"/></svg>
      </div>
      <p class="empty-title">{{ hasGenerated ? '没有生成有效的回复建议' : '还没有回复建议' }}</p>
      <p class="empty-desc">{{ hasGenerated ? '换个说法或换个语气，重新生成试试吧' : '把粉丝评论粘贴到上方（一行一条），选好语气后点「生成神回复」' }}</p>
      <p v-if="!hasGenerated" class="empty-example">每条评论都会给出多个可复制的回复建议</p>
    </div>

    <ErrorCard
      v-if="error"
      class="reply-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { generateReplies, type ReplyItem, type ReplyTone } from '../api/reply'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'
import { setCommentHandoff, takeCommentHandoff } from '../utils/commentHandoff'
import {
  REPLY_ARCHIVE_KEY,
  addToolArchiveEntry,
  createToolArchiveEntry,
  formatArchiveTime,
  isValidReplyPayload,
  loadToolArchive,
  saveToolArchive,
  type ReplyArchivePayload,
  type ToolArchiveEntry,
} from '../utils/toolArchive'
import ErrorCard from '../components/common/ErrorCard.vue'

const MAX_COMMENTS = 20

const TONES: ReadonlyArray<{ value: ReplyTone; label: string; hint: string }> = [
  { value: '热情', label: '热情', hint: '高能量、有感染力，让粉丝感觉被热烈欢迎' },
  { value: '专业', label: '专业', hint: '干货感、可信赖，用简洁专业的表达展示功底' },
  { value: '幽默', label: '幽默', hint: '有梗会接梗，轻松诙谐带动评论区氛围' },
  { value: '温暖', label: '温暖', hint: '共情治愈，先接住对方情绪再温柔回应' }
] as const

const router = useRouter()

const commentsInput = ref('')
const tone = ref<ReplyTone>(TONES[0].value)
const includePinned = ref(true)
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const replies = ref<ReplyItem[]>([])
const pinnedComment = ref('')
const copiedText = ref('')

// 最近记录（本地存档，最近 10 次生成结果）
const archive = ref<Array<ToolArchiveEntry<ReplyArchivePayload>>>(
  loadToolArchive(REPLY_ARCHIVE_KEY, isValidReplyPayload)
)
const showArchive = ref(false)

// 来自评论洞察的预填提示（挂载时检测 sessionStorage）
const handoffFromInsight = ref(false)

// 品牌人设选择：'' 表示不使用，默认选中当前启用档案
const brands = ref<BrandKit[]>([])
const activeBrandId = ref<string | null>(null)
const selectedBrandId = ref('')
const brandsLoaded = ref(false)

onMounted(async () => {
  // 检测评论洞察带过来的评论：预填输入框并提示来源
  const handoff = takeCommentHandoff()
  if (handoff && handoff.source === 'insight') {
    commentsInput.value = handoff.comments.join('\n')
    handoffFromInsight.value = true
  }

  const res = await getBrandList()
  if (res.success) {
    brands.value = res.brands
    activeBrandId.value = res.active_id
    if (res.active_id && res.brands.some(b => b.id === res.active_id)) {
      selectedBrandId.value = res.active_id
    }
  }
  brandsLoaded.value = true
})

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

const activeToneHint = computed(() =>
  TONES.find(t => t.value === tone.value)?.hint ?? ''
)

async function handleGenerate() {
  if (parsedComments.value.length === 0 || loading.value) return

  loading.value = true
  error.value = null

  const usedComments = parsedComments.value.slice(0, MAX_COMMENTS)

  try {
    const result = await generateReplies({
      comments: usedComments,
      tone: tone.value,
      includePinned: includePinned.value,
      brandId: selectedBrandId.value || undefined
    })

    if (result.success && result.replies) {
      replies.value = result.replies
      pinnedComment.value = result.pinned_comment || ''
      hasGenerated.value = true
      recordArchive(usedComments, result.replies, result.pinned_comment || '')
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成回复失败',
        '生成回复失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成回复失败')
  } finally {
    loading.value = false
  }
}

// ==================== 最近记录（本地存档） ====================

function recordArchive(usedComments: string[], resultReplies: ReplyItem[], pinned: string) {
  if (resultReplies.length === 0) return
  const entry = createToolArchiveEntry<ReplyArchivePayload>({
    input: usedComments.join(' '),
    payload: {
      comments: usedComments,
      tone: tone.value,
      includePinned: includePinned.value,
      replies: resultReplies,
      pinnedComment: pinned,
    },
  })
  archive.value = addToolArchiveEntry(archive.value, entry)
  saveToolArchive(REPLY_ARCHIVE_KEY, archive.value)
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: ToolArchiveEntry<ReplyArchivePayload>) {
  if (loading.value) return
  commentsInput.value = entry.payload.comments.join('\n')
  if (TONES.some(t => t.value === entry.payload.tone)) {
    tone.value = entry.payload.tone
  }
  includePinned.value = entry.payload.includePinned
  replies.value = entry.payload.replies
  pinnedComment.value = entry.payload.pinnedComment
  hasGenerated.value = true
  error.value = null
}

// ==================== 与评论洞察互通 ====================

/**
 * 把当前结果对应的这批评论带到评论洞察工具挖选题痛点
 * （sessionStorage 传递，洞察页挂载时预填并提示来源）
 */
function goInsightWithComments() {
  const comments = replies.value.map(r => r.comment).filter(Boolean)
  if (comments.length === 0) return
  setCommentHandoff({ source: 'reply', comments })
  router.push('/tools/insight')
}

async function handleCopy(text: string) {
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
  copiedText.value = text
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedText.value = '' }, 1500)
}
</script>

<style scoped>
.reply-container {
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
  min-height: 130px;
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

.option-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.option-chip {
  padding: 7px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.option-chip:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.option-chip:active {
  transform: translateY(0);
  box-shadow: none;
}

.option-chip.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
  box-shadow: var(--shadow-focus);
}

.option-chip.active:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
}

.tone-hint {
  margin: 10px 2px 0;
  font-size: 13px;
  color: var(--text-sub);
}

.pinned-toggle {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
  cursor: pointer;
}

.pinned-checkbox {
  width: 16px;
  height: 16px;
  accent-color: var(--primary);
  cursor: pointer;
}

.pinned-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.pinned-desc {
  font-size: 12.5px;
  color: var(--text-sub);
}

/* ── 品牌人设选择（与标题工坊同款） ── */
.brand-select {
  width: 100%;
  max-width: 320px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.brand-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.brand-empty-hint {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-sub);
}

.brand-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.brand-link:hover {
  text-decoration: underline;
}

/* ── 来自评论洞察的预填提示 ── */
.handoff-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 16px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--primary);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 13.5px;
  font-weight: 500;
}

.handoff-close {
  margin-left: auto;
  border: none;
  background: transparent;
  color: var(--primary);
  font-size: 16px;
  line-height: 1;
  cursor: pointer;
}

/* 生成按钮基于全局 .btn btn-primary，仅覆盖布局 */
.generate-btn {
  margin-top: 22px;
  width: 100%;
}

/* ── 最近记录（本地存档，样式参照选题灵感的历史区） ── */
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

/* ── 置顶引导评论 ───────────────── */
.pinned-card {
  background: var(--primary-light);
  border: 1px solid var(--primary);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  margin-bottom: 20px;
  box-shadow: var(--shadow-xs);
  animation: fadeIn 0.4s var(--ease-out);
}

.pinned-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 10px;
}

.pinned-badge {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 4px 12px;
  border-radius: var(--radius-full);
  background: var(--primary);
  color: #fff;
  font-size: 12.5px;
  font-weight: 600;
}

.pinned-text {
  margin: 0;
  font-size: 15px;
  color: var(--text-main);
  line-height: 1.7;
  word-break: break-word;
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

.sk-line,
.sk-avatar {
  display: block;
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-line {
  height: 14px;
  border-radius: var(--radius-full);
}

.sk-comment-row {
  display: flex;
  align-items: center;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border-color);
}

.sk-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
}

.sk-comment { width: 55%; }

.sk-suggestion {
  display: flex;
  align-items: center;
  gap: 10px;
}

.sk-index {
  flex-shrink: 0;
  width: 56px;
  height: 20px;
}

.sk-text { flex: 1; max-width: 78%; }
.sk-text-short { max-width: 56%; }

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
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
  padding: 0 4px;
}

.result-count {
  font-size: 14px;
  color: var(--text-sub);
}

/* 「用这批评论挖选题痛点」互跳按钮 */
.crosslink-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--primary);
  background: var(--bg-card);
  color: var(--primary);
  font-size: var(--font-size-caption);
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.crosslink-btn:hover {
  background: var(--primary-light);
  box-shadow: var(--shadow-xs);
}

.reply-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.reply-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base), border-color var(--transition-base),
    transform var(--transition-base);
  animation: fadeIn 0.4s var(--ease-out) both;
  animation-delay: calc(min(var(--i, 0), 8) * 50ms);
}

.reply-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.comment-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding-bottom: 12px;
  border-bottom: 1px dashed var(--border-color);
}

.comment-avatar {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-2);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
}

.comment-text {
  margin: 2px 0 0;
  font-size: 14.5px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.55;
  word-break: break-word;
}

.suggestion-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
  margin-top: 12px;
}

.suggestion-row {
  display: flex;
  align-items: flex-start;
  gap: 10px;
}

.suggestion-index {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--primary-fade);
  color: var(--primary);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.suggestion-text {
  flex: 1;
  min-width: 0;
  margin: 0;
  font-size: 14.5px;
  color: var(--text-main);
  line-height: 1.65;
  word-break: break-word;
}

.suggestion-empty {
  margin: 12px 0 0;
  font-size: 13.5px;
  color: var(--text-sub);
}

.copy-btn {
  flex-shrink: 0;
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

.reply-error {
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
  .reply-container {
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

  .option-chip {
    padding: 6px 13px;
    font-size: 13px;
  }

  .reply-card {
    padding: 14px;
  }

  .suggestion-row {
    flex-wrap: wrap;
  }

  .suggestion-text {
    flex-basis: 100%;
    order: 1;
  }

  .suggestion-index {
    order: 0;
  }

  .copy-btn {
    order: 0;
    margin-left: auto;
  }

  .pinned-card {
    padding: 14px;
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
  .pinned-card,
  .reply-card,
  .empty-state,
  .reply-error {
    animation: none;
  }

  .sk-line,
  .sk-avatar {
    animation: none;
    background: var(--gray-2);
  }

  .option-chip,
  .option-chip:hover,
  .copy-btn,
  .copy-btn:hover,
  .reply-card:hover {
    transform: none;
  }
}
</style>
