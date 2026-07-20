<template>
  <div class="container cover-container">
    <!-- 页头 -->
    <div class="cover-header">
      <h1 class="page-title">封面 A/B 方向</h1>
      <p class="page-subtitle">输入主题，AI 一次生成多个差异化封面方向，并排对比选出最能打的那一个</p>
    </div>

    <!-- 输入区 -->
    <div class="card cover-form">
      <div class="form-field">
        <label class="form-label" for="cover-topic">主题 <span class="required-mark">*</span></label>
        <input
          id="cover-topic"
          v-model="topic"
          class="form-input"
          type="text"
          placeholder="例如：新手化妆避坑指南"
          maxlength="100"
          :disabled="loading"
          @keyup.enter="handleGenerate"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="cover-content">补充内容/背景（可选）</label>
        <textarea
          id="cover-content"
          v-model="content"
          class="form-textarea"
          rows="3"
          placeholder="可粘贴笔记正文、卖点、目标人群等，帮助 AI 更贴合内容"
          maxlength="2000"
          :disabled="loading"
        ></textarea>
      </div>

      <button
        type="button"
        class="btn btn-primary generate-btn"
        :disabled="loading || !topic.trim()"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '生成中，约需 10-30 秒…' : directions.length > 0 ? '重新生成方向' : '生成封面方向' }}
      </button>
    </div>

    <!-- 最近记录（本地存档，样式与其他工具的历史区一致） -->
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
            <span class="history-summary">{{ entry.summary }} · {{ entry.payload.directions.length }} 个方向</span>
            <span v-if="adoptedLabel(entry)" class="adopted-badge">已采用 {{ adoptedLabel(entry) }}</span>
            <span class="history-time">{{ formatArchiveTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && directions.length === 0" class="skeleton-grid" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <div class="sk-row">
          <span class="sk-line sk-label"></span>
        </div>
        <div class="sk-score-row">
          <span class="sk-line sk-score"></span>
          <span class="sk-line sk-bar"></span>
        </div>
        <span class="sk-line sk-title"></span>
        <span class="sk-line"></span>
        <span class="sk-line sk-short"></span>
      </div>
    </div>

    <!-- 结果对比区 -->
    <div v-if="directions.length > 0" class="directions-grid">
      <div
        v-for="(direction, index) in directions"
        :key="index"
        class="direction-card"
        :class="{ 'direction-card-best': index === bestIndex }"
        :style="{ '--i': index }"
      >
        <div class="card-top">
          <span class="direction-label">方向 {{ String.fromCharCode(65 + index) }}</span>
          <span v-if="index === bestIndex" class="best-badge">推荐</span>
        </div>

        <!-- 评分 -->
        <div class="score-row">
          <div class="score-value">{{ direction.score }}</div>
          <div class="score-meta">
            <span class="score-caption">预估点击力</span>
            <div class="score-bar">
              <div class="score-bar-fill" :style="{ width: direction.score + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- 文案 -->
        <div class="direction-title">{{ direction.title }}</div>
        <div v-if="direction.subtitle" class="direction-subtitle">{{ direction.subtitle }}</div>
        <div v-if="direction.style" class="style-tag">{{ direction.style }}</div>

        <!-- 视觉概念 -->
        <div class="section-block">
          <div class="section-caption">视觉概念</div>
          <p class="section-text">{{ direction.visual_concept }}</p>
        </div>

        <!-- 点击理由 -->
        <div class="section-block">
          <div class="section-caption">为什么可能更吸引点击</div>
          <p class="section-text">{{ direction.reason }}</p>
        </div>

        <!-- 送创作 + 复制操作 -->
        <div class="card-actions card-actions-use">
          <button
            type="button"
            class="use-direction-btn"
            :aria-label="`带着方向 ${String.fromCharCode(65 + index)} 的标题与视觉概念开始新创作`"
            title="标题与视觉概念将带入创作中心，开始一次新创作"
            @click="useDirectionForCreation(direction)"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
            用这个方向创作
          </button>
        </div>
        <p class="use-direction-hint">将带着该方向的标题与视觉概念开始新创作</p>
        <div class="card-actions">
          <button
            type="button"
            class="copy-btn"
            :class="{ copied: copiedKey === copyKeyOf(index, 'text') }"
            :aria-label="`复制方向 ${String.fromCharCode(65 + index)} 的文案`"
            @click="copyText(copyKeyOf(index, 'text'), buildCopyText(direction))"
          >
            {{ copiedKey === copyKeyOf(index, 'text') ? '已复制 ✓' : '复制文案' }}
          </button>
          <button
            type="button"
            class="copy-btn copy-btn-secondary"
            :class="{ copied: copiedKey === copyKeyOf(index, 'visual') }"
            :aria-label="`复制方向 ${String.fromCharCode(65 + index)} 的视觉概念`"
            @click="copyText(copyKeyOf(index, 'visual'), direction.visual_concept)"
          >
            {{ copiedKey === copyKeyOf(index, 'visual') ? '已复制 ✓' : '复制视觉概念' }}
          </button>
          <button
            v-if="currentEntryId"
            type="button"
            class="copy-btn copy-btn-secondary adopt-btn"
            :class="{ adopted: isAdopted(index) }"
            :aria-label="`标记方向 ${String.fromCharCode(65 + index)} ${isAdopted(index) ? '取消已采用' : '为已采用'}`"
            title="记录你实际采用了哪个封面方向，沉淀到最近记录里"
            @click="toggleAdopted(index)"
          >
            {{ isAdopted(index) ? '已采用 ✓' : '标记已采用' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><rect width="18" height="18" x="3" y="3" rx="2" ry="2"/><circle cx="9" cy="9" r="2"/><path d="m21 15-3.086-3.086a2 2 0 0 0-2.828 0L6 21"/></svg>
      </div>
      <p class="empty-title">封面方向会在这里并排对比</p>
      <p class="empty-desc">输入主题，AI 会一次生成多个差异化方向，标注预估点击力与视觉概念，帮你选出最能打的那一个</p>
      <p class="empty-example">试试：新手化妆避坑指南</p>
    </div>

    <ErrorCard
      v-if="error"
      class="cover-error"
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
import { generateCoverDirections, type CoverDirection } from '../api/cover'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  COVER_ARCHIVE_KEY,
  addToolArchiveEntry,
  createToolArchiveEntry,
  formatArchiveTime,
  isValidCoverPayload,
  loadToolArchive,
  saveToolArchive,
  type CoverArchivePayload,
  type ToolArchiveEntry,
} from '../utils/toolArchive'
import ErrorCard from '../components/common/ErrorCard.vue'

const router = useRouter()
const store = useGeneratorStore()

const topic = ref('')
const content = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const directions = ref<CoverDirection[]>([])

// 最近记录（本地存档，最近 10 次生成结果 + 已采用标记）
const archive = ref<Array<ToolArchiveEntry<CoverArchivePayload>>>(
  loadToolArchive(COVER_ARCHIVE_KEY, isValidCoverPayload)
)
const showArchive = ref(false)
// 当前结果区对应的存档条目 ID（「标记已采用」写回这条存档）
const currentEntryId = ref('')

/** 已复制标记（key 形如 "0-text"），短暂显示"已复制"反馈 */
const copiedKey = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copiedTimer !== undefined) clearTimeout(copiedTimer)
})

/** 评分最高的方向下标，用于"推荐"角标 */
const bestIndex = computed(() => {
  if (directions.value.length === 0) return -1
  let best = 0
  directions.value.forEach((d, i) => {
    if (d.score > directions.value[best].score) best = i
  })
  return best
})

function copyKeyOf(index: number, kind: 'text' | 'visual') {
  return `${index}-${kind}`
}

/** 拼装可直接粘贴使用的文案（主标题 + 副标题 + 风格） */
function buildCopyText(direction: CoverDirection) {
  const lines = [direction.title]
  if (direction.subtitle) lines.push(direction.subtitle)
  if (direction.style) lines.push(`风格：${direction.style}`)
  return lines.join('\n')
}

async function copyText(key: string, text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文降级：用临时 textarea 复制
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
  if (copiedTimer !== undefined) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedKey.value = ''
  }, 1500)
}

/**
 * 用这个封面方向开始新创作：
 * - 方向标题（含副标题）与用户输入的主题组合成主题文本写入 generator store
 *   （与选题工具「用这个创作」同款的多行主题范式）
 * - 视觉概念通过 setStylePrompt 注入，供后续生成链路沿用
 * - 跳回首页创作流程
 */
function useDirectionForCreation(direction: CoverDirection) {
  const userTopic = topic.value.trim()
  const coverTitle = direction.subtitle
    ? `${direction.title}（${direction.subtitle}）`
    : direction.title

  const lines = userTopic ? [userTopic, `封面方向：${coverTitle}`] : [coverTitle]
  if (direction.style) {
    lines.push(`风格倾向：${direction.style}`)
  }
  store.setTopic(lines.join('\n'))
  store.setStylePrompt(direction.visual_concept || '')
  router.push('/')
}

async function handleGenerate() {
  if (!topic.value.trim() || loading.value) return

  loading.value = true
  error.value = null

  try {
    const result = await generateCoverDirections(
      topic.value.trim(),
      content.value.trim() || undefined
    )

    if (result.success && result.directions && result.directions.length > 0) {
      directions.value = result.directions
      recordArchive(result.directions)
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成封面方向失败',
        '生成封面方向失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成封面方向失败')
  } finally {
    loading.value = false
  }
}

// ==================== 最近记录（本地存档 + 已采用标记） ====================

/** 生成成功后自动存档（主题 + 方向数组，「已采用」标记初始为全 false） */
function recordArchive(resultDirections: CoverDirection[]) {
  const entry = createToolArchiveEntry<CoverArchivePayload>({
    input: topic.value.trim(),
    payload: {
      topic: topic.value.trim(),
      content: content.value.trim(),
      directions: resultDirections,
      adopted: resultDirections.map(() => false),
    },
  })
  archive.value = addToolArchiveEntry(archive.value, entry)
  saveToolArchive(COVER_ARCHIVE_KEY, archive.value)
  currentEntryId.value = entry.id
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: ToolArchiveEntry<CoverArchivePayload>) {
  if (loading.value) return
  topic.value = entry.payload.topic
  content.value = entry.payload.content
  directions.value = entry.payload.directions
  currentEntryId.value = entry.id
  error.value = null
}

/** 当前结果区对应的存档条目（「已采用」的读写目标） */
function currentEntry(): ToolArchiveEntry<CoverArchivePayload> | undefined {
  return archive.value.find(entry => entry.id === currentEntryId.value)
}

/** 某个方向是否已被标记采用 */
function isAdopted(index: number): boolean {
  return currentEntry()?.payload.adopted[index] === true
}

/** 切换「已采用」标记并写回存档（为将来的封面胜率统计沉淀数据） */
function toggleAdopted(index: number) {
  const entry = currentEntry()
  if (!entry) return
  entry.payload.adopted[index] = !entry.payload.adopted[index]
  saveToolArchive(COVER_ARCHIVE_KEY, archive.value)
}

/** 存档条目的已采用徽标文案：把已采用方向的下标转成 A/B/C 字母 */
function adoptedLabel(entry: ToolArchiveEntry<CoverArchivePayload>): string {
  return entry.payload.adopted
    .map((flag, i) => (flag ? String.fromCharCode(65 + i) : ''))
    .filter(Boolean)
    .join('/')
}
</script>

<style scoped>
.cover-container {
  max-width: 1100px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.cover-header {
  text-align: center;
  margin-bottom: 28px;
  animation: fadeIn 0.6s var(--ease-out);
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

/* 输入表单（基于全局 .card，仅覆盖布局） */
.cover-form {
  padding: var(--space-6);
  margin-bottom: var(--space-6);
}

.form-field {
  margin-bottom: 18px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.required-mark {
  color: var(--primary);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 12px 14px;
  font-size: 14px;
  color: var(--text-main);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    background var(--transition-fast);
  font-family: inherit;
  box-sizing: border-box;
}

.form-textarea {
  resize: vertical;
  line-height: 1.6;
}

.form-input:focus,
.form-textarea:focus {
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: var(--shadow-focus);
  outline: none;
}

.form-input:disabled,
.form-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* ── 最近记录（本地存档，样式照抄其他工具的历史区） ── */
.history-card {
  margin: 0 0 var(--space-6);
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

/* 存档条目上的已采用徽标 */
.adopted-badge {
  flex-shrink: 0;
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--color-success);
  background: var(--color-success-soft);
  border-radius: var(--radius-full);
  white-space: nowrap;
}

/* 加载骨架（纯 CSS shimmer） */
.skeleton-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.skeleton-card {
  display: flex;
  flex-direction: column;
  gap: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-xs);
}

.sk-line {
  display: block;
  height: 13px;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-label { width: 64px; }

.sk-score-row {
  display: flex;
  align-items: center;
  gap: 12px;
}

.sk-score {
  width: 52px;
  height: 32px;
  border-radius: var(--radius-sm);
}

.sk-bar { flex: 1; height: 6px; }
.sk-title { width: 70%; height: 18px; }
.sk-short { width: 45%; }

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* 方向对比网格 */
.directions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
}

.direction-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-5);
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base), transform var(--transition-base),
    border-color var(--transition-base);
  animation: fadeIn 0.45s var(--ease-out) both;
  animation-delay: calc(var(--i, 0) * 80ms);
}

.direction-card:hover {
  box-shadow: var(--shadow-hover);
  border-color: var(--border-hover);
  transform: translateY(-2px);
}

.direction-card-best {
  border-color: var(--primary);
  box-shadow: var(--shadow-xs), 0 4px 16px var(--primary-fade);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.direction-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-sub);
  letter-spacing: 0.5px;
}

.best-badge {
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  border-radius: var(--radius-full);
}

/* 评分 */
.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.score-value {
  font-size: 32px;
  font-weight: 800;
  letter-spacing: var(--tracking-tighter);
  color: var(--primary);
  line-height: 1;
}

.score-meta {
  flex: 1;
  min-width: 0;
}

.score-caption {
  display: block;
  font-size: 12px;
  color: var(--text-sub);
  margin-bottom: 4px;
}

.score-bar {
  height: 6px;
  background: var(--gray-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: var(--radius-full);
  transition: width 0.4s var(--ease-out);
}

/* 文案 */
.direction-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.4;
  margin-bottom: 6px;
}

.direction-subtitle {
  font-size: 14px;
  color: var(--text-sub);
  margin-bottom: 10px;
}

.style-tag {
  display: inline-block;
  align-self: flex-start;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--text-sub);
  background: var(--gray-2);
  border-radius: var(--radius-full);
  margin-bottom: 12px;
}

.section-block {
  margin-bottom: 12px;
}

.section-caption {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: 4px;
}

.section-text {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.7;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 复制操作 */
.card-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: auto;
  padding-top: 12px;
}

/* 「标记已采用」切换：选中后走 success 语义色 */
.adopt-btn.adopted {
  background: var(--color-success-soft);
  color: var(--color-success);
}

/* 送创作按钮行：贴在卡片底部动作区最上方 */
.card-actions-use {
  margin-top: auto;
  padding-top: 12px;
}

.card-actions-use + .use-direction-hint + .card-actions {
  margin-top: 0;
  padding-top: 10px;
}

.use-direction-btn {
  flex: 1;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 10px 12px;
  font-size: 14px;
  font-weight: 600;
  color: #fff;
  background: var(--primary);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.use-direction-btn:hover {
  background: var(--primary-hover);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.use-direction-btn:active {
  background: var(--primary-active);
  transform: translateY(0);
  box-shadow: none;
}

.use-direction-hint {
  margin: 6px 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: center;
}

.copy-btn {
  flex: 1;
  padding: 9px 12px;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  border: none;
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
}

.copy-btn:hover {
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.copy-btn:active {
  transform: translateY(0);
  box-shadow: none;
}

.copy-btn.copied {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.copy-btn-secondary {
  color: var(--text-sub);
  background: var(--gray-2);
}

.copy-btn-secondary:hover {
  color: var(--text-main);
}

.copy-btn-secondary.copied {
  background: var(--color-success-soft);
  color: var(--color-success);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 48px 20px;
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
  margin: 0 0 var(--space-2);
  font-size: var(--font-size-body);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.empty-desc {
  margin: 0 auto;
  max-width: 480px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-sub);
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

.cover-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
}

/* 移动端 */
@media (max-width: 768px) {
  .cover-form {
    padding: 20px;
  }

  .directions-grid {
    grid-template-columns: 1fr;
  }

  .generate-btn {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 640px) {
  .cover-container {
    padding-top: 12px;
  }

  .cover-form {
    padding: 18px 16px;
  }

  .direction-card {
    padding: 16px;
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
  .cover-header,
  .direction-card,
  .empty-state,
  .cover-error {
    animation: none;
  }

  .sk-line {
    animation: none;
    background: var(--gray-2);
  }

  .direction-card:hover,
  .copy-btn,
  .copy-btn:hover,
  .use-direction-btn,
  .use-direction-btn:hover {
    transform: none;
  }

  .score-bar-fill {
    transition: none;
  }
}
</style>
