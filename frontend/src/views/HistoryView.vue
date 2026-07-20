<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">我的创作</h1>
      </div>
      <div class="header-actions">
        <button
          class="btn btn-secondary"
          @click="handleScanAll"
          :disabled="isScanning"
        >
          <svg v-if="!isScanning" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <div v-else class="spinner-small" style="margin-right: 6px;"></div>
          {{ isScanning ? '同步中...' : '同步历史' }}
        </button>
        <!-- 空态时中央已有同款主 CTA，右上角降级为次级样式，保证同屏只有一个主按钮 -->
        <button
          class="btn"
          :class="!loading && records.length === 0 ? 'btn-secondary' : 'btn-primary'"
          @click="router.push('/')"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建图文
        </button>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      :error="error"
      dismissible
      style="margin-bottom: 16px;"
      @dismiss="error = null"
      @retry="handleRetry"
    />

    <div v-else-if="successMessage" class="success-card" role="status" aria-live="polite">
      <span>{{ successMessage }}</span>
      <button type="button" @click="successMessage = ''" aria-label="关闭提示">×</button>
    </div>

    <!-- Stats Overview -->
    <StatsOverview v-if="stats" :stats="stats" />

    <!-- Toolbar: Tabs & Search -->
    <div class="toolbar-wrapper">
      <div class="tabs-container" style="margin-bottom: 0; border-bottom: none;">
        <div
          v-for="tab in STATUS_TABS"
          :key="tab.value"
          class="tab-item"
          :class="{ active: currentTab === tab.value }"
          @click="switchTab(tab.value)"
        >
          {{ tab.label }}
        </div>
      </div>

      <div class="toolbar-right">
        <div class="search-mini">
          <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
          <input
            v-model="searchKeyword"
            type="text"
            placeholder="搜索标题..."
            @keyup.enter="handleSearch"
          />
        </div>
        <button
          type="button"
          class="batch-toggle-btn"
          :class="{ active: batchMode }"
          @click="toggleBatchMode"
        >
          <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 11 12 14 22 4"></polyline><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"></path></svg>
          {{ batchMode ? '退出批量' : '批量管理' }}
        </button>
      </div>
    </div>

    <!-- 批量操作条 -->
    <div v-if="batchMode" class="batch-bar" role="toolbar" aria-label="批量操作">
      <div class="batch-info">
        <span class="batch-count">已选 {{ selectedIds.size }} 项</span>
        <span v-if="batchDeleting" class="batch-progress" role="status" aria-live="polite">
          删除中 {{ batchProgress.done }}/{{ batchProgress.total }}
        </span>
      </div>
      <div class="batch-actions">
        <button type="button" class="btn btn-secondary batch-btn" :disabled="batchDeleting" @click="selectAllOnPage">
          全选本页
        </button>
        <button type="button" class="btn btn-secondary batch-btn" :disabled="batchDeleting" @click="toggleBatchMode">
          取消
        </button>
        <button
          type="button"
          class="btn btn-secondary batch-btn"
          :disabled="selectedIds.size === 0 || batchDeleting"
          @click="doBatchDownload"
        >
          批量下载
        </button>
        <button
          type="button"
          class="btn batch-btn batch-btn-danger"
          :disabled="selectedIds.size === 0 || batchDeleting"
          @click="showBatchDeleteConfirm = true"
        >
          批量删除
        </button>
      </div>
    </div>

    <!-- Content Area：加载中用轻量骨架占位，避免整页 spinner 跳动 -->
    <div v-if="loading" class="gallery-grid" aria-hidden="true">
      <div v-for="i in 8" :key="i" class="skeleton-card">
        <div class="skeleton-cover"></div>
        <div class="skeleton-lines">
          <div class="skeleton-line"></div>
          <div class="skeleton-line short"></div>
        </div>
      </div>
    </div>

    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
      </div>
      <h3>暂无相关记录</h3>
      <p class="empty-tips">第一篇图文只需要一句话，从主题开始吧</p>
      <button class="btn btn-primary empty-cta" @click="router.push('/')">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        新建图文
      </button>
    </div>

    <div v-else class="gallery-grid">
      <div
        v-for="record in records"
        :key="record.id"
        class="gallery-item"
        :class="{ 'batch-selected': batchMode && selectedIds.has(record.id) }"
      >
        <div class="gallery-card-wrap">
          <GalleryCard
            :record="record"
            @preview="viewImages"
            @edit="loadRecord"
            @delete="confirmDelete"
          />
          <!-- 批量模式：覆盖层拦截卡片点击，改为切换选中 -->
          <button
            v-if="batchMode"
            type="button"
            class="batch-overlay"
            :aria-pressed="selectedIds.has(record.id)"
            :aria-label="`选择「${record.title}」`"
            @click="toggleSelect(record.id)"
          >
            <span class="batch-checkbox" :class="{ checked: selectedIds.has(record.id) }">
              <svg v-if="selectedIds.has(record.id)" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="3" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
            </span>
          </button>
        </div>
        <div v-if="!batchMode" class="card-actions">
          <!-- 爆款迭代：仅已完成/部分完成的作品可「再做一版」 -->
          <button
            v-if="canIterate(record)"
            type="button"
            class="add-plan-btn iterate-btn"
            title="把爆款再做一遍是最稳的流量打法"
            @click="openIterateModal(record)"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
            再做一版
          </button>
          <button type="button" class="add-plan-btn" @click="openPlanModal(record)">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line><line x1="12" y1="14" x2="12" y2="18"></line><line x1="10" y1="16" x2="14" y2="16"></line></svg>
            加入内容日历
          </button>
        </div>
      </div>
    </div>

    <!-- Pagination -->
    <div v-if="totalPages > 1" class="pagination-wrapper">
       <button class="page-btn" :disabled="currentPage === 1" @click="changePage(currentPage - 1)">上一页</button>
       <span class="page-indicator">第 {{ currentPage }} / {{ totalPages }} 页</span>
       <button class="page-btn" :disabled="currentPage === totalPages" @click="changePage(currentPage + 1)">下一页</button>
    </div>

    <!-- Image Viewer Modal -->
    <ImageGalleryModal
      v-if="viewingRecord"
      :visible="!!viewingRecord"
      :record="viewingRecordForModal"
      :regeneratingImages="regeneratingImages"
      @close="closeGallery"
      @showOutline="showOutlineModal = true"
      @regenerate="regenerateHistoryImage"
      @downloadAll="downloadAllImages"
      @download="downloadImage"
    />

    <!-- 大纲查看模态框 -->
    <OutlineModal
      v-if="showOutlineModal && viewingRecord"
      :visible="showOutlineModal"
      :pages="viewingRecord.outline.pages"
      @close="showOutlineModal = false"
    />

    <!-- 删除确认弹窗 -->
    <ConfirmDialog
      :visible="!!deleteTarget"
      title="删除这条创作记录？"
      :message="deleteMessage"
      confirm-text="删除"
      danger
      @confirm="doDelete"
      @cancel="deleteTarget = null"
    />

    <!-- 批量删除确认弹窗 -->
    <ConfirmDialog
      :visible="showBatchDeleteConfirm"
      title="批量删除创作记录？"
      :message="`将删除选中的 ${selectedIds.size} 条记录，删除后无法恢复。`"
      confirm-text="全部删除"
      danger
      @confirm="doBatchDelete"
      @cancel="showBatchDeleteConfirm = false"
    />

    <!-- 加入内容日历弹窗 -->
    <Teleport to="body">
      <div v-if="planTarget" class="plan-modal-overlay" @click.self="closePlanModal">
        <div class="plan-modal" role="dialog" aria-modal="true" aria-label="加入内容日历">
          <div class="plan-modal-head">
            <h3>加入内容日历</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closePlanModal">×</button>
          </div>

          <div class="plan-modal-body">
            <p class="plan-modal-record" :title="planTarget.title">「{{ planTarget.title }}」</p>

            <div class="plan-form-grid">
              <div class="plan-form-field">
                <label for="plan-platform-select">发布平台</label>
                <select id="plan-platform-select" v-model="planForm.platform" class="input">
                  <option v-for="p in PLAN_PLATFORM_OPTIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div class="plan-form-field">
                <label for="plan-date-input">计划发布日期</label>
                <input id="plan-date-input" v-model="planForm.publish_date" class="input" type="date" />
              </div>
            </div>

            <p v-if="planFormError" class="plan-form-error" role="alert">{{ planFormError }}</p>
          </div>

          <div class="plan-modal-foot">
            <button type="button" class="btn btn-secondary" @click="closePlanModal">取消</button>
            <button type="button" class="btn btn-primary" :disabled="planSaving" @click="doAddToPlan">
              {{ planSaving ? '添加中...' : '加入日历' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 爆款迭代「再做一版」方向选择弹窗 -->
    <Teleport to="body">
      <div v-if="iterateTarget" class="plan-modal-overlay" @click.self="closeIterateModal">
        <div class="plan-modal iterate-modal" role="dialog" aria-modal="true" aria-label="再做一版">
          <div class="plan-modal-head">
            <h3>再做一版</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeIterateModal">×</button>
          </div>

          <div class="plan-modal-body">
            <p class="plan-modal-record" :title="iterateTarget.title">「{{ iterateTarget.title }}」</p>
            <p class="iterate-hint">同一个选题重复做，是被验证过最稳的流量打法。选一个迭代方向：</p>

            <div class="iterate-directions" role="radiogroup" aria-label="选择迭代方向">
              <button
                v-for="direction in ITERATE_DIRECTIONS"
                :key="direction.key"
                type="button"
                class="direction-card"
                :class="{ selected: iterateDirectionKey === direction.key }"
                role="radio"
                :aria-checked="iterateDirectionKey === direction.key"
                @click="iterateDirectionKey = direction.key"
              >
                <span class="direction-label">{{ direction.label }}</span>
                <span class="direction-desc">{{ direction.desc }}</span>
              </button>
            </div>
          </div>

          <div class="plan-modal-foot">
            <button type="button" class="btn btn-secondary" :disabled="iterateLoading" @click="closeIterateModal">取消</button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="!iterateDirectionKey || iterateLoading"
              @click="doIterate"
            >
              {{ iterateLoading ? '准备中...' : '开始迭代' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted, watch } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getHistoryList,
  getHistoryStats,
  searchHistory,
  deleteHistory,
  getHistory,
  type HistoryRecord,
  type HistoryDetail,
  type Page,
  regenerateImage as apiRegenerateImage,
  updateHistory,
  scanAllTasks
} from '../api'
import { useGeneratorStore } from '../stores/generator'
import { useGenerationRestore } from '../composables/useGenerationRestore'
import { withCacheBuster } from '../utils/url'
import { createPlan, type PlanItemInput, type PlanPlatform } from '../api/calendar'

/**
 * 创建计划入参的本地扩展：附带来源历史记录 ID。
 * 后端 POST /api/plans 已支持可选 record_id（旧后端会忽略未知字段，向后兼容）。
 */
type PlanCreateInput = PlanItemInput & { record_id?: string }

// 引入组件
import StatsOverview from '../components/history/StatsOverview.vue'
import GalleryCard from '../components/history/GalleryCard.vue'
import ImageGalleryModal from '../components/history/ImageGalleryModal.vue'
import OutlineModal from '../components/history/OutlineModal.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import { normalizeApiError, type AppError } from '../utils/errors'

const router = useRouter()
const route = useRoute()
const store = useGeneratorStore()
const { hydrateFromHistory } = useGenerationRestore()

// 状态 tab：与后端 status 全集对齐（generating 为瞬态，不单列）
const STATUS_TABS: Array<{ value: string; label: string }> = [
  { value: 'all', label: '全部' },
  { value: 'completed', label: '已完成' },
  { value: 'partial', label: '部分完成' },
  { value: 'draft', label: '草稿箱' },
  { value: 'error', label: '失败' }
]

/** 统计概览数据（getHistoryStats 响应的展示子集） */
interface HistoryStats {
  total: number
  by_status: Record<string, number>
}

// 数据状态
const records = ref<HistoryRecord[]>([])
const loading = ref(false)
const stats = ref<HistoryStats | null>(null)
const currentTab = ref('all')
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

// 批量操作状态
const batchMode = ref(false)
const selectedIds = ref<Set<string>>(new Set())
const showBatchDeleteConfirm = ref(false)
const batchDeleting = ref(false)
const batchProgress = ref({ done: 0, total: 0 })

// 查看器状态
const viewingRecord = ref<HistoryDetail | null>(null)

// ImageGalleryModal 的 props 要求 task_id 为非空字符串；草稿等无任务记录退化为空串
// （此时 generated 均为空，模板只渲染占位，不会拼出图片 URL）
const viewingRecordForModal = computed(() => {
  if (!viewingRecord.value) return null
  return {
    ...viewingRecord.value,
    images: {
      task_id: viewingRecord.value.images.task_id ?? '',
      generated: viewingRecord.value.images.generated
    }
  }
})
const regeneratingImages = ref<Set<number>>(new Set())
const showOutlineModal = ref(false)
const isScanning = ref(false)
const error = ref<AppError | null>(null)
const successMessage = ref('')

// 删除确认状态
const deleteTarget = ref<{ id: string; title: string } | null>(null)
const deleteImageCount = ref(0)

// 「加入内容日历」状态
const PLAN_PLATFORM_OPTIONS: Array<{ value: PlanPlatform; label: string }> = [
  { value: 'xiaohongshu', label: '小红书' },
  { value: 'douyin', label: '抖音' },
  { value: 'gongzhonghao', label: '公众号' },
  { value: 'bilibili', label: 'B站' },
  { value: 'shipinhao', label: '视频号' }
]

/** 本地时区的 YYYY-MM-DD（避免 toISOString 的 UTC 偏移） */
function localDateStr(d: Date = new Date()): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const planTarget = ref<{ id: string; title: string } | null>(null)
const planSaving = ref(false)
const planFormError = ref('')
const planForm = ref<{ platform: PlanPlatform; publish_date: string }>({
  platform: 'xiaohongshu',
  publish_date: localDateStr()
})

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  const base = `「${deleteTarget.value.title}」删除后无法恢复。`
  if (deleteImageCount.value > 0) {
    return `${base}\n将同时删除已生成的 ${deleteImageCount.value} 张图片。`
  }
  return base
})

/**
 * 错误重试：重新加载列表与统计
 */
function handleRetry() {
  error.value = null
  loadData()
  loadStats()
}

/**
 * 加载历史记录列表
 */
async function loadData() {
  loading.value = true
  error.value = null
  try {
    const statusFilter = currentTab.value === 'all' ? undefined : currentTab.value
    const res = await getHistoryList(currentPage.value, 12, statusFilter)
    if (res.success) {
      records.value = res.records
      totalPages.value = res.total_pages
      // 列表内容变化后清空选中，避免选中项指向已不在当前页的记录
      selectedIds.value = new Set()
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '获取历史记录列表失败', '获取历史记录列表失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '获取历史记录列表失败')
  } finally {
    loading.value = false
  }
}

/**
 * 加载统计数据
 */
async function loadStats() {
  try {
    const res = await getHistoryStats()
    if (res.success) {
      stats.value = res
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '获取统计信息失败', '获取统计信息失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '获取统计信息失败')
  }
}

/**
 * 切换标签页
 */
function switchTab(tab: string) {
  currentTab.value = tab
  currentPage.value = 1
  loadData()
}

/**
 * 搜索历史记录
 */
async function handleSearch() {
  if (!searchKeyword.value.trim()) {
    loadData()
    return
  }
  loading.value = true
  error.value = null
  try {
    const res = await searchHistory(searchKeyword.value)
    if (res.success) {
      records.value = res.records
      totalPages.value = 1
      selectedIds.value = new Set()
    } else {
      error.value = normalizeApiError(res.error || res.error_message || '搜索历史记录失败', '搜索历史记录失败')
    }
  } catch(e) {
    error.value = normalizeApiError(e, '搜索历史记录失败')
  } finally {
    loading.value = false
  }
}

/**
 * 加载记录并跳转到编辑页
 * 水合逻辑统一走 useGenerationRestore 的 hydrateFromHistory（edit 场景：
 * 先重置上一会话残留状态，stage 停留在大纲页，图片 URL 统一走 getImageUrl）
 */
async function loadRecord(id: string) {
  const res = await getHistory(id)
  if (res.success && res.record) {
    hydrateFromHistory(res.record, { target: 'edit' })
    router.push('/outline')
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '打开历史记录失败', '打开历史记录失败')
  }
}

/**
 * 查看图片
 */
async function viewImages(id: string) {
  const res = await getHistory(id)
  if (res.success && res.record) {
    viewingRecord.value = res.record
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '查看图片失败', '查看图片失败')
  }
}

/**
 * 关闭图片查看器
 */
function closeGallery() {
  viewingRecord.value = null
  showOutlineModal.value = false
}

/**
 * 打开删除确认弹窗（先查询已生成图片数量，用于提示）
 */
async function confirmDelete(record: { id: string; title: string }) {
  deleteImageCount.value = 0
  deleteTarget.value = record

  // 尽力获取已生成图片数量，失败不阻断删除流程
  try {
    const res = await getHistory(record.id)
    if (res.success && res.record) {
      deleteImageCount.value = (res.record.images.generated || []).filter(Boolean).length
    }
  } catch {
    // 忽略统计失败
  }
}

/**
 * 执行删除
 */
async function doDelete() {
  if (!deleteTarget.value) return
  const id = deleteTarget.value.id
  deleteTarget.value = null

  const result = await deleteHistory(id)
  if (result.success) {
    loadData()
    loadStats()
  } else {
    error.value = normalizeApiError(result.error || result.error_message || '删除历史记录失败', '删除历史记录失败')
  }
}

/**
 * 进入/退出批量管理模式（退出时清空选中）
 */
function toggleBatchMode() {
  if (batchDeleting.value) return
  batchMode.value = !batchMode.value
  selectedIds.value = new Set()
  showBatchDeleteConfirm.value = false
}

/**
 * 切换单条记录选中状态
 */
function toggleSelect(id: string) {
  if (batchDeleting.value) return
  const next = new Set(selectedIds.value)
  if (next.has(id)) {
    next.delete(id)
  } else {
    next.add(id)
  }
  selectedIds.value = next
}

/**
 * 全选当前页
 */
function selectAllOnPage() {
  selectedIds.value = new Set(records.value.map(r => r.id))
}

/**
 * 批量删除：逐条串行调用 deleteHistory，展示进度；
 * 完成后刷新列表并退出批量模式，部分失败时给出提示。
 */
async function doBatchDelete() {
  showBatchDeleteConfirm.value = false
  const ids = [...selectedIds.value]
  if (ids.length === 0 || batchDeleting.value) return

  batchDeleting.value = true
  batchProgress.value = { done: 0, total: ids.length }
  let failed = 0

  for (const id of ids) {
    try {
      const res = await deleteHistory(id)
      if (!res.success) failed++
    } catch {
      failed++
    }
    batchProgress.value = { done: batchProgress.value.done + 1, total: ids.length }
  }

  batchDeleting.value = false
  batchMode.value = false
  selectedIds.value = new Set()
  currentPage.value = 1
  await loadData()
  await loadStats()

  if (failed > 0) {
    error.value = normalizeApiError(
      `${failed} 条删除失败，已成功删除 ${ids.length - failed} 条。`,
      '批量删除部分失败'
    )
  } else {
    successMessage.value = `已删除 ${ids.length} 条记录`
  }
}

/**
 * 批量下载：对每条有图片的选中记录触发 zip 下载，
 * 间隔 400ms 防浏览器拦截；无图片的记录跳过并计数提示。
 */
function doBatchDownload() {
  const selected = records.value.filter(r => selectedIds.value.has(r.id))
  if (selected.length === 0) return

  // 有缩略图 + 任务 ID 才有已生成图片可打包
  const downloadable = selected.filter(r => r.thumbnail && r.task_id)
  const skipped = selected.length - downloadable.length

  downloadable.forEach((record, index) => {
    setTimeout(() => {
      const link = document.createElement('a')
      link.href = `/api/history/${record.id}/download`
      link.click()
    }, index * 400)
  })

  if (downloadable.length === 0) {
    error.value = normalizeApiError('选中的记录都还没有生成图片，无法下载。', '无可下载内容')
    return
  }

  successMessage.value =
    skipped > 0
      ? `已开始下载 ${downloadable.length} 条记录，${skipped} 条无图片已跳过`
      : `已开始下载 ${downloadable.length} 条记录`
}

// ==================== 爆款迭代「再做一版」 ====================

/** 迭代方向定义：label/desc 用于弹窗展示，instruction 拼进新主题文本 */
interface IterateDirection {
  key: 'hook' | 'angle' | 'format' | 'sequel'
  label: string
  desc: string
  instruction: string
}

const ITERATE_DIRECTIONS: IterateDirection[] = [
  {
    key: 'hook',
    label: '换封面钩子',
    desc: '同一内容，换个更强的开头抓人方式',
    instruction:
      '内容主体保持同一主题，但换一个更强的封面钩子和开头抓人方式（如反问、悬念、数字冲击、身份点名），确保第一屏就能让人停下来'
  },
  {
    key: 'angle',
    label: '换切入角度',
    desc: '同一主题，从另一个人群/场景切入',
    instruction:
      '同一主题从另一个人群或场景切入（换一类目标读者、换一个使用场景），给出与上一篇不同的视角、案例和结论侧重'
  },
  {
    key: 'format',
    label: '换内容形式',
    desc: '如清单体改故事体、教程改避坑',
    instruction:
      '换一种内容形式重新组织这个主题（如清单体改故事体、教程体改避坑体、干货罗列改亲身经历复盘），信息可以重叠但表达结构要完全不同'
  },
  {
    key: 'sequel',
    label: '做续集',
    desc: '承接上一篇的延伸话题',
    instruction:
      '做上一篇的续集，承接上一篇的延伸话题（更进阶的方法、下一阶段会遇到的问题、上一篇没展开的细节），开头可以自然呼应上一篇'
  }
]

// 迭代上下文的 sessionStorage 键：存原大纲与所选方向，供后续深化消费
const ITERATE_CONTEXT_KEY = 'redink:iterate-context'

const iterateTarget = ref<{ id: string; title: string } | null>(null)
const iterateDirectionKey = ref<IterateDirection['key'] | ''>('')
const iterateLoading = ref(false)

/** 只有已完成/部分完成的作品才有「再做一版」的价值（草稿/失败没有可迭代的成品） */
function canIterate(record: { status: string }): boolean {
  return record.status === 'completed' || record.status === 'partial'
}

function openIterateModal(record: { id: string; title: string }) {
  iterateTarget.value = { id: record.id, title: record.title }
  iterateDirectionKey.value = ''
}

function closeIterateModal() {
  if (iterateLoading.value) return
  iterateTarget.value = null
}

/**
 * 确认迭代：
 * 1. 尽力拉取原作品大纲原文，与所选方向一起写入 sessionStorage
 *    （迭代上下文供未来深化，取不到大纲不阻断主流程）
 * 2. 按「原主题 + 迭代要求」构造新主题写入 generator store
 * 3. 跳回首页，由现有机制自动带入主题，用户直接点生成
 */
async function doIterate() {
  if (!iterateTarget.value || !iterateDirectionKey.value || iterateLoading.value) return
  const target = iterateTarget.value
  const direction = ITERATE_DIRECTIONS.find(d => d.key === iterateDirectionKey.value)
  if (!direction) return

  iterateLoading.value = true

  // 尽力获取原大纲原文，失败静默（上下文里 outline_raw 为空串）
  let outlineRaw = ''
  try {
    const res = await getHistory(target.id)
    if (res.success && res.record) {
      outlineRaw = res.record.outline.raw || ''
    }
  } catch {
    // 忽略大纲拉取失败
  }

  try {
    sessionStorage.setItem(ITERATE_CONTEXT_KEY, JSON.stringify({
      record_id: target.id,
      title: target.title,
      direction: direction.key,
      direction_label: direction.label,
      instruction: direction.instruction,
      outline_raw: outlineRaw,
      created_at: new Date().toISOString()
    }))
  } catch {
    // sessionStorage 不可用（如隐私模式）时忽略，不影响主题带入
  }

  const newTopic =
    `${target.title}\n` +
    `【迭代要求】基于我上一篇内容《${target.title}》做迭代：${direction.instruction}。` +
    '保持同一赛道人设，但内容不要重复上一篇。'

  store.setTopic(newTopic)
  iterateLoading.value = false
  iterateTarget.value = null
  router.push('/')
}

/**
 * 打开「加入内容日历」弹窗（默认小红书 + 今天）
 */
function openPlanModal(record: { id: string; title: string }) {
  planTarget.value = { id: record.id, title: record.title }
  planForm.value = {
    platform: 'xiaohongshu',
    publish_date: localDateStr()
  }
  planFormError.value = ''
}

function closePlanModal() {
  planTarget.value = null
}

/**
 * 用历史记录标题创建一条内容计划（状态：待发布）
 */
async function doAddToPlan() {
  if (!planTarget.value) return
  if (!planForm.value.publish_date) {
    planFormError.value = '请选择计划发布日期'
    return
  }

  planSaving.value = true
  planFormError.value = ''

  // 附带来源记录 ID，便于日历侧回链到具体作品（旧后端忽略该字段，向后兼容）
  const payload: PlanCreateInput = {
    title: planTarget.value.title,
    platform: planForm.value.platform,
    publish_date: planForm.value.publish_date,
    status: 'ready',
    notes: '来自历史作品',
    record_id: planTarget.value.id
  }
  const res = await createPlan(payload)

  planSaving.value = false

  if (res.success) {
    successMessage.value = `已加入内容日历：「${planTarget.value.title}」`
    planTarget.value = null
  } else {
    planFormError.value = res.error_message || '加入内容日历失败，请重试'
  }
}

/**
 * 切换页码
 */
function changePage(p: number) {
  currentPage.value = p
  loadData()
}

/**
 * 重新生成历史记录中的图片
 */
async function regenerateHistoryImage(index: number) {
  // 捕获局部引用：await 期间关闭查看器也不影响本次更新与保存
  const record = viewingRecord.value
  const taskId = record?.images.task_id
  if (!record || !taskId) {
    error.value = normalizeApiError('缺少任务信息，无法重新生成图片。', '无法重新生成')
    return
  }

  const page = record.outline.pages.find((item: Page) => item.index === index)
  if (!page) return

  regeneratingImages.value.add(index)

  try {
    const context = {
      fullOutline: record.outline.raw || '',
      userTopic: record.title || '',
      recordId: record.id,
      // 与旧的 api 层兜底行为保持一致：沿用当前会话记录的风格提示词
      stylePrompt: store.stylePrompt
    }

    const result = await apiRegenerateImage(taskId, page, true, context)

    if (result.success && result.image_url) {
      // image_url 可能带 query（如 ?thumbnail=true），先去掉再取文件名
      const filename = result.image_url.split('?')[0].split('/').pop() || ''

      // 持久化用的干净文件名列表（剥掉展示层可能追加过的 ?t= 时间戳）
      const cleanGenerated = record.images.generated.map(name => name.split('?')[0])
      while (cleanGenerated.length <= index) cleanGenerated.push('')
      cleanGenerated[index] = filename

      // 展示层响应式强刷：仅给本张图追加时间戳，src 变化后由模板自动重新加载；
      // generated 里存的是纯文件名，withCacheBuster 按相对路径解析会带上前导 /，需去掉
      const nextGenerated = [...record.images.generated]
      while (nextGenerated.length <= index) nextGenerated.push('')
      nextGenerated[index] = withCacheBuster(filename).replace(/^\//, '')
      record.images.generated = nextGenerated

      await updateHistory(record.id, {
        images: {
          task_id: taskId,
          generated: cleanGenerated
        }
      })

      regeneratingImages.value.delete(index)
    } else {
      regeneratingImages.value.delete(index)
      error.value = normalizeApiError(result.error || result.error_message || '重新生成失败', '重新生成失败')
    }
  } catch (e) {
    regeneratingImages.value.delete(index)
    error.value = normalizeApiError(e, '重新生成失败')
  }
}

/**
 * 下载单张图片
 */
function downloadImage(filename: string, index: number) {
  if (!viewingRecord.value) return
  // 展示层文件名可能带 ?t= 时间戳，下载前剥掉 query
  const cleanName = filename.split('?')[0]
  const link = document.createElement('a')
  link.href = `/api/images/${viewingRecord.value.images.task_id}/${cleanName}?thumbnail=false`
  link.download = `page_${index + 1}.png`
  link.click()
}

/**
 * 打包下载所有图片
 */
function downloadAllImages() {
  if (!viewingRecord.value) return
  const link = document.createElement('a')
  link.href = `/api/history/${viewingRecord.value.id}/download`
  link.click()
}

/**
 * 扫描所有任务并同步
 */
async function handleScanAll() {
  isScanning.value = true
  try {
    const result = await scanAllTasks()
    if (result.success) {
      let message = `扫描完成！\n`
      message += `- 总任务数: ${result.total_tasks || 0}\n`
      message += `- 同步成功: ${result.synced || 0}\n`
      message += `- 同步失败: ${result.failed || 0}\n`

      if (result.orphan_tasks && result.orphan_tasks.length > 0) {
        message += `- 孤立任务（无记录）: ${result.orphan_tasks.length} 个\n`
      }

      successMessage.value = message
      await loadData()
      await loadStats()
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '扫描失败', '扫描失败')
    }
  } catch (e) {
    console.error('扫描失败:', e)
    error.value = normalizeApiError(e, '扫描失败')
  } finally {
    isScanning.value = false
  }
}

// 会话级自动扫描节流标记：后端全量扫描较慢（超时 60s），
// 每个浏览器会话只自动扫描一次，手动「同步历史」按钮不受影响
const AUTO_SCAN_SESSION_KEY = 'history-auto-scan-done'

/** 本会话是否还需要自动扫描（sessionStorage 不可用时保守跳过） */
function shouldAutoScan(): boolean {
  try {
    return sessionStorage.getItem(AUTO_SCAN_SESSION_KEY) !== '1'
  } catch {
    return false
  }
}

/** 标记本会话已尝试过自动扫描 */
function markAutoScanDone() {
  try {
    sessionStorage.setItem(AUTO_SCAN_SESSION_KEY, '1')
  } catch {
    // sessionStorage 不可用时忽略（下次挂载 shouldAutoScan 也会返回 false）
  }
}

// 响应 /history/:id 与 /history 之间的导航：有 ID 打开图片查看器，无 ID 关闭
watch(
  () => route.params.id,
  async (id) => {
    if (typeof id === 'string' && id) {
      await viewImages(id)
    } else if (viewingRecord.value) {
      closeGallery()
    }
  }
)

onMounted(async () => {
  await loadData()
  await loadStats()

  // 检查路由参数，如果有 ID 则自动打开图片查看器
  if (route.params.id) {
    await viewImages(route.params.id as string)
  }

  // 自动执行一次扫描（静默，不显示结果；会话级节流，避免每次进页都触发后端全量扫描）
  if (shouldAutoScan()) {
    markAutoScanDone()
    try {
      const result = await scanAllTasks()
      if (result.success && (result.synced || 0) > 0) {
        await loadData()
        await loadStats()
      }
    } catch (e) {
      console.error('自动扫描失败:', e)
    }
  }
})
</script>

<style scoped>
/* Small Spinner */
.spinner-small {
  width: 16px;
  height: 16px;
  border: 2px solid var(--primary);
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  display: inline-block;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}

.header-actions {
  display: flex;
  gap: var(--space-3);
}

/* 加载骨架：与真实卡片同构（3:4 封面 + 两行文字），减少布局跳动 */
.skeleton-card {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
}

.skeleton-cover {
  aspect-ratio: 3/4;
  background: var(--gray-2);
}

.skeleton-lines {
  padding: var(--space-4);
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.skeleton-line {
  height: 12px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
}

.skeleton-line.short { width: 55%; }

.skeleton-cover,
.skeleton-line {
  animation: skeleton-pulse 1.4s var(--ease-out) infinite;
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

/* Toolbar */
.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-5);
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: 10px;
}

.search-mini {
  position: relative;
  width: 240px;
}

/* 批量管理切换按钮 */
.batch-toggle-btn {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: var(--font-size-caption);
  font-weight: 500;
  font-family: inherit;
  white-space: nowrap;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast), box-shadow var(--transition-fast);
}

.batch-toggle-btn:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
}

.batch-toggle-btn.active {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
}

/* 批量操作条 */
.batch-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-bottom: var(--space-5);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--gray-0);
  box-shadow: var(--shadow-xs);
}

.batch-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
}

.batch-count {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  font-variant-numeric: tabular-nums;
}

.batch-progress {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.batch-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.batch-btn {
  padding: 7px 14px;
  font-size: var(--font-size-caption);
}

.batch-btn-danger {
  border: 1px solid transparent;
  background: var(--color-danger);
  color: white;
}

.batch-btn-danger:hover:not(:disabled) {
  background: var(--color-danger);
  opacity: 0.9;
}

.batch-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* 批量模式的卡片覆盖层与复选框 */
.gallery-card-wrap {
  position: relative;
}

.batch-overlay {
  position: absolute;
  inset: 0;
  border: 2px solid transparent;
  border-radius: var(--radius-lg);
  background: transparent;
  padding: 0;
  cursor: pointer;
  z-index: 2;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.batch-overlay:hover {
  background: rgba(33, 30, 27, 0.04);
}

.gallery-item.batch-selected .batch-overlay {
  border-color: var(--primary);
  background: var(--primary-fade);
}

.batch-checkbox {
  position: absolute;
  top: 10px;
  left: 10px;
  width: 22px;
  height: 22px;
  border-radius: var(--radius-xs);
  border: 2px solid var(--gray-4);
  background: rgba(255, 255, 255, 0.94);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  box-shadow: var(--shadow-xs);
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.batch-checkbox.checked {
  background: var(--primary);
  border-color: var(--primary);
}

.search-mini input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.search-mini input::placeholder {
  color: var(--text-placeholder);
}

.search-mini input:hover {
  border-color: var(--border-hover);
}

.search-mini input:focus {
  border-color: var(--primary);
  outline: none;
  box-shadow: var(--shadow-focus);
}

.search-mini .icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: var(--text-placeholder);
}

.success-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid rgba(31, 169, 92, 0.25);
  background: var(--color-success-soft);
  color: var(--color-success);
  border-radius: var(--radius-md);
  font-size: 14px;
  white-space: pre-line;
}

.success-card button {
  border: none;
  background: transparent;
  color: var(--color-success);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  border-radius: var(--radius-xs);
  transition: opacity var(--transition-fast);
}

.success-card button:hover {
  opacity: 0.7;
}

/* Gallery Grid */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-5);
  margin-bottom: var(--space-7);
}

/* 卡片 + 加入日历按钮 */
.gallery-item {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

/* 卡片下方操作行：再做一版 / 加入日历 并排等分 */
.card-actions {
  display: flex;
  gap: var(--space-2);
}

.card-actions .add-plan-btn {
  flex: 1;
  min-width: 0;
}

.add-plan-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.add-plan-btn:hover {
  border-color: var(--border-hover);
  color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

/* 爆款迭代「再做一版」弹窗 */
.iterate-modal {
  max-width: 520px;
}

.iterate-hint {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  line-height: 1.6;
}

.iterate-directions {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-3);
}

.direction-card {
  display: flex;
  flex-direction: column;
  align-items: flex-start;
  gap: 4px;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  font-family: inherit;
  text-align: left;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
}

.direction-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.direction-card.selected {
  border-color: var(--primary);
  background: var(--primary-light);
  box-shadow: var(--shadow-focus);
}

.direction-label {
  font-size: 14px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.direction-card.selected .direction-label {
  color: var(--primary);
}

.direction-desc {
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
}

/* 加入内容日历弹窗 */
.plan-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: var(--space-5);
  animation: overlay-fade 0.2s var(--ease-out);
}

.plan-modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: modal-pop 0.2s var(--ease-out);
}

@keyframes overlay-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-pop {
  from { opacity: 0; transform: scale(0.97) translateY(8px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

.plan-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: var(--space-5) var(--space-5) var(--space-3);
}

.plan-modal-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  padding: 2px 6px;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-btn:hover {
  color: var(--text-main);
  background: var(--gray-2);
}

.plan-modal-body {
  padding: var(--space-2) var(--space-5);
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.plan-modal-record {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: var(--space-4);
}

.plan-form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-form-field label {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
}

.plan-form-error {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--color-danger);
}

.plan-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: var(--space-4) var(--space-5) var(--space-5);
  border-top: 1px solid var(--border-color);
  margin-top: var(--space-2);
}

/* Pagination */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: var(--space-4);
  margin-top: var(--space-7);
}

.page-btn {
  padding: 8px 18px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: var(--font-size-caption);
  font-weight: 500;
  font-family: inherit;
  border-radius: var(--radius-full);
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
}

.page-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.page-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.page-indicator {
  font-size: var(--font-size-caption);
  font-variant-numeric: tabular-nums;
  color: var(--text-secondary);
}

/* Empty State：图标 + 一句引导 + 主 CTA */
.empty-state-large {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-8) var(--space-5);
  color: var(--text-sub);
}

.empty-img {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-2);
  color: var(--gray-5);
}

.empty-state-large h3 {
  margin: var(--space-5) 0 0;
  font-size: var(--font-size-subtitle);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.empty-state-large .empty-tips {
  margin-top: var(--space-2);
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.empty-cta {
  margin-top: var(--space-5);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .toolbar-wrapper {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .toolbar-right {
    width: 100%;
  }

  .search-mini {
    flex: 1;
    width: auto;
  }

  .batch-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .batch-actions {
    justify-content: flex-end;
  }

  .gallery-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 14px;
  }

  .add-plan-btn {
    font-size: 12px;
    padding: 6px 8px;
  }

  /* 移动端方向卡片改单列，避免文字挤压 */
  .iterate-directions {
    grid-template-columns: 1fr;
  }

  .plan-form-grid {
    grid-template-columns: 1fr;
  }

  .plan-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  /* 移动端改为底部抽屉，入场从下方滑入 */
  .plan-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
    animation: sheet-up 0.25s var(--ease-out);
  }
}

@keyframes sheet-up {
  from { opacity: 0; transform: translateY(24px); }
  to { opacity: 1; transform: translateY(0); }
}
</style>
