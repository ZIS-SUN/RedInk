<template>
  <div class="checklist-panel">
    <!-- 初始态：虚线卡片 + 检查按钮（与爆款体检入口并列的发布合规检查入口） -->
    <div v-if="status === 'idle'" class="start-section">
      <button class="btn btn-primary start-btn" @click="handleCheck(platform)">
        <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
          <path d="M9 11l3 3L22 4"/>
          <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
        </svg>
        发布前检查
      </button>
      <p class="start-hint">按平台规范检查标题字数、标签数量、禁用词、图片完整性等，避免发布时踩线</p>
    </div>

    <!-- 错误态 -->
    <ErrorCard
      v-else-if="status === 'error'"
      :error="error"
      title="发布前检查失败"
      dismissible
      @dismiss="status = 'idle'"
      @retry="handleCheck(platform)"
    />

    <!-- 结果态 / 切换平台重查中 -->
    <div v-else class="report-card">
      <div class="report-header">
        <h3>
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M9 11l3 3L22 4"/>
            <path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
          </svg>
          发布前检查
        </h3>
        <button class="rerun-btn" :disabled="status === 'loading'" @click="handleCheck(platform)">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
            <path d="M23 4v6h-6M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          重新检查
        </button>
      </div>

      <!-- 平台切换 tabs：切换即时重查 -->
      <div class="platform-tabs" role="tablist" aria-label="选择目标平台">
        <button
          v-for="p in PLATFORMS"
          :key="p.id"
          class="platform-tab"
          :class="{ active: platform === p.id }"
          role="tab"
          :aria-selected="platform === p.id"
          :disabled="status === 'loading'"
          @click="handleCheck(p.id)"
        >
          {{ p.name }}
        </button>
      </div>

      <!-- 汇总条 -->
      <div v-if="summary" class="summary-bar" :class="{ dimmed: status === 'loading' }">
        <span class="summary-chip chip-fail" v-if="summary.fail > 0">{{ summary.fail }} 项不合规</span>
        <span class="summary-chip chip-warn" v-if="summary.warn > 0">{{ summary.warn }} 项建议关注</span>
        <span class="summary-chip chip-pass">{{ summary.pass }} 项通过</span>
        <span v-if="status === 'loading'" class="checking-hint">检查中…</span>
      </div>

      <!-- 检查项列表：按 fail -> warn -> pass 排序逐项展示 -->
      <div class="item-list" :class="{ dimmed: status === 'loading' }">
        <div v-for="item in sortedItems" :key="item.id" class="check-item">
          <span class="status-dot" :class="`dot-${item.status}`" :aria-label="statusLabel(item.status)"></span>
          <div class="check-item-body">
            <span class="check-label">{{ item.label }}</span>
            <span class="check-detail">{{ item.detail }}</span>
          </div>
        </div>
      </div>

      <p v-if="summary && summary.fail === 0 && summary.warn === 0" class="all-clear">
        全部检查通过，可以放心发布到{{ platformName }}。
      </p>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useGeneratorStore } from '../../stores/generator'
import {
  runChecklist,
  type ChecklistItem,
  type ChecklistPlatform,
  type ChecklistStatus,
  type ChecklistSummary
} from '../../api/checklist'
import ErrorCard from '../common/ErrorCard.vue'
import { normalizeApiError, type AppError } from '../../utils/errors'

const store = useGeneratorStore()

/** 平台 tab 列表（与后端 PLATFORM_RULES 的 key 一致） */
const PLATFORMS: Array<{ id: ChecklistPlatform; name: string }> = [
  { id: 'xiaohongshu', name: '小红书' },
  { id: 'douyin', name: '抖音' },
  { id: 'weixin', name: '公众号' },
  { id: 'bilibili', name: 'B站' },
  { id: 'weibo', name: '微博' }
]

// 状态机：idle -> loading -> done | error；done 后切换平台回到 loading（面板保持展开）
const status = ref<'idle' | 'loading' | 'done' | 'error'>('idle')
const platform = ref<ChecklistPlatform>('xiaohongshu')
const items = ref<ChecklistItem[]>([])
const summary = ref<ChecklistSummary | null>(null)
const error = ref<AppError | null>(null)

const platformName = computed(
  () => PLATFORMS.find(p => p.id === platform.value)?.name ?? ''
)

// fail -> warn -> pass 排序，问题项置顶
const STATUS_ORDER: Record<ChecklistStatus, number> = { fail: 0, warn: 1, pass: 2 }
const sortedItems = computed(() =>
  [...items.value].sort((a, b) => STATUS_ORDER[a.status] - STATUS_ORDER[b.status])
)

function statusLabel(s: ChecklistStatus): string {
  switch (s) {
    case 'pass': return '通过'
    case 'warn': return '建议关注'
    case 'fail': return '不合规'
  }
}

/** 执行检查：数据取自 store 当前的标题（第一个候选）/文案/标签/已生成图片数 */
async function handleCheck(target: ChecklistPlatform) {
  if (status.value === 'loading') return

  platform.value = target
  status.value = 'loading'
  error.value = null

  try {
    const result = await runChecklist({
      platform: target,
      // 结果页没有"选中标题"概念，取第一个候选标题
      title: store.content.titles[0] || undefined,
      body: store.content.copywriting || undefined,
      tags: store.content.tags.length > 0 ? store.content.tags : undefined,
      // 只统计已成功生成的图片
      imageCount: store.images.filter(img => img.status === 'done' && img.url).length
      // banned_words 不传：由服务端读取当前启用品牌档案的禁用词
    })

    if (result.success && result.items) {
      items.value = result.items
      summary.value = result.summary ?? null
      status.value = 'done'
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '检查失败', '发布前检查失败')
      status.value = 'error'
    }
  } catch (e: unknown) {
    error.value = normalizeApiError(e, '发布前检查失败')
    status.value = 'error'
  }
}
</script>

<style scoped>
.checklist-panel {
  margin-top: var(--space-4);
}

/* ==================== 初始态 ==================== */
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

.rerun-btn:hover:not(:disabled) {
  background: var(--bg-card);
  color: var(--text-main);
  border-color: var(--border-hover);
}

.rerun-btn:disabled {
  cursor: not-allowed;
  opacity: 0.6;
}

.rerun-btn svg {
  width: 14px;
  height: 14px;
}

/* ==================== 平台 tabs ==================== */
.platform-tabs {
  display: flex;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.platform-tab {
  padding: 6px 16px;
  font-size: var(--font-size-caption);
  font-weight: 600;
  font-family: inherit;
  color: var(--text-sub);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.platform-tab:hover:not(:disabled):not(.active) {
  color: var(--text-main);
  border-color: var(--border-hover);
}

.platform-tab.active {
  color: white;
  background: var(--primary);
  border-color: var(--primary);
}

.platform-tab:disabled {
  cursor: not-allowed;
  opacity: 0.7;
}

/* ==================== 汇总条 ==================== */
.summary-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.summary-chip {
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-full);
}

.chip-pass {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.chip-warn {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.chip-fail {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.checking-hint {
  font-size: 12px;
  color: var(--text-sub);
}

/* ==================== 检查项列表 ==================== */
.item-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

/* 切换平台重查时降低透明度，避免列表闪空 */
.dimmed {
  opacity: 0.5;
  pointer-events: none;
}

.check-item {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--gray-1);
  border-radius: var(--radius-md);
}

.status-dot {
  flex-shrink: 0;
  width: 10px;
  height: 10px;
  margin-top: 5px;
  border-radius: var(--radius-full);
}

.dot-pass {
  background: var(--color-success);
}

.dot-warn {
  background: var(--color-warning);
}

.dot-fail {
  background: var(--color-danger);
}

.check-item-body {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.check-label {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
}

.check-detail {
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  line-height: 1.6;
}

.all-clear {
  margin: var(--space-4) 0 0;
  text-align: center;
  font-size: var(--font-size-caption);
  color: var(--color-success);
}
</style>
