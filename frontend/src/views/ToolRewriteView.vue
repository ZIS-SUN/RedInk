<template>
  <div class="container rewrite-container">
    <div class="rewrite-header">
      <h1 class="page-title">多平台文案改写</h1>
      <p class="page-subtitle">粘贴一段文案，AI 帮你一键改写成各平台的原生风格</p>
    </div>

    <!-- 输入区 -->
    <div class="card rewrite-card">
      <label class="field-label" for="rewrite-input">原始文案 / 主题</label>
      <textarea
        id="rewrite-input"
        v-model="content"
        class="rewrite-textarea"
        rows="7"
        placeholder="粘贴你的文案，或直接输入一个主题…"
      ></textarea>

      <div class="field-row">
        <label class="field-label" for="source-select">源平台（可选）</label>
        <select id="source-select" v-model="sourcePlatform" class="source-select">
          <option value="">通用 / 不指定</option>
          <option v-for="p in platforms" :key="p.code" :value="p.code">{{ p.label }}</option>
        </select>
      </div>

      <div class="field-row">
        <label class="field-label" for="brand-select">品牌人设（可选）</label>
        <select
          v-if="brands.length > 0"
          id="brand-select"
          v-model="selectedBrandId"
          class="source-select"
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

      <div class="field-block">
        <span class="field-label">目标平台（可多选）</span>
        <div class="platform-chips">
          <button
            v-for="p in platforms"
            :key="p.code"
            type="button"
            class="platform-chip"
            :class="{ active: targetPlatforms.includes(p.code) }"
            @click="toggleTarget(p.code)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <div class="submit-row">
        <button
          type="button"
          class="btn btn-primary rewrite-btn"
          :disabled="loading || !content.trim() || targetPlatforms.length === 0"
          @click="handleRewrite"
        >
          <span v-if="loading" class="spinner-sm"></span>
          {{ loading ? '改写中…' : '开始改写' }}
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
            <span class="history-summary">{{ entry.summary }} · {{ entry.payload.results.length }} 个平台版本</span>
            <span class="history-time">{{ formatArchiveTime(entry.createdAt) }}</span>
          </button>
        </li>
      </ul>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && results.length === 0" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 2" :key="n" class="card skeleton-card">
        <div class="sk-row">
          <span class="sk-line sk-badge"></span>
          <span class="sk-line sk-btn"></span>
        </div>
        <span class="sk-line sk-title"></span>
        <span class="sk-line"></span>
        <span class="sk-line"></span>
        <span class="sk-line sk-short"></span>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="results.length > 0" class="results-section">
      <div
        v-for="(item, index) in results"
        :key="item.platform"
        class="card result-card"
        :style="{ '--i': index }"
      >
        <div class="result-header">
          <span class="platform-badge">{{ platformLabel(item.platform) }}</span>
          <div class="result-actions">
            <button
              type="button"
              class="btn btn-primary send-btn"
              :disabled="sendingPlatform !== ''"
              :aria-label="`把${platformLabel(item.platform)}文案本地切页后送入创作中心，不消耗 AI 额度`"
              title="按段落本地切成大纲页，不调用 AI"
              @click="sendToCreation(item)"
            >
              送入创作（不耗额度）
            </button>
            <span class="ai-send-group">
              <button
                type="button"
                class="btn btn-secondary send-btn"
                :disabled="sendingPlatform !== ''"
                :aria-label="`让 AI 重新提炼${platformLabel(item.platform)}文案为大纲后送入创作中心（将调用 AI）`"
                title="让 AI 重新提炼分页，将调用 AI 并消耗额度"
                @click="sendToCreationViaAI(item)"
              >
                <span v-if="sendingPlatform === item.platform" class="spinner-sm"></span>
                {{ sendingPlatform === item.platform ? '正在转成大纲…' : 'AI 重排后送入' }}
              </button>
              <span class="ai-cost-hint">将调用 AI</span>
            </span>
            <button
              type="button"
              class="btn btn-secondary copy-btn"
              :class="{ copied: copiedPlatform === item.platform }"
              :aria-label="`复制${platformLabel(item.platform)}文案`"
              @click="copyResult(item)"
            >
              {{ copiedPlatform === item.platform ? '已复制 ✓' : '一键复制' }}
            </button>
          </div>
        </div>
        <h3 class="result-title">{{ item.title }}</h3>
        <p class="result-content">{{ item.content }}</p>
        <div v-if="item.tags.length > 0" class="result-tags">
          <span v-for="tag in item.tags" :key="tag" class="tag result-tag">#{{ tag }}</span>
        </div>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.85 2.83 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5Z"/><path d="m15 5 4 4"/></svg>
      </div>
      <p class="empty-title">一稿多发，从这里开始</p>
      <p class="empty-desc">粘贴一段文案、勾选目标平台，点击「开始改写」，各平台版本会在这里逐一展示</p>
      <p class="empty-example">试试：把一篇小红书笔记，改写成抖音口播稿 + 公众号推文</p>
    </div>

    <ErrorCard
      v-if="error"
      class="rewrite-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleRewrite"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { rewriteCopy, type RewritePlatform, type RewriteResult } from '../api/rewrite'
import { getBrandList, type BrandKit } from '../api/brand'
import { linkToOutline } from '../api/link'
import type { Page } from '../api/types'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  REWRITE_ARCHIVE_KEY,
  addToolArchiveEntry,
  buildInputSummary,
  createToolArchiveEntry,
  formatArchiveTime,
  isValidRewritePayload,
  loadToolArchive,
  saveToolArchive,
  type RewriteArchivePayload,
  type ToolArchiveEntry,
} from '../utils/toolArchive'
import ErrorCard from '../components/common/ErrorCard.vue'

interface PlatformOption {
  code: RewritePlatform
  label: string
}

const platforms: PlatformOption[] = [
  { code: 'xiaohongshu', label: '小红书' },
  { code: 'douyin', label: '抖音口播' },
  { code: 'wechat', label: '公众号' },
  { code: 'bilibili', label: 'B站' },
  { code: 'weibo', label: '微博' }
]

const router = useRouter()
const store = useGeneratorStore()

const content = ref('')
const sourcePlatform = ref<RewritePlatform | ''>('')
const targetPlatforms = ref<RewritePlatform[]>([])
const results = ref<RewriteResult[]>([])
const loading = ref(false)
const error = ref<AppError | null>(null)
const copiedPlatform = ref('')
// 正在流转到创作中心的平台代号，'' 表示空闲（同一时间只允许一个流转请求）
const sendingPlatform = ref('')

// 最近记录（本地存档，最近 10 次改写结果）
const archive = ref<Array<ToolArchiveEntry<RewriteArchivePayload>>>(
  loadToolArchive(REWRITE_ARCHIVE_KEY, isValidRewritePayload)
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

function toggleTarget(code: RewritePlatform) {
  const index = targetPlatforms.value.indexOf(code)
  if (index === -1) {
    targetPlatforms.value.push(code)
  } else {
    targetPlatforms.value.splice(index, 1)
  }
}

function platformLabel(code: string): string {
  return platforms.find(p => p.code === code)?.label || code
}

async function handleRewrite() {
  if (loading.value || !content.value.trim() || targetPlatforms.value.length === 0) return

  loading.value = true
  error.value = null
  // 重新改写时保留旧结果展示，新结果返回后再整体替换（这些都是花了额度的产物）

  try {
    const result = await rewriteCopy(
      content.value.trim(),
      sourcePlatform.value,
      targetPlatforms.value,
      selectedBrandId.value || undefined
    )

    if (result.success && result.results) {
      results.value = result.results
      recordArchive(result.results)
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '文案改写失败', '文案改写失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '文案改写失败')
  } finally {
    loading.value = false
  }
}

// ==================== 最近记录（本地存档） ====================

function recordArchive(resultList: RewriteResult[]) {
  if (resultList.length === 0) return
  const entry = createToolArchiveEntry<RewriteArchivePayload>({
    input: content.value.trim(),
    payload: {
      content: content.value.trim(),
      sourcePlatform: sourcePlatform.value,
      targetPlatforms: [...targetPlatforms.value],
      results: resultList,
    },
  })
  archive.value = addToolArchiveEntry(archive.value, entry)
  saveToolArchive(REWRITE_ARCHIVE_KEY, archive.value)
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: ToolArchiveEntry<RewriteArchivePayload>) {
  if (loading.value) return
  content.value = entry.payload.content
  const validCodes = platforms.map(p => p.code) as string[]
  sourcePlatform.value = validCodes.includes(entry.payload.sourcePlatform)
    ? entry.payload.sourcePlatform
    : ''
  targetPlatforms.value = entry.payload.targetPlatforms.filter(code =>
    validCodes.includes(code)
  )
  results.value = entry.payload.results
  error.value = null
}

// ==================== 送入创作中心 ====================

// 本地切页的单页字数区间：短于下限的相邻段落会被合并，超过上限的段落按句拆分
const PAGE_MIN_CHARS = 50
const PAGE_MAX_CHARS = 120

/**
 * 把正文本地切成 50-120 字的内容页（纯前端，不调用 AI）：
 * 1. 按换行拆段；2. 超长段按句尾标点再拆（无标点的整句硬切）；
 * 3. 相邻短段贪心合并，凑到下限即成页
 */
function splitBodyToChunks(body: string): string[] {
  const paragraphs = body.split(/\n+/).map(s => s.trim()).filter(Boolean)

  const units: string[] = []
  for (const para of paragraphs) {
    if (para.length <= PAGE_MAX_CHARS) {
      units.push(para)
      continue
    }
    let buf = ''
    for (const sentence of para.split(/(?<=[。！？!?；;…])/).map(s => s.trim()).filter(Boolean)) {
      if (sentence.length > PAGE_MAX_CHARS) {
        // 整句无标点且超长：按上限硬切，避免单页爆版
        if (buf) { units.push(buf); buf = '' }
        for (let i = 0; i < sentence.length; i += PAGE_MAX_CHARS) {
          units.push(sentence.slice(i, i + PAGE_MAX_CHARS))
        }
      } else if (buf && buf.length + sentence.length > PAGE_MAX_CHARS) {
        units.push(buf)
        buf = sentence
      } else {
        buf = buf ? buf + sentence : sentence
      }
    }
    if (buf) units.push(buf)
  }

  const chunks: string[] = []
  let current = ''
  for (const unit of units) {
    if (!current) {
      current = unit
    } else if (current.length < PAGE_MIN_CHARS && current.length + 1 + unit.length <= PAGE_MAX_CHARS) {
      current = `${current}\n${unit}`
    } else {
      chunks.push(current)
      current = unit
    }
  }
  if (current) chunks.push(current)
  return chunks
}

/**
 * 送入创作中心（默认路径，不耗额度）：
 * 改写结果已经是分好段的成稿，前端直接本地构造大纲——
 * 标题作封面页、正文切成 50-120 字的内容页、标签收尾作总结页，
 * 组装与后端一致的 raw（<page> 分隔）后写入 store 并跳转大纲页
 */
function sendToCreation(item: RewriteResult) {
  if (sendingPlatform.value !== '') return

  const title = item.title.trim() || buildInputSummary(item.content, 30)
  const pages: Page[] = [{ index: 0, type: 'cover', content: title }]
  for (const chunk of splitBodyToChunks(item.content)) {
    pages.push({ index: pages.length, type: 'content', content: chunk })
  }
  if (item.tags.length > 0) {
    pages.push({
      index: pages.length,
      type: 'summary',
      content: item.tags.map(t => `#${t}`).join(' '),
    })
  }
  const raw = pages.map(page => page.content).join('\n\n<page>\n\n')

  store.setTopic(title)
  store.setOutline(raw, pages)
  // 清空旧的历史记录 ID，让大纲页为本次内容创建新的历史记录
  store.setRecordId(null)

  router.push('/outline')
}

/**
 * AI 重排后送入（次级路径，将调用 AI）：
 * title + content + tags 拼成长文本 → 调链接工具的长文转大纲能力 →
 * 照 ToolLinkView.sendToCreation 的模式写入 generator store 并跳转大纲页
 */
async function sendToCreationViaAI(item: RewriteResult) {
  if (sendingPlatform.value !== '') return

  const rawParts = [`标题：${item.title}`, item.content]
  if (item.tags.length > 0) {
    rawParts.push(`标签：${item.tags.join(' ')}`)
  }
  const rawText = rawParts.filter(Boolean).join('\n\n')

  sendingPlatform.value = item.platform
  error.value = null

  try {
    const result = await linkToOutline({ text: rawText })

    if (result.success && result.pages && result.pages.length > 0) {
      const pages = result.pages
      // 保证 index 连续
      pages.forEach((page, i) => {
        page.index = i
      })
      const raw = pages.map(page => page.content).join('\n\n<page>\n\n')

      store.setTopic(result.topic?.trim() || item.title)
      store.setOutline(raw, pages)
      // 清空旧的历史记录 ID，让大纲页为本次内容创建新的历史记录
      store.setRecordId(null)

      router.push('/outline')
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '送入创作中心失败',
        '送入创作中心失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '送入创作中心失败')
  } finally {
    sendingPlatform.value = ''
  }
}

let copyTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})

async function copyResult(item: RewriteResult) {
  const parts = [item.title, item.content]
  if (item.tags.length > 0) {
    parts.push(item.tags.map(t => `#${t}`).join(' '))
  }
  const text = parts.filter(Boolean).join('\n\n')
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
  copiedPlatform.value = item.platform
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    copiedPlatform.value = ''
  }, 1500)
}
</script>

<style scoped>
.rewrite-container {
  max-width: 860px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.rewrite-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

.rewrite-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.rewrite-textarea {
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

.rewrite-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.rewrite-textarea::placeholder {
  color: var(--text-placeholder);
}

.field-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.source-select {
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.source-select:focus {
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

.platform-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.platform-chip {
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

.platform-chip:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.platform-chip:active {
  transform: translateY(0);
  box-shadow: none;
}

.platform-chip.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
  box-shadow: var(--shadow-focus);
}

.platform-chip.active:hover {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
}

.submit-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.rewrite-btn {
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

.result-card {
  animation: fadeIn 0.4s var(--ease-out) both;
  animation-delay: calc(var(--i, 0) * 70ms);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.platform-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.result-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.send-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 18px;
  font-size: 14px;
}

/* AI 重排按钮 + 消耗提示：提示紧贴按钮，提醒该路径会调用 AI */
.ai-send-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ai-cost-hint {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
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

.result-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-3);
  line-height: 1.5;
}

.result-content {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: var(--space-3);
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.result-tag {
  padding: 6px 14px;
  font-size: var(--font-size-caption);
  cursor: default;
}

.result-tag:hover {
  transform: none;
  box-shadow: none;
  background: var(--gray-2);
  border-color: transparent;
  color: var(--text-sub);
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

.rewrite-error {
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
  .result-card,
  .empty-state,
  .rewrite-error {
    animation: none;
  }

  .sk-line {
    animation: none;
    background: var(--gray-2);
  }

  .platform-chip,
  .platform-chip:hover {
    transform: none;
  }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .rewrite-container {
    padding-top: 12px;
  }

  .card {
    padding: var(--space-5);
  }

  .field-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .source-select {
    width: 100%;
  }

  .rewrite-btn {
    width: 100%;
  }

  .result-header {
    flex-wrap: wrap;
  }
}
</style>
