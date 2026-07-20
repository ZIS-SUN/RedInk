<template>
  <div class="review-panel">
    <!-- 初始态 / 加载态：虚线卡片 + 体检按钮 -->
    <div v-if="status === 'idle' || status === 'loading'" class="start-section">
      <button class="btn btn-primary start-btn" @click="handleReview" :disabled="status === 'loading'">
        <svg v-if="status !== 'loading'" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
        </svg>
        <span v-else class="spinner"></span>
        {{ status === 'loading' ? '体检中…约需 30 秒' : '爆款体检' }}
      </button>
      <p class="start-hint">AI 从钩子/标题/结构/情绪/行动引导五个维度给作品打分，并给出可执行的修改建议</p>
    </div>

    <!-- 错误态 -->
    <ErrorCard
      v-else-if="status === 'error'"
      :error="error"
      title="爆款体检失败"
      dismissible
      @dismiss="status = 'idle'"
      @retry="handleReview"
    />

    <!-- 结果态 -->
    <div v-else-if="status === 'done' && report" class="report-card">
      <div class="report-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M22 12h-4l-3 9L9 3l-3 9H2"/>
          </svg>
          爆款体检
        </h3>
        <button class="rerun-btn" @click="handleReview">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4v6h-6M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          重新体检
        </button>
      </div>

      <!-- 分数环 + 总评 -->
      <div class="score-section">
        <div class="score-ring" role="img" :aria-label="`综合得分 ${report.overall_score} 分`">
          <svg viewBox="0 0 120 120" width="120" height="120">
            <circle class="ring-track" cx="60" cy="60" :r="RING_RADIUS" fill="none" stroke-width="10" />
            <circle
              class="ring-value"
              cx="60" cy="60" :r="RING_RADIUS"
              fill="none" stroke-width="10" stroke-linecap="round"
              :stroke="scoreColor"
              :stroke-dasharray="RING_CIRCUMFERENCE"
              :stroke-dashoffset="ringOffset"
              transform="rotate(-90 60 60)"
            />
          </svg>
          <div class="score-number" :style="{ color: scoreColor }">
            {{ report.overall_score }}
            <span class="score-unit">分</span>
          </div>
        </div>
        <p class="verdict">{{ report.verdict }}</p>
      </div>

      <!-- 五维度条形 -->
      <div class="dimensions">
        <div v-for="dim in report.dimensions" :key="dim.name" class="dimension-row">
          <span class="dim-name">{{ dim.name }}</span>
          <div class="dim-bar">
            <div
              class="dim-bar-fill"
              :style="{ width: `${dim.score}%`, background: colorForScore(dim.score) }"
            ></div>
          </div>
          <span class="dim-score" :style="{ color: colorForScore(dim.score) }">{{ dim.score }}</span>
          <span class="dim-comment">{{ dim.comment }}</span>
        </div>
      </div>

      <!-- 修改建议 -->
      <div v-if="report.suggestions.length > 0" class="suggestions">
        <h4>修改建议</h4>
        <div v-for="(sug, index) in report.suggestions" :key="index" class="suggestion-item">
          <div class="suggestion-head">
            <span class="target-badge" :class="`target-${sug.target}`">{{ targetLabel(sug) }}</span>
            <span class="suggestion-issue">{{ sug.issue }}</span>
          </div>
          <p class="suggestion-text">{{ sug.suggestion }}</p>
          <!-- 有改写文本就展示；仅「应用」按钮受 canApply 控制（title/tags 等只读展示） -->
          <div v-if="sug.rewrite" class="rewrite-block">
            <p class="rewrite-text">{{ sug.rewrite }}</p>
            <div v-if="canApply(sug)" class="rewrite-actions">
              <button
                class="apply-btn"
                :class="{ applied: appliedIndices.has(index) }"
                :disabled="appliedIndices.has(index)"
                @click="applyRewrite(sug, index)"
              >
                <svg v-if="appliedIndices.has(index)" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                  <polyline points="20 6 9 17 4 12"/>
                </svg>
                {{ appliedIndices.has(index) ? '已应用' : (sug.target === 'page' ? '应用改写' : '应用') }}
              </button>
              <span v-if="appliedIndices.has(index) && sug.target === 'page'" class="apply-hint">
                可在图片卡上点『编辑文字→保存并重画』让新文案生效
              </span>
            </div>
          </div>
        </div>
      </div>
      <p v-else class="no-suggestions">没有需要重点修改的地方，可以直接发布。</p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, nextTick, ref } from 'vue'
import { useGeneratorStore } from '../../stores/generator'
import { reviewWork, updateHistory, type ReviewReport, type ReviewSuggestion } from '../../api'
import ErrorCard from '../common/ErrorCard.vue'
import { normalizeApiError, type AppError } from '../../utils/errors'

const store = useGeneratorStore()

// 状态机：idle -> loading -> done | error；done/error 可通过重新体检回到 loading
const status = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const report = ref<ReviewReport | null>(null)
const error = ref<AppError | null>(null)
// 已应用改写的建议索引（结果只存组件内存，不持久化）
const appliedIndices = ref<Set<number>>(new Set())

// ==================== 分数环 ====================
const RING_RADIUS = 52
const RING_CIRCUMFERENCE = 2 * Math.PI * RING_RADIUS

// 从 0 过渡到实际分数，驱动圆环动画（prefers-reduced-motion 下 CSS 关闭过渡）
const displayScore = ref(0)

const ringOffset = computed(() =>
  RING_CIRCUMFERENCE * (1 - displayScore.value / 100)
)

function colorForScore(score: number): string {
  if (score >= 80) return 'var(--color-success)'
  if (score >= 60) return 'var(--color-warning)'
  return 'var(--color-danger)'
}

const scoreColor = computed(() =>
  report.value ? colorForScore(report.value.overall_score) : 'var(--color-warning)'
)

// ==================== 体检 ====================
async function handleReview() {
  if (status.value === 'loading') return

  status.value = 'loading'
  error.value = null

  try {
    const result = await reviewWork({
      topic: store.topic,
      pages: store.outline.pages,
      titles: store.content.titles.length > 0 ? store.content.titles : undefined,
      copywriting: store.content.copywriting || undefined,
      tags: store.content.tags.length > 0 ? store.content.tags : undefined
    })

    if (result.success && result.review) {
      report.value = result.review
      appliedIndices.value = new Set()
      status.value = 'done'
      // 先以 0 渲染圆环，下一帧再设为实际分数触发过渡动画
      displayScore.value = 0
      await nextTick()
      requestAnimationFrame(() => {
        displayScore.value = report.value?.overall_score ?? 0
      })
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '体检失败', '爆款体检失败')
      status.value = 'error'
    }
  } catch (e: unknown) {
    error.value = normalizeApiError(e, '爆款体检失败')
    status.value = 'error'
  }
}

// ==================== 建议展示与应用 ====================
function targetLabel(sug: ReviewSuggestion): string {
  switch (sug.target) {
    case 'page':
      return sug.page_index !== null ? `第 ${sug.page_index + 1} 页` : '页面'
    case 'title':
      return '标题'
    case 'copywriting':
      return '文案'
    case 'tags':
      return '标签'
  }
}

// 只有 page（且能找到对应页）和 copywriting 支持一键应用改写
function canApply(sug: ReviewSuggestion): boolean {
  if (sug.target === 'copywriting') return true
  if (sug.target === 'page') {
    return sug.page_index !== null
      && store.outline.pages.some(p => p.index === sug.page_index)
  }
  return false
}

async function applyRewrite(sug: ReviewSuggestion, index: number) {
  if (appliedIndices.value.has(index) || !sug.rewrite) return

  if (sug.target === 'page' && sug.page_index !== null) {
    store.updatePage(sug.page_index, sug.rewrite)
    // 触发 Set 的响应式更新需要替换引用
    appliedIndices.value = new Set(appliedIndices.value).add(index)
    if (store.recordId) {
      // 同步失败不阻断本地编辑（store 已持久化到 localStorage）
      await updateHistory(store.recordId, {
        outline: { raw: store.outline.raw, pages: store.outline.pages }
      })
    }
  } else if (sug.target === 'copywriting') {
    store.updateCopywriting(sug.rewrite)
    appliedIndices.value = new Set(appliedIndices.value).add(index)
  }
}
</script>

<style scoped>
.review-panel {
  margin-top: var(--space-6);
}

/* ==================== 初始态 / 加载态 ==================== */
.start-section {
  text-align: center;
  padding: var(--space-7) var(--space-5);
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  border: 2px dashed var(--gray-4);
}

.start-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 32px;
  font-size: 16px;
}

.start-btn svg {
  width: 20px;
  height: 20px;
}

.start-hint {
  margin: var(--space-4) 0 0;
  font-size: var(--font-size-caption);
  color: var(--text-sub);
}

/* ==================== 结果卡片 ==================== */
.report-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-xs);
}

.report-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.report-header h3 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0;
}

.report-header h3 svg {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.rerun-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: var(--font-size-caption);
  font-family: inherit;
  color: var(--text-sub);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.rerun-btn:hover {
  background: var(--bg-card);
  color: var(--text-main);
  border-color: var(--border-hover);
}

.rerun-btn svg {
  width: 14px;
  height: 14px;
}

/* ==================== 分数环 ==================== */
.score-section {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-4) 0 var(--space-5);
}

.score-ring {
  position: relative;
  width: 120px;
  height: 120px;
}

.ring-track {
  stroke: var(--gray-2);
}

.ring-value {
  transition: stroke-dashoffset 0.9s var(--ease-out);
}

@media (prefers-reduced-motion: reduce) {
  .ring-value {
    transition: none;
  }
}

.score-number {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 34px;
  font-weight: 700;
  letter-spacing: var(--tracking-tighter);
}

.score-unit {
  font-size: 14px;
  font-weight: 500;
  margin-left: 2px;
  margin-top: 12px;
}

.verdict {
  margin: 0;
  max-width: 560px;
  text-align: center;
  font-size: var(--font-size-body);
  line-height: 1.6;
  color: var(--text-main);
}

/* ==================== 五维度条形 ==================== */
.dimensions {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  padding-bottom: var(--space-5);
}

.dimension-row {
  display: grid;
  grid-template-columns: 76px minmax(80px, 180px) 34px 1fr;
  align-items: center;
  gap: var(--space-3);
}

.dim-name {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
}

.dim-bar {
  height: 8px;
  background: var(--gray-2);
  border-radius: var(--radius-full);
  overflow: hidden;
}

.dim-bar-fill {
  height: 100%;
  border-radius: var(--radius-full);
}

.dim-score {
  font-size: var(--font-size-caption);
  font-weight: 700;
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.dim-comment {
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  line-height: 1.5;
}

/* ==================== 修改建议 ==================== */
.suggestions h4 {
  margin: 0 0 var(--space-3);
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-color);
}

.suggestion-item {
  padding: var(--space-3) var(--space-4);
  background: var(--gray-1);
  border-radius: var(--radius-md);
}

.suggestion-item + .suggestion-item {
  margin-top: var(--space-3);
}

.suggestion-head {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.target-badge {
  flex-shrink: 0;
  padding: 3px 8px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-xs);
  background: var(--color-info-soft);
  color: var(--color-info);
}

.target-badge.target-page {
  background: var(--primary-light);
  color: var(--primary);
}

.suggestion-issue {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.5;
}

.suggestion-text {
  margin: var(--space-2) 0 0;
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  line-height: 1.6;
}

.rewrite-block {
  margin-top: var(--space-3);
  padding: var(--space-3);
  background: var(--bg-card);
  border: 1px dashed var(--border-hover);
  border-radius: var(--radius-sm);
}

.rewrite-text {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--text-main);
  line-height: 1.6;
  white-space: pre-line;
}

.rewrite-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-top: var(--space-2);
}

.apply-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.apply-btn:hover:not(:disabled) {
  background: var(--primary-hover);
}

.apply-btn.applied {
  background: var(--color-success-soft);
  color: var(--color-success);
  cursor: default;
}

.apply-btn svg {
  width: 12px;
  height: 12px;
}

.apply-hint {
  font-size: 12px;
  color: var(--color-success);
  line-height: 1.5;
}

.no-suggestions {
  margin: 0;
  padding-top: var(--space-4);
  border-top: 1px solid var(--border-color);
  text-align: center;
  font-size: var(--font-size-caption);
  color: var(--text-sub);
}

/* ==================== 动画 ==================== */
@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255, 255, 255, 0.3);
  border-top-color: white;
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}

/* 移动端：维度行换行展示点评 */
@media (max-width: 640px) {
  .dimension-row {
    grid-template-columns: 76px 1fr 34px;
  }

  .dim-comment {
    grid-column: 1 / -1;
    margin-top: -4px;
  }
}
</style>
