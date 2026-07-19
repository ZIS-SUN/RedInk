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
    <div class="input-card">
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

      <button
        type="button"
        class="generate-btn"
        :disabled="loading || parsedComments.length === 0"
        @click="handleGenerate"
      >
        <span v-if="loading" class="btn-spinner" aria-hidden="true"></span>
        {{ loading ? '正在生成神回复…' : '生成神回复' }}
      </button>
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
      </div>

      <div class="reply-list">
        <div v-for="(item, i) in replies" :key="`${i}-${item.comment}`" class="reply-card">
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
      <p class="empty-title">{{ hasGenerated ? '没有生成有效的回复建议' : '还没有回复建议' }}</p>
      <p class="empty-desc">{{ hasGenerated ? '换个说法或换个语气，重新生成试试吧' : '把粉丝评论粘贴到上方（一行一条），选好语气后点「生成神回复」' }}</p>
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
import { computed, ref } from 'vue'
import { generateReplies, type ReplyItem, type ReplyTone } from '../api/reply'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const MAX_COMMENTS = 20

const TONES: ReadonlyArray<{ value: ReplyTone; label: string; hint: string }> = [
  { value: '热情', label: '热情', hint: '高能量、有感染力，让粉丝感觉被热烈欢迎' },
  { value: '专业', label: '专业', hint: '干货感、可信赖，用简洁专业的表达展示功底' },
  { value: '幽默', label: '幽默', hint: '有梗会接梗，轻松诙谐带动评论区氛围' },
  { value: '温暖', label: '温暖', hint: '共情治愈，先接住对方情绪再温柔回应' }
] as const

const commentsInput = ref('')
const tone = ref<ReplyTone>(TONES[0].value)
const includePinned = ref(true)
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const replies = ref<ReplyItem[]>([])
const pinnedComment = ref('')
const copiedText = ref('')

let copyTimer: ReturnType<typeof setTimeout> | undefined

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

  try {
    const result = await generateReplies({
      comments: parsedComments.value.slice(0, MAX_COMMENTS),
      tone: tone.value,
      includePinned: includePinned.value
    })

    if (result.success && result.replies) {
      replies.value = result.replies
      pinnedComment.value = result.pinned_comment || ''
      hasGenerated.value = true
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
  animation: fadeIn 0.5s ease-out;
}

.brand-pill {
  display: inline-flex;
  align-items: center;
  padding: 6px 16px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
  margin-bottom: 16px;
  letter-spacing: 0.5px;
}

.page-title {
  font-size: 28px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0 0 10px;
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-sub);
  margin: 0 0 24px;
  line-height: 1.6;
}

/* ── 输入卡片 ───────────────────── */
.input-card {
  background: var(--bg-card);
  border-radius: 20px;
  padding: 24px;
  box-shadow: 0 8px 32px rgba(0, 0, 0, 0.06);
  animation: fadeIn 0.5s ease-out;
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
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  line-height: 1.6;
  resize: vertical;
  min-height: 130px;
  transition: border-color 0.2s;
  background: var(--bg-body);
}

.comments-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
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
  border-radius: 100px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.option-chip:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.option-chip.active {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
  font-weight: 600;
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

.generate-btn {
  margin-top: 22px;
  width: 100%;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 13px 24px;
  border: none;
  border-radius: 14px;
  background: linear-gradient(135deg, var(--primary) 0%, #FF5C72 100%);
  color: #fff;
  font-size: 16px;
  font-weight: 600;
  cursor: pointer;
  transition: opacity 0.2s, transform 0.15s;
}

.generate-btn:hover:not(:disabled) {
  transform: translateY(-1px);
}

.generate-btn:disabled {
  opacity: 0.55;
  cursor: not-allowed;
}

.btn-spinner {
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: #fff;
  border-radius: 50%;
  animation: spin 0.8s linear infinite;
}

/* ── 置顶引导评论 ───────────────── */
.pinned-card {
  background: linear-gradient(135deg, var(--primary-fade) 0%, rgba(255, 92, 114, 0.06) 100%);
  border: 1px solid var(--primary);
  border-radius: 16px;
  padding: 16px 18px;
  margin-bottom: 20px;
  animation: fadeIn 0.4s ease-out;
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
  border-radius: 100px;
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

/* ── 结果区 ─────────────────────── */
.result-section {
  margin-top: 28px;
  animation: fadeIn 0.4s ease-out;
}

.result-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
  padding: 0 4px;
}

.result-count {
  font-size: 14px;
  color: var(--text-sub);
}

.reply-list {
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.reply-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: 16px;
  padding: 16px 18px;
  transition: box-shadow 0.2s, border-color 0.2s;
}

.reply-card:hover {
  border-color: var(--border-hover);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
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
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--bg-body);
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
  border-radius: 100px;
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
  border-radius: 100px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
  white-space: nowrap;
}

.copy-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
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
  padding: 0 16px;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  margin: 0 0 6px;
}

.empty-desc {
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.7;
  margin: 0;
}

.reply-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
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
    border-radius: 16px;
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

@keyframes spin {
  to { transform: rotate(360deg); }
}
</style>
