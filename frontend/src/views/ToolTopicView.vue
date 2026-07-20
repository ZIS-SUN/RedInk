<template>
  <div class="container topic-container">
    <!-- 头部 -->
    <div class="tool-header">
      <div class="brand-pill">
        <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
        AI 灵感选题
      </div>
      <h1 class="page-title">找不到选题？让 AI 给你灵感</h1>
      <p class="page-subtitle">输入你的领域赛道，AI 基于常青角度与爆款规律生成一批选题灵感（非实时热榜数据），选中即可一键进入创作</p>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <label class="field-label" for="topic-niche">你的领域 / 赛道</label>
      <input
        id="topic-niche"
        v-model="niche"
        class="niche-input"
        type="text"
        maxlength="100"
        placeholder="例如：健身减脂、职场干货、亲子育儿、家常菜教程……"
        @keydown.enter.prevent="handleGenerate"
      />

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

      <div class="field-group account-data-row">
        <label class="account-data-toggle">
          <input
            v-model="useAccountData"
            type="checkbox"
            class="account-data-checkbox"
          />
          <span class="account-data-label">结合我的账号数据</span>
        </label>
        <span class="account-data-hint">需先在数据复盘工具录入笔记数据</span>
      </div>

      <button
        type="button"
        class="btn btn-primary generate-btn"
        :disabled="loading || !niche.trim()"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '正在生成选题灵感…' : '生成选题灵感' }}
      </button>
    </div>

    <!-- 加载骨架（仅首次生成时占位，重新生成时保留旧结果） -->
    <div v-if="loading && topics.length === 0" class="skeleton-section" aria-hidden="true">
      <div v-for="n in 3" :key="n" class="skeleton-card">
        <span class="sk-lines">
          <span class="sk-line sk-wide"></span>
          <span class="sk-line sk-narrow"></span>
        </span>
        <span class="sk-circle"></span>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="topics.length > 0" class="result-section">
      <div v-if="accountContextUsed" class="account-context-banner" role="status">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"/><polyline points="22 4 12 14.01 9 11.01"/></svg>
        已结合你的账号数据生成
      </div>
      <div class="result-toolbar">
        <span class="result-count">
          共 {{ topics.length }} 条灵感<template v-if="formatFilter !== ALL_FORMATS">，筛选后 {{ displayTopics.length }} 条</template>
        </span>
        <button
          type="button"
          class="sort-btn"
          :class="{ active: sortByHeat }"
          @click="sortByHeat = !sortByHeat"
        >
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="m3 8 4-4 4 4"/><path d="M7 4v16"/><path d="M15 8h6"/><path d="M15 12h4"/><path d="M15 16h2"/></svg>
          {{ sortByHeat ? '按热度排序中' : '按热度排序' }}
        </button>
      </div>

      <!-- 按内容形式筛选 -->
      <div v-if="formatOptions.length > 2" class="filter-row">
        <button
          v-for="f in formatOptions"
          :key="f"
          type="button"
          class="filter-chip"
          :class="{ active: formatFilter === f }"
          @click="formatFilter = f"
        >{{ f }}</button>
      </div>

      <transition-group name="card" tag="div" class="topic-list">
        <div
          v-for="(item, i) in displayTopics"
          :key="item.title"
          class="topic-card"
          :style="{ '--i': i }"
        >
          <div class="card-main">
            <div class="card-top">
              <span class="format-badge">{{ item.format }}</span>
              <p class="card-title">{{ item.title }}</p>
            </div>
            <p class="card-angle">{{ item.angle }}</p>
            <div v-if="item.tags.length > 0" class="card-tags">
              <span v-for="tag in item.tags" :key="tag" class="tag-item">#{{ tag }}</span>
            </div>
          </div>

          <div class="card-side">
            <div class="heat-block" :class="heatClass(item.heat)">
              <span class="heat-num">{{ item.heat }}</span>
              <span class="heat-label">预估热度</span>
            </div>
            <div class="card-actions">
              <button
                type="button"
                class="use-btn"
                @click="handleUse(item)"
              >
                用这个选题创作
              </button>
              <button
                type="button"
                class="copy-btn"
                :class="{ copied: copiedTitle === item.title }"
                @click="handleCopy(item)"
              >
                {{ copiedTitle === item.title ? '已复制' : '复制' }}
              </button>
            </div>
          </div>
        </div>
      </transition-group>

      <p class="result-disclaimer">* 热度为 AI 基于经验的主观预估，仅供选题参考，非平台实时数据</p>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <div class="empty-icon" aria-hidden="true">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M15 14c.2-1 .7-1.7 1.5-2.5 1-.9 1.5-2.2 1.5-3.5A6 6 0 0 0 6 8c0 1 .2 2.2 1.5 3.5.7.7 1.3 1.5 1.5 2.5"/><path d="M9 18h6"/><path d="M10 22h4"/></svg>
      </div>
      <p class="empty-title">{{ hasGenerated ? '没有生成有效的选题' : '还没有选题灵感' }}</p>
      <p class="empty-desc">{{ hasGenerated ? '换个领域描述再试试吧' : '输入你的领域赛道，选好平台后点「生成选题灵感」，选中的选题可一键进入创作' }}</p>
      <p v-if="!hasGenerated" class="empty-example">试试：健身减脂、职场干货、亲子育儿</p>
    </div>

    <ErrorCard
      v-if="error"
      class="topic-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onUnmounted, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { generateTopics, type TopicIdea } from '../api/topic'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const PLATFORMS = ['小红书', '抖音', '视频号', 'B站', '公众号'] as const
const ALL_FORMATS = '全部形式'

const router = useRouter()
const store = useGeneratorStore()

const niche = ref('')
const platform = ref<string>(PLATFORMS[0])
const useAccountData = ref(false)
const accountContextUsed = ref(false)
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const topics = ref<TopicIdea[]>([])
const sortByHeat = ref(true)
const formatFilter = ref(ALL_FORMATS)
const copiedTitle = ref('')

let copyTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})

// 结果中出现过的内容形式，用于筛选 chips
const formatOptions = computed(() => {
  const set = new Set(topics.value.map(t => t.format).filter(Boolean))
  return [ALL_FORMATS, ...set]
})

const displayTopics = computed(() => {
  let list = topics.value
  if (formatFilter.value !== ALL_FORMATS) {
    list = list.filter(t => t.format === formatFilter.value)
  }
  if (sortByHeat.value) {
    list = [...list].sort((a, b) => b.heat - a.heat)
  }
  return list
})

// 新一批结果生成后重置筛选，避免残留的筛选项把结果全部过滤掉
watch(topics, () => {
  formatFilter.value = ALL_FORMATS
})

function heatClass(heat: number): string {
  if (heat >= 85) return 'heat-high'
  if (heat >= 70) return 'heat-mid'
  return 'heat-low'
}

async function handleGenerate() {
  if (!niche.value.trim() || loading.value) return

  loading.value = true
  error.value = null

  try {
    const result = await generateTopics({
      niche: niche.value.trim(),
      platform: platform.value,
      ...(useAccountData.value ? { use_account_data: true } : {})
    })

    if (result.success && result.topics) {
      topics.value = result.topics
      accountContextUsed.value = result.account_context_used === true
      hasGenerated.value = true
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成选题灵感失败',
        '生成选题灵感失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成选题灵感失败')
  } finally {
    loading.value = false
  }
}

/**
 * 把选题用于创作：把标题、切入角度、建议标签组合成更丰富的主题文本
 * 写入 generator store，跳回首页创作流程（空字段跳过对应行）
 */
function handleUse(item: TopicIdea) {
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

async function handleCopy(item: TopicIdea) {
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
  copiedTitle.value = item.title
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedTitle.value = '' }, 1500)
}
</script>

<style scoped>
.topic-container {
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

/* ── 结合账号数据开关 ─────────────── */
.account-data-row {
  display: flex;
  align-items: center;
  flex-wrap: wrap;
  gap: 8px;
}

.account-data-toggle {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  cursor: pointer;
  user-select: none;
}

.account-data-checkbox {
  width: 16px;
  height: 16px;
  margin: 0;
  accent-color: var(--primary);
  cursor: pointer;
}

.account-data-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.account-data-hint {
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  opacity: 0.85;
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

.sk-lines {
  flex: 1;
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.sk-line,
.sk-circle {
  display: block;
  background: linear-gradient(90deg, var(--gray-2) 25%, var(--gray-1) 45%, var(--gray-2) 65%);
  background-size: 200% 100%;
  animation: shimmer 1.4s ease-in-out infinite;
}

.sk-line {
  height: 14px;
  border-radius: var(--radius-full);
}

.sk-wide { width: 72%; }
.sk-narrow { width: 45%; height: 12px; }

.sk-circle {
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

.account-context-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding: 10px 14px;
  border-radius: var(--radius-md);
  border: 1px solid var(--primary);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 13.5px;
  font-weight: 500;
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

.filter-row {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
  margin-bottom: 14px;
  padding: 0 4px;
}

.filter-chip {
  padding: 5px 13px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.filter-chip:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.filter-chip.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.topic-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.topic-card {
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

.topic-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.card-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.card-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
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

.card-title {
  margin: 0;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.55;
  word-break: break-word;
}

.card-angle {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.6;
  word-break: break-word;
}

.card-tags {
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

.card-side {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 10px;
}

.heat-block {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  width: 54px;
  height: 54px;
  border-radius: 50%;
  border: 3px solid;
}

.heat-block.heat-high {
  border-color: var(--primary);
  color: var(--primary);
}

.heat-block.heat-mid {
  border-color: var(--color-warning);
  color: var(--color-warning);
}

.heat-block.heat-low {
  border-color: var(--border-hover);
  color: var(--text-sub);
}

.heat-num {
  font-size: 17px;
  font-weight: 700;
  line-height: 1;
}

.heat-label {
  font-size: 9px;
  opacity: 0.75;
  margin-top: 2px;
  white-space: nowrap;
}

.card-actions {
  display: flex;
  flex-direction: column;
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

.result-disclaimer {
  margin: 16px 4px 0;
  font-size: 12.5px;
  color: var(--text-sub);
  opacity: 0.8;
}

/* 排序/筛选过渡动画 */
.card-move {
  transition: transform 0.35s var(--ease-out);
}

.card-enter-active,
.card-leave-active {
  transition: opacity 0.25s var(--ease-out), transform 0.25s var(--ease-out);
}

.card-enter-from,
.card-leave-to {
  opacity: 0;
  transform: translateY(8px);
}

.card-leave-active {
  position: absolute;
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

.topic-error {
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
  .topic-container {
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

  .topic-card {
    flex-wrap: wrap;
    padding: 14px;
    gap: 10px;
  }

  .card-main {
    flex-basis: 100%;
  }

  .card-side {
    flex-direction: row;
    width: 100%;
    justify-content: space-between;
    padding-top: 10px;
    border-top: 1px dashed var(--border-color);
  }

  .card-actions {
    flex-direction: row;
  }

  .heat-block {
    width: 46px;
    height: 46px;
    border-width: 2.5px;
  }

  .heat-num {
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
  .topic-card,
  .empty-state,
  .topic-error {
    animation: none;
  }

  .sk-line,
  .sk-circle {
    animation: none;
    background: var(--gray-2);
  }

  .card-move,
  .card-enter-active,
  .card-leave-active {
    transition: none;
  }

  .option-chip,
  .option-chip:hover,
  .use-btn,
  .use-btn:hover,
  .copy-btn,
  .copy-btn:hover,
  .topic-card:hover {
    transform: none;
  }
}
</style>
