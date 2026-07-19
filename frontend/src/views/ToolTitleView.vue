<template>
  <div class="container title-container">
    <!-- 头部 -->
    <div class="tool-header">
      <div class="brand-pill">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
        爆款标题工坊
      </div>
      <h1 class="page-title">一句话，生成 10+ 个爆款标题</h1>
      <p class="page-subtitle">输入主题或文案草稿，AI 按平台调性与风格倾向批量产出候选标题，标注爆款要素并打分</p>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <label class="field-label" for="title-topic">主题 / 文案草稿</label>
      <textarea
        id="title-topic"
        v-model="topic"
        class="topic-input"
        rows="4"
        maxlength="1000"
        placeholder="例如：打工人早八如何 10 分钟搞定营养早餐，附 5 个快手食谱……"
        @keydown.enter.meta.prevent="handleGenerate"
        @keydown.enter.ctrl.prevent="handleGenerate"
      ></textarea>

      <div class="field-group">
        <span class="field-label">目标平台</span>
        <div class="option-row">
          <button
            v-for="p in PLATFORMS"
            :key="p"
            type="button"
            class="option-chip"
            :class="{ active: platform === p }"
            @click="platform = p"
          >{{ p }}</button>
        </div>
      </div>

      <div class="field-group">
        <span class="field-label">风格倾向</span>
        <div class="option-row">
          <button
            v-for="s in STYLES"
            :key="s.value"
            type="button"
            class="option-chip"
            :class="{ active: style === s.value }"
            @click="style = s.value"
          >
            {{ s.label }}
          </button>
        </div>
        <p class="style-hint">{{ activeStyleHint }}</p>
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
        :disabled="loading || !topic.trim()"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '正在生成候选标题…' : '生成爆款标题' }}
      </button>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && titles.length === 0" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <span class="sk-circle"></span>
        <span class="sk-lines">
          <span class="sk-line sk-wide"></span>
          <span class="sk-line sk-narrow"></span>
        </span>
        <span class="sk-ring"></span>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="titles.length > 0" class="result-section">
      <div class="result-toolbar">
        <span class="result-count">共 {{ titles.length }} 个候选</span>
        <div class="toolbar-actions">
          <button
            type="button"
            class="sort-btn"
            :class="{ active: sortByScore }"
            @click="sortByScore = !sortByScore"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/><path d="M15 8h6"/><path d="M15 12h4"/><path d="M15 16h2"/></svg>
            {{ sortByScore ? '按评分排序中' : '按评分排序' }}
          </button>
        </div>
      </div>

      <transition-group name="card" tag="div" class="title-list">
        <div
          v-for="(item, i) in displayTitles"
          :key="item.text"
          class="title-card"
          :style="{ '--i': i }"
        >
          <div class="card-rank" :class="rankClass(i)">{{ i + 1 }}</div>
          <div class="card-body">
            <p class="card-text">{{ item.text }}</p>
            <div class="card-meta">
              <span
                v-for="el in item.elements"
                :key="el"
                class="element-tag"
              >{{ el }}</span>
            </div>
          </div>
          <div class="card-side">
            <div class="score-ring" :class="scoreClass(item.score)">
              <span class="score-num">{{ item.score }}</span>
              <span class="score-label">吸引力</span>
            </div>
            <button
              type="button"
              class="copy-btn"
              :class="{ copied: copiedText === item.text }"
              :aria-label="`复制标题：${item.text}`"
              @click="handleCopy(item.text)"
            >
              {{ copiedText === item.text ? '已复制' : '复制' }}
            </button>
          </div>
        </div>
      </transition-group>
    </div>

    <!-- 空态 -->
    <div v-else-if="!loading && hasGenerated" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/></svg>
      </div>
      <p class="empty-title">没有生成有效的标题</p>
      <p class="empty-desc">换个说法再试试吧</p>
    </div>

    <!-- 初始引导态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
      </div>
      <p class="empty-title">候选标题会在这里展示</p>
      <p class="empty-desc">输入主题、选好平台和风格，点击「生成爆款标题」，每条标题都会标注爆款要素与吸引力评分</p>
      <p class="empty-example">试试：打工人早八如何 10 分钟搞定营养早餐</p>
    </div>

    <ErrorCard
      v-if="error"
      class="title-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { generateTitles, type TitleCandidate } from '../api/title'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const PLATFORMS = ['小红书', '抖音', '视频号', 'B站', '公众号'] as const

const STYLES = [
  { value: '综合', label: '综合推荐', hint: '不限定风格，AI 自由发挥，覆盖多种打法' },
  { value: '悬念型', label: '悬念型', hint: '留白吊胃口，让人忍不住点进来一探究竟' },
  { value: '数字型', label: '数字型', hint: '用具体数字量化价值，信息密度高、可信感强' },
  { value: '痛点型', label: '痛点型', hint: '直击用户痛处，引发"这说的就是我"的共鸣' },
  { value: '反差型', label: '反差型', hint: '制造预期违背与强烈对比，冲击力拉满' },
  { value: '福利型', label: '福利型', hint: '强调干货、免费、限时等利益点，给足点击理由' },
  { value: '情绪型', label: '情绪型', hint: '调动情绪共鸣，靠感染力带动转发与讨论' }
] as const

const topic = ref('')
const platform = ref<string>(PLATFORMS[0])
const style = ref<string>(STYLES[0].value)
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const titles = ref<TitleCandidate[]>([])
const sortByScore = ref(true)
const copiedText = ref('')

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

let copyTimer: ReturnType<typeof setTimeout> | undefined

const activeStyleHint = computed(() =>
  STYLES.find(s => s.value === style.value)?.hint ?? ''
)

const displayTitles = computed(() => {
  if (!sortByScore.value) return titles.value
  return [...titles.value].sort((a, b) => b.score - a.score)
})

function rankClass(index: number): string {
  if (!sortByScore.value) return ''
  if (index === 0) return 'rank-gold'
  if (index === 1) return 'rank-silver'
  if (index === 2) return 'rank-bronze'
  return ''
}

function scoreClass(score: number): string {
  if (score >= 85) return 'score-high'
  if (score >= 70) return 'score-mid'
  return 'score-low'
}

async function handleGenerate() {
  if (!topic.value.trim() || loading.value) return

  loading.value = true
  error.value = null

  try {
    const result = await generateTitles({
      topic: topic.value.trim(),
      platform: platform.value,
      style: style.value,
      brandId: selectedBrandId.value || undefined
    })

    if (result.success && result.titles) {
      titles.value = result.titles
      hasGenerated.value = true
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成标题失败',
        '生成标题失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成标题失败')
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
.title-container {
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

.topic-input {
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
  min-height: 96px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    background var(--transition-fast);
  background: var(--gray-1);
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: var(--shadow-focus);
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

.style-hint {
  margin: 10px 2px 0;
  font-size: 13px;
  color: var(--text-sub);
}

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

/* 生成按钮基于全局 .btn btn-primary，仅覆盖布局 */
.generate-btn {
  margin-top: 22px;
  width: 100%;
}

/* ── 加载骨架（纯 CSS shimmer） ───── */
.skeleton-section {
  margin-top: 28px;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton-card {
  display: flex;
  align-items: center;
  gap: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  box-shadow: var(--shadow-xs);
}

.sk-line,
.sk-circle,
.sk-ring {
  display: block;
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-circle {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
}

.sk-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sk-line {
  height: 14px;
  border-radius: var(--radius-full);
}

.sk-wide { width: 72%; }
.sk-narrow { width: 40%; height: 12px; }

.sk-ring {
  flex-shrink: 0;
  width: 54px;
  height: 54px;
  border-radius: 50%;
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
  margin-bottom: 14px;
  padding: 0 4px;
}

.result-count {
  font-size: 14px;
  color: var(--text-sub);
}

.sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: var(--font-size-caption);
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.sort-btn:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.sort-btn.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.title-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.title-card {
  display: flex;
  align-items: stretch;
  gap: 14px;
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

.title-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.card-rank {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: var(--font-size-caption);
  font-weight: 700;
  background: var(--gray-2);
  color: var(--text-sub);
  align-self: center;
}

.card-rank.rank-gold {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.card-rank.rank-silver {
  background: var(--gray-2);
  color: var(--gray-6);
}

.card-rank.rank-bronze {
  background: var(--gray-3);
  color: var(--gray-7);
}

.card-body {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.card-text {
  margin: 0;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.55;
  word-break: break-word;
}

.card-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.element-tag {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 500;
}

.card-side {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.score-ring {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  border: 3px solid;
}

.score-ring.score-high {
  border-color: var(--primary);
  color: var(--primary);
}

.score-ring.score-mid {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.score-ring.score-low {
  border-color: var(--border-hover);
  color: var(--text-sub);
}

.score-num {
  font-size: 17px;
  font-weight: 700;
  line-height: 1;
}

.score-label {
  font-size: 10px;
  opacity: 0.75;
  margin-top: 2px;
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

/* 排序过渡动画 */
.card-move {
  transition: transform 0.35s var(--ease-out);
}

/* ── 空态 / 错误 ────────────────── */
.empty-state {
  margin-top: 32px;
  text-align: center;
  padding: var(--space-6) 16px;
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
  font-size: 13.5px;
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

.title-error {
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
  .title-container {
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

  .title-card {
    flex-wrap: wrap;
    padding: 14px;
    gap: 10px;
  }

  .card-body {
    flex-basis: calc(100% - 38px);
  }

  .card-side {
    flex-direction: row;
    width: 100%;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px dashed var(--border-color);
  }

  .score-ring {
    width: 46px;
    height: 46px;
    border-width: 2.5px;
  }

  .score-num {
    font-size: 15px;
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
  .title-card,
  .empty-state,
  .title-error {
    animation: none;
  }

  .sk-line,
  .sk-circle,
  .sk-ring {
    animation: none;
    background: var(--gray-2);
  }

  .card-move {
    transition: none;
  }

  .option-chip,
  .option-chip:hover,
  .copy-btn,
  .copy-btn:hover,
  .title-card:hover {
    transform: none;
  }
}
</style>
