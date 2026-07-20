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

      <div class="field-block">
        <label class="field-label" for="brand-select">
          品牌人设（可选）
          <span class="field-hint">仿写草稿会按你的人设语气生成，避免"写成别人"</span>
        </label>
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

    <!-- 我的套路库（长期沉淀，与 20 条滚动的拆解历史相互独立） -->
    <div v-if="patterns.length > 0" class="card history-card">
      <button type="button" class="history-toggle" @click="showPatterns = !showPatterns">
        <span class="history-title">我的套路库（{{ patterns.length }}）</span>
        <svg
          class="history-chevron"
          :class="{ open: showPatterns }"
          width="16" height="16" viewBox="0 0 24 24" fill="none"
          stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
          aria-hidden="true"
        ><polyline points="6 9 12 15 18 9"/></svg>
      </button>
      <ul v-if="showPatterns" class="history-list pattern-list">
        <li v-for="pattern in patterns" :key="pattern.id" class="pattern-item">
          <div class="pattern-row">
            <button
              type="button"
              class="pattern-name-btn"
              :title="expandedPatternId === pattern.id ? '收起模板全文' : '查看模板全文'"
              @click="togglePatternExpand(pattern.id)"
            >
              <span class="history-summary">{{ pattern.name }}</span>
              <span class="history-time">{{ formatTime(pattern.created_at) }}</span>
            </button>
            <div class="pattern-actions">
              <button
                type="button"
                class="pattern-action-btn"
                :disabled="loading || !!sending"
                title="以这个套路结构创作我的主题"
                @click="openTopicDialogForPattern(pattern)"
              >
                以此结构创作
              </button>
              <button
                type="button"
                class="pattern-action-btn danger"
                :title="pendingDeletePatternId === pattern.id ? '再点一次确认删除' : '从套路库删除'"
                @click="requestDeletePattern(pattern.id)"
              >
                {{ pendingDeletePatternId === pattern.id ? '确认删除？' : '删除' }}
              </button>
            </div>
          </div>
          <div v-if="expandedPatternId === pattern.id" class="pattern-detail">
            <p class="pattern-template-text">{{ pattern.template }}</p>
            <p v-if="pattern.source_title" class="pattern-source">来源：{{ pattern.source_title }}</p>
          </div>
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
            <div class="template-actions">
              <button
                type="button"
                class="btn btn-secondary copy-btn"
                :class="{ copied: patternSavedFlash }"
                title="把这个套路长期存进「我的套路库」，随时以此结构创作"
                @click="openPatternDialog"
              >
                {{ patternSavedFlash ? '已存入 ✓' : '存入套路库' }}
              </button>
              <button
                type="button"
                class="btn btn-secondary copy-btn"
                :class="{ copied: copiedKey === 'template' }"
                @click="copyTemplate"
              >
                {{ copiedKey === 'template' ? '已复制 ✓' : '复制模板' }}
              </button>
            </div>
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
            title="按段落本地切成大纲页，不调用 AI"
            @click="sendDraftToCreation"
          >
            用仿写草稿创作（不耗额度）
          </button>
          <span v-if="draft" class="ai-send-group">
            <button
              type="button"
              class="btn btn-secondary creation-btn"
              :disabled="loading || !!sending"
              title="让 AI 重新提炼草稿分页，将调用 AI 并消耗额度"
              @click="sendDraftToCreationViaAI"
            >
              <span v-if="sending === 'draft'" class="spinner-sm" aria-hidden="true"></span>
              {{ sending === 'draft' ? '正在生成大纲…' : 'AI 重排后送入' }}
            </button>
            <span class="ai-cost-hint">将调用 AI</span>
          </span>
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
        <p class="creation-tip">「用仿写草稿创作」在本地切页送入创作中心、不消耗额度；「AI 重排」与「以此结构创作」会调用 AI 生成大纲</p>
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

    <!-- 「存入套路库」命名弹窗 -->
    <div v-if="patternDialogVisible" class="topic-dialog-mask" @click.self="closePatternDialog">
      <div class="card topic-dialog" role="dialog" aria-modal="true" aria-labelledby="pattern-dialog-title">
        <h3 id="pattern-dialog-title" class="topic-dialog-title">存入套路库</h3>
        <p class="topic-dialog-desc">给这个套路起个好记的名字（默认取对标标题），之后可在「我的套路库」随时以此结构创作</p>
        <input
          ref="patternNameInputEl"
          v-model="patternNameInput"
          class="topic-input"
          type="text"
          placeholder="例如：痛点清单体 / 反差故事体"
          @keyup.enter="confirmSavePattern"
        />
        <div class="topic-dialog-actions">
          <button type="button" class="btn btn-secondary" @click="closePatternDialog">取消</button>
          <button type="button" class="btn btn-primary" @click="confirmSavePattern">存入</button>
        </div>
      </div>
    </div>

    <!-- 「以此结构创作」主题输入弹窗 -->
    <div v-if="topicDialogVisible" class="topic-dialog-mask" @click.self="closeTopicDialog">
      <div class="card topic-dialog" role="dialog" aria-modal="true" aria-labelledby="topic-dialog-title">
        <h3 id="topic-dialog-title" class="topic-dialog-title">以此结构创作我的主题</h3>
        <p class="topic-dialog-desc">AI 会严格按选中的爆款结构模板，围绕你的主题生成图文大纲（将调用 AI）</p>
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
import { computed, nextTick, onMounted, onUnmounted, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { analyzeBenchmark, type BenchmarkAnalysis } from '../api/benchmark'
import { getBrandList, type BrandKit } from '../api/brand'
import { linkToOutline } from '../api/link'
import type { Page } from '../api/types'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  addEntry,
  buildSummary,
  createEntry,
  loadHistory,
  saveHistory,
  type BenchmarkHistoryEntry,
} from '../utils/benchmarkHistory'
import {
  addPatternEntry,
  createPatternEntry,
  loadPatternLibrary,
  removePatternEntry,
  savePatternLibrary,
  type PatternEntry,
} from '../utils/patternLibrary'
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

// 「以此结构创作」主题弹窗；templateForCreation 是本次确认后要套用的结构模板
// （既可能来自刚拆解出的结果，也可能来自套路库里存的某条套路）
const topicDialogVisible = ref(false)
const topicDialogInput = ref('')
const topicDialogInputEl = ref<HTMLInputElement | null>(null)
const templateForCreation = ref('')

// 本地历史
const history = ref<BenchmarkHistoryEntry[]>(loadHistory())
const showHistory = ref(false)

// 当前拆解结果的来源标题/摘要（存套路时的默认命名与来源字段）
const analysisSource = ref('')

// ==================== 我的套路库状态 ====================
const patterns = ref<PatternEntry[]>(loadPatternLibrary())
const showPatterns = ref(false)
// 展开查看模板全文的套路 ID
const expandedPatternId = ref('')
// 两次点击确认删除：第一次点击记录 ID，2.5 秒内再点才真正删除
const pendingDeletePatternId = ref('')
let deletePatternTimer: ReturnType<typeof setTimeout> | undefined

// 「存入套路库」命名弹窗
const patternDialogVisible = ref(false)
const patternNameInput = ref('')
const patternNameInputEl = ref<HTMLInputElement | null>(null)
// 存入成功后的短暂反馈（按钮变「已存入 ✓」）
const patternSavedFlash = ref(false)
let patternSavedTimer: ReturnType<typeof setTimeout> | undefined

// 品牌人设选择：'' 表示不使用，默认选中当前启用档案
const brands = ref<BrandKit[]>([])
const activeBrandId = ref<string | null>(null)
const selectedBrandId = ref('')
const brandsLoaded = ref(false)

let copyTimer: ReturnType<typeof setTimeout> | undefined

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

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  if (deletePatternTimer !== undefined) clearTimeout(deletePatternTimer)
  if (patternSavedTimer !== undefined) clearTimeout(patternSavedTimer)
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
      brandId: selectedBrandId.value || undefined,
    })

    if (result.success && result.analysis) {
      analysis.value = result.analysis
      draft.value = result.draft || ''
      // 记录来源摘要，作为「存入套路库」的默认命名与来源字段
      analysisSource.value = buildSummary(input)
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
  analysisSource.value = entry.summary
  if (entry.myTopic) myTopic.value = entry.myTopic
  error.value = null
}

function formatTime(timestamp: number): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ==================== 一键送创作 ====================

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

/** 纯 #标签 行（如「#穿搭 #通勤」），作为收尾时切成总结页 */
function isTagLine(text: string): boolean {
  return /^(#[^\s#]+\s*)+$/.test(text.trim())
}

/**
 * 「用仿写草稿创作」（默认路径，不耗额度）：
 * 草稿已经是分好段的成稿，前端直接本地构造大纲——
 * 首段较短时视为草稿自带标题作封面页（否则用「我的主题」作封面），
 * 正文切成 50-120 字的内容页，结尾的纯标签行作总结页收尾
 */
function sendDraftToCreation() {
  if (!draft.value || loading.value || sending.value) return

  const paragraphs = draft.value.split(/\n+/).map(s => s.trim()).filter(Boolean)
  if (paragraphs.length === 0) return

  const topic = myTopic.value.trim()
  // 封面文案：首段不超过 40 字时视为草稿自带标题；否则退回主题/默认名
  let coverText = topic || '对标仿创'
  let bodyParagraphs = paragraphs
  if (paragraphs[0].length <= 40 && paragraphs.length > 1) {
    coverText = paragraphs[0]
    bodyParagraphs = paragraphs.slice(1)
  }

  // 结尾的纯标签行单独收出来作总结页
  let summaryText = ''
  if (bodyParagraphs.length > 1 && isTagLine(bodyParagraphs[bodyParagraphs.length - 1])) {
    summaryText = bodyParagraphs[bodyParagraphs.length - 1]
    bodyParagraphs = bodyParagraphs.slice(0, -1)
  }

  const pages: Page[] = [{ index: 0, type: 'cover', content: coverText }]
  for (const chunk of splitBodyToChunks(bodyParagraphs.join('\n'))) {
    pages.push({ index: pages.length, type: 'content', content: chunk })
  }
  if (summaryText) {
    pages.push({ index: pages.length, type: 'summary', content: summaryText })
  }
  const raw = pages.map(page => page.content).join('\n\n<page>\n\n')

  store.setTopic(topic || coverText)
  store.setOutline(raw, pages)
  // 清空旧的历史记录 ID，让大纲页为本次内容创建新的历史记录
  store.setRecordId(null)

  router.push('/outline')
}

/**
 * 长文本 → 大纲 → 写入 store → 跳转创作中心（照抄 ToolLinkView.sendToCreation 模式，将调用 AI）
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

/** 「AI 重排后送入」（次级路径）：把 draft 交给 AI 重新提炼成大纲后进入创作流程 */
function sendDraftToCreationViaAI() {
  if (!draft.value) return
  sendTextToCreation(draft.value, myTopic.value.trim(), 'draft')
}

/** 以刚拆解出的结构模板打开主题弹窗 */
function openTopicDialog() {
  if (loading.value || sending.value) return
  if (!analysis.value?.reusable_template) return
  templateForCreation.value = analysis.value.reusable_template
  topicDialogInput.value = myTopic.value.trim()
  topicDialogVisible.value = true
  nextTick(() => topicDialogInputEl.value?.focus())
}

/** 以套路库里存的某条套路打开主题弹窗（复用同一个「以此结构创作」路径） */
function openTopicDialogForPattern(pattern: PatternEntry) {
  if (loading.value || sending.value) return
  templateForCreation.value = pattern.template
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
  if (!topic || !templateForCreation.value) return

  topicDialogVisible.value = false
  const text = [
    '请严格按以下爆款结构模板创作：',
    `主题：${topic}`,
    `结构模板：\n${templateForCreation.value}`,
  ].join('\n\n')

  sendTextToCreation(text, topic, 'template')
}

// ==================== 我的套路库 ====================

/** 打开「存入套路库」命名弹窗，名称默认取对标标题/摘要 */
function openPatternDialog() {
  if (!analysis.value?.reusable_template) return
  patternNameInput.value = analysisSource.value
  patternDialogVisible.value = true
  nextTick(() => {
    patternNameInputEl.value?.focus()
    patternNameInputEl.value?.select()
  })
}

function closePatternDialog() {
  patternDialogVisible.value = false
}

/** 确认存入：写入套路库并给出短暂反馈 */
function confirmSavePattern() {
  if (!analysis.value?.reusable_template) return

  const entry = createPatternEntry({
    name: patternNameInput.value,
    template: analysis.value.reusable_template,
    sourceTitle: analysisSource.value,
  })
  patterns.value = addPatternEntry(patterns.value, entry)
  savePatternLibrary(patterns.value)

  patternDialogVisible.value = false
  patternSavedFlash.value = true
  if (patternSavedTimer !== undefined) clearTimeout(patternSavedTimer)
  patternSavedTimer = setTimeout(() => { patternSavedFlash.value = false }, 1500)
}

/** 展开/收起某条套路的模板全文 */
function togglePatternExpand(id: string) {
  expandedPatternId.value = expandedPatternId.value === id ? '' : id
}

/** 两段式删除：第一次点击进入确认态，2.5 秒内再点才删除 */
function requestDeletePattern(id: string) {
  if (pendingDeletePatternId.value !== id) {
    pendingDeletePatternId.value = id
    if (deletePatternTimer !== undefined) clearTimeout(deletePatternTimer)
    deletePatternTimer = setTimeout(() => { pendingDeletePatternId.value = '' }, 2500)
    return
  }
  if (deletePatternTimer !== undefined) clearTimeout(deletePatternTimer)
  pendingDeletePatternId.value = ''
  patterns.value = removePatternEntry(patterns.value, id)
  savePatternLibrary(patterns.value)
  if (expandedPatternId.value === id) expandedPatternId.value = ''
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

.brand-select {
  align-self: flex-start;
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

/* 我的套路库（在历史区样式基础上加操作按钮与详情展开） */
.pattern-item {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-1);
}

.pattern-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  padding: 6px 8px 6px 0;
}

.pattern-name-btn {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  padding: 6px 14px;
  border: none;
  background: transparent;
  cursor: pointer;
  text-align: left;
}

.pattern-name-btn:hover .history-summary {
  color: var(--primary);
}

.pattern-actions {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  gap: var(--space-1);
}

.pattern-action-btn {
  padding: 5px 10px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xs);
  background: var(--bg-card);
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  cursor: pointer;
  white-space: nowrap;
  transition: color var(--transition-fast), border-color var(--transition-fast),
    background var(--transition-fast);
}

.pattern-action-btn:hover:not(:disabled) {
  color: var(--primary);
  border-color: var(--primary);
}

.pattern-action-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.pattern-action-btn.danger:hover {
  color: var(--color-danger);
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.pattern-detail {
  padding: 0 14px 12px;
}

.pattern-template-text {
  margin: 0;
  padding: 10px 12px;
  font-size: 13.5px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xs);
}

.pattern-source {
  margin: var(--space-2) 0 0;
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
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

.template-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.template-text {
  font-weight: 500;
}

/* 一键送创作 */
.creation-bar {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-5);
  flex-wrap: wrap;
}

.creation-btn {
  min-width: 200px;
}

/* AI 重排按钮 + 消耗提示：提示紧贴按钮，提醒该路径会调用 AI */
.ai-send-group {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.ai-send-group .creation-btn {
  min-width: 0;
}

.ai-cost-hint {
  font-size: 12px;
  color: var(--text-secondary);
  white-space: nowrap;
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

  .brand-select {
    align-self: stretch;
    width: 100%;
  }

  .result-header,
  .template-header {
    flex-wrap: wrap;
  }

  .pattern-row {
    flex-wrap: wrap;
    padding: 6px 8px;
  }

  .pattern-actions {
    width: 100%;
    justify-content: flex-end;
  }
}
</style>
