<template>
  <div class="container script-container">
    <div class="script-header">
      <h1 class="page-title">口播视频脚本</h1>
      <p class="page-subtitle">粘贴图文内容或输入主题，AI 帮你生成带时间轴分镜的短视频口播脚本</p>
    </div>

    <!-- 输入区 -->
    <div class="card script-card">
      <label class="field-label" for="script-input">图文内容 / 主题</label>
      <textarea
        id="script-input"
        v-model="content"
        class="script-textarea"
        rows="7"
        placeholder="粘贴你的图文正文或大纲，或直接输入一个主题…"
      ></textarea>

      <div class="field-block">
        <span class="field-label">视频时长</span>
        <div class="option-chips">
          <button
            v-for="d in durations"
            :key="d.code"
            type="button"
            class="option-chip"
            :class="{ active: duration === d.code }"
            @click="duration = d.code"
          >
            {{ d.label }}
          </button>
        </div>
      </div>

      <div class="field-block">
        <span class="field-label">场景类型</span>
        <div class="option-chips">
          <button
            v-for="s in scenes"
            :key="s.code"
            type="button"
            class="option-chip"
            :class="{ active: scene === s.code }"
            @click="scene = s.code"
          >
            {{ s.label }}
          </button>
        </div>
      </div>

      <div class="field-row">
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
        <span v-else-if="brandsLoaded" class="brand-empty-hint">
          还没有品牌档案，<RouterLink to="/tools/brand" class="brand-link">去创建</RouterLink>
        </span>
      </div>

      <div class="submit-row">
        <button
          type="button"
          class="btn btn-primary script-btn"
          :disabled="loading || !content.trim()"
          @click="handleGenerate"
        >
          <span v-if="loading" class="spinner-sm"></span>
          {{ loading ? '生成中…' : '生成脚本' }}
        </button>
      </div>
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
            <span class="history-summary">{{ entry.summary }} · {{ durationLabel(entry.payload.duration) }} · {{ sceneLabel(entry.payload.scene) }}</span>
            <span class="history-time">{{ formatArchiveTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && !script" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="card skeleton-card">
        <div class="sk-row">
          <span class="sk-line sk-badge"></span>
          <span class="sk-line sk-btn"></span>
        </div>
        <span class="sk-line sk-title"></span>
        <span class="sk-line"></span>
        <span class="sk-line sk-short"></span>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="script" class="results-section">
      <!-- 整体信息 -->
      <div class="card overview-card" :style="{ '--i': 0 }">
        <div class="overview-header">
          <span class="overview-badge">{{ durationLabel(script.duration) }} · {{ sceneLabel(script.scene) }}</span>
          <button
            type="button"
            class="btn btn-secondary copy-btn"
            :class="{ copied: copiedKey === 'all' }"
            aria-label="复制完整脚本"
            @click="copyAll"
          >
            {{ copiedKey === 'all' ? '已复制 ✓' : '复制全文' }}
          </button>
        </div>
        <h3 v-if="script.title" class="overview-title">{{ script.title }}</h3>
        <p v-if="script.hook" class="overview-line"><span class="line-label">开场钩子</span>{{ script.hook }}</p>
        <p v-if="script.bgm_mood" class="overview-line"><span class="line-label">BGM 情绪</span>{{ script.bgm_mood }}</p>
      </div>

      <!-- 时间轴分镜 -->
      <div
        v-for="(seg, index) in script.segments"
        :key="index"
        class="card segment-card"
        :style="{ '--i': index + 1 }"
      >
        <div class="segment-header">
          <span class="time-badge">{{ seg.time_range || `第 ${index + 1} 段` }}</span>
          <button
            type="button"
            class="btn btn-secondary copy-btn"
            :class="{ copied: copiedKey === `seg-${index}` }"
            :aria-label="`复制第 ${index + 1} 段台词`"
            @click="copySegment(seg, index)"
          >
            {{ copiedKey === `seg-${index}` ? '已复制 ✓' : '复制台词' }}
          </button>
        </div>
        <p v-if="seg.visual" class="segment-line"><span class="line-label">画面</span>{{ seg.visual }}</p>
        <p class="segment-voiceover">{{ seg.voiceover }}</p>
        <p v-if="seg.subtitle_notes" class="segment-line segment-subtitle">
          <span class="line-label">字幕断句</span>{{ seg.subtitle_notes }}
        </p>
      </div>

      <!-- 结尾 CTA -->
      <div v-if="script.cta" class="card cta-card" :style="{ '--i': script.segments.length + 1 }">
        <div class="segment-header">
          <span class="cta-badge">结尾 CTA</span>
        </div>
        <p class="segment-voiceover">{{ script.cta }}</p>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><polygon points="23 7 16 12 23 17 23 7"/><rect x="1" y="5" width="15" height="14" rx="2" ry="2"/></svg>
      </div>
      <p class="empty-title">图文一键变视频脚本</p>
      <p class="empty-desc">粘贴一篇图文正文、选好时长和场景，点击「生成脚本」，带时间轴的分镜脚本会在这里逐段展示</p>
      <p class="empty-example">试试：把一篇小红书穿搭笔记，变成 60 秒口播出镜脚本</p>
    </div>

    <ErrorCard
      v-if="error"
      class="script-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import {
  generateScript,
  type ScriptDuration,
  type ScriptScene,
  type ScriptSegment,
  type VideoScript
} from '../api/script'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  SCRIPT_ARCHIVE_KEY,
  addToolArchiveEntry,
  createToolArchiveEntry,
  formatArchiveTime,
  isValidScriptPayload,
  loadToolArchive,
  saveToolArchive,
  type ScriptArchivePayload,
  type ToolArchiveEntry,
} from '../utils/toolArchive'
import ErrorCard from '../components/common/ErrorCard.vue'

interface DurationOption {
  code: ScriptDuration
  label: string
}

interface SceneOption {
  code: ScriptScene
  label: string
}

const durations: DurationOption[] = [
  { code: '30s', label: '30 秒' },
  { code: '60s', label: '60 秒' },
  { code: '3min', label: '3 分钟' }
]

const scenes: SceneOption[] = [
  { code: 'talking_head', label: '口播出镜' },
  { code: 'voiceover', label: '图文配音' },
  { code: 'drama', label: '情景剧情' }
]

const content = ref('')
const duration = ref<ScriptDuration>('60s')
const scene = ref<ScriptScene>('talking_head')
const script = ref<VideoScript | null>(null)
const loading = ref(false)
const error = ref<AppError | null>(null)
// 当前已复制的目标：'' 空闲 / 'all' 全文 / `seg-${index}` 单段台词
const copiedKey = ref('')

// 最近记录（本地存档，最近 10 次生成结果）
const archive = ref<Array<ToolArchiveEntry<ScriptArchivePayload>>>(
  loadToolArchive(SCRIPT_ARCHIVE_KEY, isValidScriptPayload)
)
const showArchive = ref(false)

// 品牌人设选择：'' 表示不使用，默认选中当前启用档案
const brands = ref<BrandKit[]>([])
const activeBrandId = ref<string | null>(null)
const selectedBrandId = ref('')
const brandsLoaded = ref(false)

onMounted(async () => {
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

function durationLabel(code: string): string {
  return durations.find(d => d.code === code)?.label || code
}

function sceneLabel(code: string): string {
  return scenes.find(s => s.code === code)?.label || code
}

async function handleGenerate() {
  if (loading.value || !content.value.trim()) return

  loading.value = true
  error.value = null
  // 重新生成时保留旧脚本展示，新结果返回后再整体替换（这些都是花了额度的产物）

  try {
    const result = await generateScript(
      content.value.trim(),
      duration.value,
      scene.value,
      selectedBrandId.value || undefined
    )

    if (result.success && result.script) {
      script.value = result.script
      recordArchive(result.script)
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '脚本生成失败', '脚本生成失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '脚本生成失败')
  } finally {
    loading.value = false
  }
}

// ==================== 最近记录（本地存档） ====================

function recordArchive(resultScript: VideoScript) {
  const entry = createToolArchiveEntry<ScriptArchivePayload>({
    input: content.value.trim(),
    payload: {
      content: content.value.trim(),
      duration: duration.value,
      scene: scene.value,
      script: resultScript,
    },
  })
  archive.value = addToolArchiveEntry(archive.value, entry)
  saveToolArchive(SCRIPT_ARCHIVE_KEY, archive.value)
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: ToolArchiveEntry<ScriptArchivePayload>) {
  if (loading.value) return
  content.value = entry.payload.content
  if (durations.some(d => d.code === entry.payload.duration)) {
    duration.value = entry.payload.duration
  }
  if (scenes.some(s => s.code === entry.payload.scene)) {
    scene.value = entry.payload.scene
  }
  script.value = entry.payload.script
  error.value = null
}

let copyTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})

async function copyText(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文（非 https）降级：用临时 textarea + execCommand 复制
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
  copyTimer = setTimeout(() => {
    copiedKey.value = ''
  }, 1500)
}

/** 把完整脚本拼成可直接粘贴的纯文本 */
function buildFullText(s: VideoScript): string {
  const parts: string[] = []
  if (s.title) parts.push(`《${s.title}》`)
  if (s.hook) parts.push(`开场钩子：${s.hook}`)
  if (s.bgm_mood) parts.push(`BGM 情绪：${s.bgm_mood}`)

  s.segments.forEach((seg, i) => {
    const lines = [`【${seg.time_range || `第 ${i + 1} 段`}】`]
    if (seg.visual) lines.push(`画面：${seg.visual}`)
    lines.push(`台词：${seg.voiceover}`)
    if (seg.subtitle_notes) lines.push(`字幕断句：${seg.subtitle_notes}`)
    parts.push(lines.join('\n'))
  })

  if (s.cta) parts.push(`结尾 CTA：${s.cta}`)
  return parts.join('\n\n')
}

async function copyAll() {
  if (!script.value) return
  await copyText(buildFullText(script.value), 'all')
}

async function copySegment(seg: ScriptSegment, index: number) {
  await copyText(seg.voiceover, `seg-${index}`)
}
</script>

<style scoped>
.script-container {
  max-width: 860px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.script-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

.script-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.script-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  resize: vertical;
  min-height: 140px;
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.script-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.script-textarea::placeholder {
  color: var(--text-placeholder);
}

.field-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.brand-select {
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
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
  font-size: 14px;
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

.field-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.option-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.option-chip {
  padding: 8px 18px;
  background: var(--gray-2);
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.option-chip:hover {
  background: var(--bg-card);
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

.submit-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.script-btn {
  min-width: 180px;
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
}

.sk-line {
  display: block;
  height: 14px;
  border-radius: var(--radius-full);
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-badge { width: 72px; height: 24px; }
.sk-btn { width: 88px; height: 30px; border-radius: var(--radius-md); }
.sk-title { width: 55%; height: 18px; }
.sk-short { width: 40%; }

@keyframes shimmer {
  from { background-position: 200% 0; }
  to { background-position: -200% 0; }
}

/* 结果区 */
.results-section {
  margin-top: var(--space-5);
}

.overview-card,
.segment-card,
.cta-card {
  animation: fadeIn 0.4s var(--ease-out) both;
  animation-delay: calc(var(--i, 0) * 70ms);
}

.overview-header,
.segment-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.overview-badge,
.time-badge,
.cta-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.cta-badge {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.copy-btn {
  padding: 8px 18px;
  font-size: 14px;
}

.copy-btn.copied {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
}

.overview-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-3);
  line-height: 1.5;
}

.overview-line,
.segment-line {
  font-size: 14px;
  line-height: 1.8;
  color: var(--text-sub);
  margin-bottom: var(--space-2);
  word-break: break-word;
}

.line-label {
  display: inline-block;
  margin-right: 8px;
  font-weight: 600;
  color: var(--text-main);
  flex-shrink: 0;
}

.segment-voiceover {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: var(--space-2);
}

.segment-subtitle {
  margin-bottom: 0;
}

/* 空/初始态 */
.empty-state {
  margin-top: var(--space-5);
  text-align: center;
  padding: var(--space-7) var(--space-5);
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
  margin: 0;
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

.script-error {
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

/* 降低动效偏好：关闭入场与 shimmer 动画 */
@media (prefers-reduced-motion: reduce) {
  .overview-card,
  .segment-card,
  .cta-card,
  .empty-state,
  .script-error {
    animation: none;
  }

  .sk-line {
    animation: none;
    background: var(--gray-2);
  }

  .option-chip,
  .option-chip:hover {
    transform: none;
  }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .script-container {
    padding-top: 12px;
  }

  .card {
    padding: var(--space-5);
  }

  .field-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .brand-select {
    width: 100%;
  }

  .script-btn {
    width: 100%;
  }

  .overview-header,
  .segment-header {
    flex-wrap: wrap;
  }
}
</style>
