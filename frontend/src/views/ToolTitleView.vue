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
      没有生成有效的标题，换个说法再试试吧
    </div>

    <!-- 初始引导态 -->
    <div v-else-if="!loading" class="empty-state">
      输入主题、选好平台和风格，点击「生成爆款标题」，候选标题会带爆款要素与评分在这里展示
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

/* ── 输入卡片（基于全局 .card，仅覆盖内边距） ───────────────────── */
.input-card {
  padding: 24px;
  margin-bottom: 0;
  animation: fadeIn 0.5s ease-out;
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
  border-radius: 12px;
  padding: 12px 14px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  line-height: 1.6;
  resize: vertical;
  min-height: 96px;
  transition: border-color 0.2s;
  background: var(--bg-body);
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
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
  border-radius: 12px;
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color 0.2s;
}

.brand-select:focus {
  outline: none;
  border-color: var(--primary);
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

.sort-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 7px 14px;
  border-radius: 100px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13px;
  font-weight: 500;
  cursor: pointer;
  transition: all 0.2s;
}

.sort-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
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
  border-radius: 16px;
  padding: 16px 18px;
  transition: box-shadow 0.2s, border-color 0.2s, transform 0.3s;
}

.title-card:hover {
  border-color: var(--border-hover);
  box-shadow: 0 6px 20px rgba(0, 0, 0, 0.06);
}

.card-rank {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 13px;
  font-weight: 700;
  background: var(--bg-body);
  color: var(--text-sub);
  align-self: center;
}

.card-rank.rank-gold {
  background: #FFF4D6;
  color: #B8860B;
}

.card-rank.rank-silver {
  background: #F0F2F5;
  color: #7A8699;
}

.card-rank.rank-bronze {
  background: #F9E8DC;
  color: #A6672E;
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
  border-radius: 100px;
  background: var(--primary-fade);
  color: var(--primary);
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

/* 排序过渡动画 */
.card-move {
  transition: transform 0.35s ease;
}

/* ── 空态 / 错误 ────────────────── */
.empty-state {
  margin-top: 32px;
  text-align: center;
  color: var(--text-sub);
  font-size: 14px;
}

.title-error {
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
    border-radius: 16px;
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
</style>
