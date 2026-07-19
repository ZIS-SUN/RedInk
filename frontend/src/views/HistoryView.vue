<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">我的创作</h1>
      </div>
      <div style="display: flex; gap: 10px;">
        <button
          class="btn"
          @click="handleScanAll"
          :disabled="isScanning"
          style="border: 1px solid var(--border-color);"
        >
          <svg v-if="!isScanning" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M23 4v6h-6"></path><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          <div v-else class="spinner-small" style="margin-right: 6px;"></div>
          {{ isScanning ? '同步中...' : '同步历史' }}
        </button>
        <button class="btn btn-primary" @click="router.push('/')">
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
          class="tab-item"
          :class="{ active: currentTab === 'all' }"
          @click="switchTab('all')"
        >
          全部
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'completed' }"
          @click="switchTab('completed')"
        >
          已完成
        </div>
        <div
          class="tab-item"
          :class="{ active: currentTab === 'draft' }"
          @click="switchTab('draft')"
        >
          草稿箱
        </div>
      </div>

      <div class="search-mini">
        <svg class="icon" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>
        <input
          v-model="searchKeyword"
          type="text"
          placeholder="搜索标题..."
          @keyup.enter="handleSearch"
        />
      </div>
    </div>

    <!-- Content Area -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M21 16V8a2 2 0 0 0-1-1.73l-7-4a2 2 0 0 0-2 0l-7 4A2 2 0 0 0 3 8v8a2 2 0 0 0 1 1.73l7 4a2 2 0 0 0 2 0l7-4A2 2 0 0 0 21 16z"></path><polyline points="3.27 6.96 12 12.01 20.73 6.96"></polyline><line x1="12" y1="22.08" x2="12" y2="12"></line></svg>
      </div>
      <h3>暂无相关记录</h3>
      <p class="empty-tips">去创建一个新的作品吧</p>
    </div>

    <div v-else class="gallery-grid">
      <div v-for="record in records" :key="record.id" class="gallery-item">
        <GalleryCard
          :record="record"
          @preview="viewImages"
          @edit="loadRecord"
          @delete="confirmDelete"
        />
        <button type="button" class="add-plan-btn" @click="openPlanModal(record)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line><line x1="12" y1="14" x2="12" y2="18"></line><line x1="10" y1="16" x2="14" y2="16"></line></svg>
          加入内容日历
        </button>
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
      :record="viewingRecord"
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
            <button type="button" class="btn" style="border: 1px solid var(--border-color, #eee);" @click="closePlanModal">取消</button>
            <button type="button" class="btn btn-primary" :disabled="planSaving" @click="doAddToPlan">
              {{ planSaving ? '添加中...' : '加入日历' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

  </div>
</template>

<script setup lang="ts">
import { ref, computed, onMounted } from 'vue'
import { useRouter, useRoute } from 'vue-router'
import {
  getHistoryList,
  getHistoryStats,
  searchHistory,
  deleteHistory,
  getHistory,
  type HistoryRecord,
  regenerateImage as apiRegenerateImage,
  updateHistory,
  scanAllTasks
} from '../api'
import { useGeneratorStore } from '../stores/generator'
import { createPlan, type PlanPlatform } from '../api/calendar'

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

// 数据状态
const records = ref<HistoryRecord[]>([])
const loading = ref(false)
const stats = ref<any>(null)
const currentTab = ref('all')
const searchKeyword = ref('')
const currentPage = ref(1)
const totalPages = ref(1)

// 查看器状态
const viewingRecord = ref<any>(null)
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
    let statusFilter = currentTab.value === 'all' ? undefined : currentTab.value
    const res = await getHistoryList(currentPage.value, 12, statusFilter)
    if (res.success) {
      records.value = res.records
      totalPages.value = res.total_pages
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
 */
async function loadRecord(id: string) {
  const res = await getHistory(id)
  if (res.success && res.record) {
    // 定向重置上一会话残留状态，防止上一篇的内容串到新记录：
    // 清空标题/文案/标签、重置生成进度、清空旧图片/任务ID/用户上传图
    store.clearContent()
    store.progress = { current: 0, total: 0, status: 'idle' }
    store.images = []
    store.taskId = null
    store.userImages = []

    store.setTopic(res.record.title)
    store.setOutline(res.record.outline.raw, res.record.outline.pages)
    store.setRecordId(res.record.id)
    const generated = res.record.images.generated || []
    if (generated.some(Boolean)) {
      store.taskId = res.record.images.task_id
      store.images = res.record.outline.pages.map((page, idx) => {
        const filename = generated[page.index] || generated[idx] || ''
        return {
          index: page.index,
          url: filename ? `/api/images/${res.record!.images.task_id}/${filename}` : '',
          status: filename ? 'done' : 'error',
          retryable: !filename
        }
      })
      // 同步进度到恢复的图片状态
      const doneCount = store.images.filter(img => img.status === 'done').length
      store.progress = {
        current: doneCount,
        total: store.images.length,
        status: doneCount >= store.images.length ? 'done' : 'error'
      }
    }
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
  if (res.success) {
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

  const res = await createPlan({
    title: planTarget.value.title,
    platform: planForm.value.platform,
    publish_date: planForm.value.publish_date,
    status: 'ready',
    notes: '来自历史作品'
  })

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
  if (!viewingRecord.value || !viewingRecord.value.images.task_id) {
    error.value = normalizeApiError('缺少任务信息，无法重新生成图片。', '无法重新生成')
    return
  }

  const page = viewingRecord.value.outline.pages.find((item: any) => item.index === index)
  if (!page) return

  regeneratingImages.value.add(index)

  try {
    const context = {
      fullOutline: viewingRecord.value.outline.raw || '',
      userTopic: viewingRecord.value.title || '',
      recordId: viewingRecord.value.id
    }

    const result = await apiRegenerateImage(
      viewingRecord.value.images.task_id,
      page,
      true,
      context
    )

    if (result.success && result.image_url) {
      const filename = result.image_url.split('/').pop()
      while (viewingRecord.value.images.generated.length <= index) {
        viewingRecord.value.images.generated.push('')
      }
      viewingRecord.value.images.generated[index] = filename

      // 刷新图片
      const timestamp = Date.now()
      const imgElements = document.querySelectorAll(`img[src*="${viewingRecord.value.images.task_id}/${filename}"]`)
      imgElements.forEach(img => {
        const baseUrl = (img as HTMLImageElement).src.split('?')[0]
        ;(img as HTMLImageElement).src = `${baseUrl}?t=${timestamp}`
      })

      await updateHistory(viewingRecord.value.id, {
        images: {
          task_id: viewingRecord.value.images.task_id,
          generated: viewingRecord.value.images.generated
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
  const link = document.createElement('a')
  link.href = `/api/images/${viewingRecord.value.images.task_id}/${filename}?thumbnail=false`
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

onMounted(async () => {
  await loadData()
  await loadStats()

  // 检查路由参数，如果有 ID 则自动打开图片查看器
  if (route.params.id) {
    await viewImages(route.params.id as string)
  }

  // 自动执行一次扫描（静默，不显示结果）
  try {
    const result = await scanAllTasks()
    if (result.success && (result.synced || 0) > 0) {
      await loadData()
      await loadStats()
    }
  } catch (e) {
    console.error('自动扫描失败:', e)
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

/* Toolbar */
.toolbar-wrapper {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: 24px;
  border-bottom: 1px solid var(--border-color);
  padding-bottom: 0;
}

.search-mini {
  position: relative;
  width: 240px;
  margin-bottom: 10px;
}

.search-mini input {
  width: 100%;
  padding: 8px 12px 8px 36px;
  border-radius: 100px;
  border: 1px solid var(--border-color);
  font-size: 14px;
  background: white;
  transition: border-color 0.2s, box-shadow 0.2s;
}

.search-mini input:focus {
  border-color: var(--primary);
  outline: none;
  box-shadow: 0 0 0 3px var(--primary-light);
}

.search-mini .icon {
  position: absolute;
  left: 12px;
  top: 50%;
  transform: translateY(-50%);
  color: #ccc;
}

.success-card {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--color-success-soft, #bbf7d0);
  background: var(--color-success-soft, #f0fdf4);
  color: var(--color-success, #166534);
  border-radius: 8px;
  font-size: 14px;
  white-space: pre-line;
}

.success-card button {
  border: none;
  background: transparent;
  color: var(--color-success, #166534);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

/* Gallery Grid */
.gallery-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: 24px;
  margin-bottom: 40px;
}

/* 卡片 + 加入日历按钮 */
.gallery-item {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.add-plan-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 6px;
  padding: 7px 12px;
  border: 1px solid var(--border-color, #eee);
  border-radius: 100px;
  background: white;
  color: var(--text-sub, #666);
  font-size: 13px;
  cursor: pointer;
  transition: border-color 0.2s, color 0.2s, background-color 0.2s;
}

.add-plan-btn:hover {
  border-color: var(--primary, #ff2442);
  color: var(--primary, #ff2442);
  background: var(--primary-light, #fff7f8);
}

/* 加入内容日历弹窗 */
.plan-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.plan-modal {
  background: white;
  border-radius: 14px;
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.plan-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 12px;
}

.plan-modal-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-secondary, #999);
  cursor: pointer;
}

.plan-modal-body {
  padding: 8px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.plan-modal-record {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.plan-form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-form-field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main, #333);
}

.plan-form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger, #ef4444);
}

.plan-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color, #eee);
  margin-top: 8px;
}

/* Pagination */
.pagination-wrapper {
  display: flex;
  justify-content: center;
  align-items: center;
  gap: 16px;
  margin-top: 40px;
}

.page-btn {
  padding: 8px 16px;
  border: 1px solid var(--border-color);
  background: white;
  border-radius: 6px;
  cursor: pointer;
}

.page-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

/* Empty State */
.empty-state-large {
  text-align: center;
  padding: 80px 0;
  color: var(--text-sub);
}

.empty-img {
  font-size: 64px;
  opacity: 0.5;
}

.empty-state-large .empty-tips {
  margin-top: 10px;
  color: var(--text-placeholder);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .toolbar-wrapper {
    flex-direction: column;
    align-items: stretch;
    gap: 12px;
  }

  .search-mini {
    width: 100%;
  }

  .gallery-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: 14px;
  }

  .add-plan-btn {
    font-size: 12px;
    padding: 6px 8px;
  }

  .plan-form-grid {
    grid-template-columns: 1fr;
  }

  .plan-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .plan-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: 14px 14px 0 0;
  }
}
</style>
