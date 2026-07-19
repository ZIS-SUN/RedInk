<template>
  <div class="container" style="max-width: 1080px;">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">内容日历</h1>
        <p class="page-subtitle">规划发布节奏，追踪每条内容从想法到发布的进度</p>
      </div>
      <button type="button" class="btn btn-primary" @click="openCreateModal()">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        新建计划
      </button>
    </div>

    <!-- 反馈提示 -->
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

    <!-- 统计卡片 -->
    <div v-if="stats" class="stats-row">
      <div class="stat-card">
        <span class="stat-num">{{ stats.total }}</span>
        <span class="stat-label">本月计划</span>
      </div>
      <div
        v-for="s in STATUS_OPTIONS"
        :key="s.value"
        class="stat-card"
        :class="`stat-${s.value}`"
      >
        <span class="stat-num">{{ stats.by_status[s.value] ?? 0 }}</span>
        <span class="stat-label">{{ s.label }}</span>
      </div>
    </div>

    <!-- 工具栏：月份切换 / 视图切换 / 筛选 -->
    <div class="toolbar">
      <div class="month-nav">
        <button type="button" class="btn btn-mini" aria-label="上一月" @click="shiftMonth(-1)">‹</button>
        <span class="month-text">{{ monthDisplay }}</span>
        <button type="button" class="btn btn-mini" aria-label="下一月" @click="shiftMonth(1)">›</button>
        <button v-if="currentMonth !== todayMonth" type="button" class="btn btn-mini" @click="goToday">回到本月</button>
      </div>

      <div class="toolbar-right">
        <select v-model="filterPlatform" class="input select-mini" aria-label="按平台筛选">
          <option value="">全部平台</option>
          <option v-for="p in PLATFORM_OPTIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
        </select>
        <select v-model="filterStatus" class="input select-mini" aria-label="按状态筛选">
          <option value="">全部状态</option>
          <option v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
        </select>

        <div class="view-toggle" role="tablist" aria-label="视图切换">
          <button
            type="button"
            class="view-toggle-btn"
            :class="{ active: viewMode === 'month' }"
            :aria-pressed="viewMode === 'month'"
            @click="viewMode = 'month'"
          >月历</button>
          <button
            type="button"
            class="view-toggle-btn"
            :class="{ active: viewMode === 'list' }"
            :aria-pressed="viewMode === 'list'"
            @click="viewMode = 'list'"
          >列表</button>
        </div>
      </div>
    </div>

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <template v-else>
      <!-- 月历视图 -->
      <div v-if="viewMode === 'month'" class="calendar-wrap card">
        <div class="calendar-grid calendar-head">
          <div v-for="w in WEEKDAYS" :key="w" class="weekday-cell">{{ w }}</div>
        </div>
        <div class="calendar-grid">
          <div
            v-for="cell in calendarCells"
            :key="cell.key"
            class="day-cell"
            :class="{ 'other-month': !cell.inMonth, today: cell.date === todayDate }"
            @click="cell.inMonth && openCreateModal(cell.date)"
          >
            <span class="day-num">{{ cell.day }}</span>
            <div class="day-plans">
              <button
                v-for="plan in plansByDate[cell.date] || []"
                :key="plan.id"
                type="button"
                class="plan-chip"
                :class="[`chip-${plan.status}`]"
                :title="`${platformLabel(plan.platform)} · ${statusLabel(plan.status)}\n${plan.title}`"
                @click.stop="openEditModal(plan)"
              >
                <span class="chip-dot" :style="{ background: platformColor(plan.platform) }"></span>
                <span class="chip-title">{{ plan.title }}</span>
              </button>
            </div>
          </div>
        </div>
        <p class="calendar-hint">点击日期新建计划，点击条目查看/编辑</p>
      </div>

      <!-- 列表视图 -->
      <template v-else>
        <div v-if="plans.length === 0" class="empty-state-large">
          <div class="empty-img">
            <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
          </div>
          <h3>{{ monthDisplay }} 还没有计划</h3>
          <p class="empty-tips">添加一条内容计划，开始规划你的发布节奏</p>
          <button type="button" class="btn btn-primary" style="margin-top: 16px;" @click="openCreateModal()">立即添加</button>
        </div>

        <div v-else class="plan-list">
          <div v-for="plan in plans" :key="plan.id" class="card plan-row">
            <div class="plan-row-date">
              <span class="date-day">{{ plan.publish_date.slice(8, 10) }}</span>
              <span class="date-month">{{ plan.publish_date.slice(0, 7) }}</span>
            </div>

            <div class="plan-row-main">
              <div class="plan-row-title">{{ plan.title }}</div>
              <div class="plan-row-meta">
                <span class="platform-tag">
                  <span class="chip-dot" :style="{ background: platformColor(plan.platform) }"></span>
                  {{ platformLabel(plan.platform) }}
                </span>
                <span v-if="plan.notes" class="plan-notes" :title="plan.notes">{{ plan.notes }}</span>
              </div>
            </div>

            <div class="plan-row-actions">
              <select
                class="input select-mini status-select"
                :class="`chip-${plan.status}`"
                :value="plan.status"
                :disabled="statusUpdatingId === plan.id"
                aria-label="流转状态"
                @change="handleStatusChange(plan, ($event.target as HTMLSelectElement).value as PlanStatus)"
              >
                <option v-for="s in STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
              <button type="button" class="btn btn-mini btn-create" :aria-label="`用「${plan.title}」开始创作`" @click="startCreation(plan)">
                <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
                开始创作
              </button>
              <button type="button" class="btn btn-mini" :aria-label="`编辑「${plan.title}」`" @click="openEditModal(plan)">编辑</button>
              <button type="button" class="btn btn-mini btn-danger" :aria-label="`删除「${plan.title}」`" @click="deleteTarget = plan">删除</button>
            </div>
          </div>
        </div>
      </template>
    </template>

    <!-- 新建/编辑弹窗 -->
    <Teleport to="body">
      <div v-if="showModal" class="plan-modal-overlay" @click.self="closeModal">
        <div class="plan-modal" role="dialog" aria-modal="true" :aria-label="editingPlan ? '编辑内容计划' : '新建内容计划'">
          <div class="plan-modal-head">
            <h3>{{ editingPlan ? '编辑内容计划' : '新建内容计划' }}</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeModal">×</button>
          </div>

          <div class="plan-modal-body">
            <div class="form-field">
              <label>计划标题 <span class="required">*</span></label>
              <input v-model="form.title" class="input" type="text" placeholder="如：夏日防晒好物合集" maxlength="100" />
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>发布平台</label>
                <select v-model="form.platform" class="input">
                  <option v-for="p in PLATFORM_OPTIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div class="form-field">
                <label>计划发布日期 <span class="required">*</span></label>
                <input v-model="form.publish_date" class="input" type="date" />
              </div>
            </div>

            <div class="form-field">
              <label>状态</label>
              <div class="status-radio-group" role="radiogroup" aria-label="计划状态">
                <button
                  v-for="s in STATUS_OPTIONS"
                  :key="s.value"
                  type="button"
                  class="status-radio"
                  :class="[{ selected: form.status === s.value }, `chip-${s.value}`]"
                  role="radio"
                  :aria-checked="form.status === s.value"
                  @click="form.status = s.value"
                >{{ s.label }}</button>
              </div>
            </div>

            <div class="form-field">
              <label>备注</label>
              <textarea v-model="form.notes" class="input" rows="3" placeholder="选题思路、素材链接、注意事项等"></textarea>
            </div>

            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
          </div>

          <div class="plan-modal-foot">
            <button
              v-if="editingPlan"
              type="button"
              class="btn btn-create modal-create-btn"
              @click="startCreation(editingPlan)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="5 3 19 12 5 21 5 3"></polygon></svg>
              开始创作
            </button>
            <button type="button" class="btn" @click="closeModal">取消</button>
            <button type="button" class="btn btn-primary" :disabled="saving || !canSave" @click="handleSave">
              {{ saving ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 删除确认弹窗 -->
    <ConfirmDialog
      :visible="!!deleteTarget"
      title="删除这条内容计划？"
      :message="deleteMessage"
      confirm-text="删除"
      danger
      @confirm="doDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import {
  createPlan,
  deletePlan,
  getPlanList,
  getPlanStats,
  updatePlan,
  type PlanItem,
  type PlanPlatform,
  type PlanStats,
  type PlanStatus
} from '../api/calendar'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 内容日历（发布计划）页面
 *
 * 功能：
 * - 月历 / 列表两种视图，按月切换
 * - 计划条目的新建 / 编辑 / 删除（删除二次确认）
 * - 状态流转（想法 → 制作中 → 待发布 → 已发布）
 * - 按平台 / 状态筛选
 * - 本月统计（计划总数 + 各状态数量）
 */

const PLATFORM_OPTIONS: Array<{ value: PlanPlatform; label: string; color: string }> = [
  { value: 'xiaohongshu', label: '小红书', color: '#ff2442' },
  { value: 'douyin', label: '抖音', color: '#170b1a' },
  { value: 'gongzhonghao', label: '公众号', color: '#07c160' },
  { value: 'bilibili', label: 'B站', color: '#fb7299' },
  { value: 'shipinhao', label: '视频号', color: '#fa9d3b' }
]

const STATUS_OPTIONS: Array<{ value: PlanStatus; label: string }> = [
  { value: 'idea', label: '想法' },
  { value: 'in_progress', label: '制作中' },
  { value: 'ready', label: '待发布' },
  { value: 'published', label: '已发布' }
]

const WEEKDAYS = ['一', '二', '三', '四', '五', '六', '日']

const router = useRouter()
const generatorStore = useGeneratorStore()

function platformLabel(value: PlanPlatform): string {
  return PLATFORM_OPTIONS.find(p => p.value === value)?.label || value
}

function platformColor(value: PlanPlatform): string {
  return PLATFORM_OPTIONS.find(p => p.value === value)?.color || 'var(--border-hover, #ccc)'
}

function statusLabel(value: PlanStatus): string {
  return STATUS_OPTIONS.find(s => s.value === value)?.label || value
}

/** 本地时区的 YYYY-MM-DD（避免 toISOString 的 UTC 偏移） */
function toDateStr(d: Date): string {
  const y = d.getFullYear()
  const m = String(d.getMonth() + 1).padStart(2, '0')
  const day = String(d.getDate()).padStart(2, '0')
  return `${y}-${m}-${day}`
}

const todayDate = toDateStr(new Date())
const todayMonth = todayDate.slice(0, 7)

// 列表 / 视图状态
const plans = ref<PlanItem[]>([])
const stats = ref<PlanStats | null>(null)
const loading = ref(false)
const error = ref<AppError | null>(null)
const successMessage = ref('')
const viewMode = ref<'month' | 'list'>('month')

// 当前月份与筛选
const currentMonth = ref(todayMonth)
const filterPlatform = ref<'' | PlanPlatform>('')
const filterStatus = ref<'' | PlanStatus>('')

// 状态流转中的条目 ID
const statusUpdatingId = ref<string | null>(null)

// 弹窗表单状态
const showModal = ref(false)
const editingPlan = ref<PlanItem | null>(null)
const saving = ref(false)
const formError = ref('')

const form = reactive<{
  title: string
  platform: PlanPlatform
  publish_date: string
  status: PlanStatus
  notes: string
}>({
  title: '',
  platform: 'xiaohongshu',
  publish_date: todayDate,
  status: 'idea',
  notes: ''
})

/** 必填项（标题、发布日期）非空才允许保存 */
const canSave = computed(() => form.title.trim().length > 0 && !!form.publish_date)

// 删除确认状态
const deleteTarget = ref<PlanItem | null>(null)

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  return `「${deleteTarget.value.title}」（${deleteTarget.value.publish_date}）删除后无法恢复。`
})

const monthDisplay = computed(() => {
  const [y, m] = currentMonth.value.split('-')
  return `${y} 年 ${Number(m)} 月`
})

/** 按日期分组，供月历视图渲染 */
const plansByDate = computed(() => {
  const map: Record<string, PlanItem[]> = {}
  for (const plan of plans.value) {
    if (!map[plan.publish_date]) map[plan.publish_date] = []
    map[plan.publish_date].push(plan)
  }
  return map
})

interface CalendarCell {
  key: string
  date: string
  day: number
  inMonth: boolean
}

/** 月历格子（周一开始，含前后月补位） */
const calendarCells = computed<CalendarCell[]>(() => {
  const [year, month] = currentMonth.value.split('-').map(Number)
  const first = new Date(year, month - 1, 1)
  // getDay(): 周日=0，转换为周一=0 的偏移
  const leading = (first.getDay() + 6) % 7
  const start = new Date(year, month - 1, 1 - leading)

  const cells: CalendarCell[] = []
  const total = Math.ceil((leading + new Date(year, month, 0).getDate()) / 7) * 7
  for (let i = 0; i < total; i++) {
    const d = new Date(start.getFullYear(), start.getMonth(), start.getDate() + i)
    const date = toDateStr(d)
    cells.push({
      key: date,
      date,
      day: d.getDate(),
      inMonth: d.getMonth() === month - 1
    })
  }
  return cells
})

/**
 * 加载计划列表与统计
 */
async function loadData() {
  loading.value = true
  error.value = null

  const [listRes, statsRes] = await Promise.all([
    getPlanList({
      month: currentMonth.value,
      platform: filterPlatform.value || undefined,
      status: filterStatus.value || undefined
    }),
    getPlanStats(currentMonth.value)
  ])

  if (listRes.success) {
    plans.value = listRes.plans
  } else {
    error.value = normalizeApiError(listRes.error || listRes.error_message || '获取内容计划列表失败', '获取内容计划列表失败')
  }

  if (statsRes.success && statsRes.stats) {
    stats.value = statsRes.stats
  }

  loading.value = false
}

function handleRetry() {
  error.value = null
  loadData()
}

/**
 * 月份切换
 */
function shiftMonth(delta: number) {
  const [y, m] = currentMonth.value.split('-').map(Number)
  const d = new Date(y, m - 1 + delta, 1)
  currentMonth.value = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}`
}

function goToday() {
  currentMonth.value = todayMonth
}

/**
 * 打开新建弹窗（可预填日期，月历点击日期时使用）
 */
function openCreateModal(date?: string) {
  editingPlan.value = null
  form.title = ''
  form.platform = 'xiaohongshu'
  form.publish_date = date || (currentMonth.value === todayMonth ? todayDate : `${currentMonth.value}-01`)
  form.status = 'idea'
  form.notes = ''
  formError.value = ''
  showModal.value = true
}

/**
 * 打开编辑弹窗
 */
function openEditModal(plan: PlanItem) {
  editingPlan.value = plan
  form.title = plan.title
  form.platform = plan.platform
  form.publish_date = plan.publish_date
  form.status = plan.status
  form.notes = plan.notes
  formError.value = ''
  showModal.value = true
}

function closeModal() {
  showModal.value = false
}

/**
 * 保存（新建或更新）
 */
async function handleSave() {
  if (saving.value) return
  if (!form.title.trim()) {
    formError.value = '请填写计划标题'
    return
  }
  if (!form.publish_date) {
    formError.value = '请选择计划发布日期'
    return
  }

  saving.value = true
  formError.value = ''

  const payload = {
    title: form.title.trim(),
    platform: form.platform,
    publish_date: form.publish_date,
    status: form.status,
    notes: form.notes.trim()
  }

  const res = editingPlan.value
    ? await updatePlan(editingPlan.value.id, payload)
    : await createPlan(payload)

  saving.value = false

  if (res.success) {
    successMessage.value = editingPlan.value ? '计划已更新' : '计划已添加'
    showModal.value = false
    await loadData()
  } else {
    formError.value = res.error_message || '保存失败，请重试'
  }
}

/**
 * 状态流转（列表视图内联下拉）
 */
async function handleStatusChange(plan: PlanItem, status: PlanStatus) {
  if (status === plan.status || statusUpdatingId.value) return
  statusUpdatingId.value = plan.id
  const res = await updatePlan(plan.id, { status })
  statusUpdatingId.value = null

  if (res.success) {
    successMessage.value = `「${plan.title}」已流转为「${statusLabel(status)}」`
    await loadData()
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '更新计划状态失败', '更新计划状态失败')
    await loadData()
  }
}

/**
 * 从计划直接进入创作流程：
 * 把计划标题写入 generator store 作为主题并跳转到创作起点（首页）。
 * 若计划处于 idea/ready 状态，顺带流转为 in_progress（尽力而为，失败不阻塞跳转）。
 */
function startCreation(plan: PlanItem) {
  generatorStore.setTopic(plan.title)

  if (plan.status === 'idea' || plan.status === 'ready') {
    // 不 await：状态流转失败不影响进入创作
    updatePlan(plan.id, { status: 'in_progress' }).catch(() => {})
  }

  router.push({ name: 'home' })
}

/**
 * 执行删除
 */
async function doDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  deleteTarget.value = null

  const res = await deletePlan(target.id)
  if (res.success) {
    successMessage.value = `已删除「${target.title}」`
    await loadData()
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '删除内容计划失败', '删除内容计划失败')
  }
}

watch([currentMonth, filterPlatform, filterStatus], () => {
  loadData()
})

onMounted(() => {
  loadData()
})
</script>

<style scoped>
/* 成功提示 */
.success-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  margin-bottom: 16px;
  padding: 12px 14px;
  border: 1px solid var(--color-success-soft);
  background: var(--color-success-soft);
  color: var(--color-success);
  border-radius: 8px;
  font-size: 14px;
}

.success-card button {
  border: none;
  background: transparent;
  color: var(--color-success);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
}

/* 统计卡片 */
.stats-row {
  display: grid;
  grid-template-columns: repeat(5, 1fr);
  gap: 12px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  padding: 14px 8px;
  border: 1px solid var(--border-color, #eee);
  border-radius: 12px;
  background: white;
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary, #999);
}

.stat-idea .stat-num { color: var(--color-info); }
.stat-in_progress .stat-num { color: var(--color-warning); }
.stat-ready .stat-num { color: var(--primary); }
.stat-published .stat-num { color: var(--color-success); }

/* 工具栏 */
.toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  margin-bottom: 16px;
}

.month-nav {
  display: flex;
  align-items: center;
  gap: 8px;
}

.month-text {
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
  min-width: 100px;
  text-align: center;
}

.toolbar-right {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.select-mini {
  width: auto;
  padding: 6px 10px;
  font-size: 13px;
}

.view-toggle {
  display: flex;
  border: 1px solid var(--border-color, #eee);
  border-radius: 8px;
  overflow: hidden;
}

.view-toggle-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: none;
  background: white;
  color: var(--text-sub, #666);
  cursor: pointer;
}

.view-toggle-btn.active {
  background: var(--primary);
  color: white;
  font-weight: 600;
}

/* 加载 / 空状态 */
.loading-state {
  display: flex;
  justify-content: center;
  padding: 80px 0;
}

.empty-state-large {
  text-align: center;
  padding: 80px 0;
  color: var(--text-sub);
}

.empty-img {
  opacity: 0.5;
  margin-bottom: 12px;
}

.empty-tips {
  margin-top: 10px;
  color: var(--text-placeholder);
}

/* 月历视图 */
.calendar-wrap {
  padding: 16px;
  margin-bottom: 40px;
}

.calendar-grid {
  display: grid;
  grid-template-columns: repeat(7, 1fr);
  gap: 4px;
}

.calendar-head {
  margin-bottom: 4px;
}

.weekday-cell {
  text-align: center;
  font-size: 12px;
  font-weight: 600;
  color: var(--text-secondary, #999);
  padding: 6px 0;
}

.day-cell {
  min-height: 88px;
  border: 1px solid var(--border-color, #f0f0f0);
  border-radius: 8px;
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: border-color 0.15s;
}

.day-cell:hover {
  border-color: var(--border-hover, #d0d0d0);
}

.day-cell.other-month {
  opacity: 0.35;
  cursor: default;
}

.day-cell.today {
  border-color: var(--primary);
  background: var(--primary-light);
}

.day-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub, #666);
}

.day-cell.today .day-num {
  color: var(--primary);
}

.day-plans {
  display: flex;
  flex-direction: column;
  gap: 3px;
  overflow: hidden;
}

.plan-chip {
  display: flex;
  align-items: center;
  gap: 4px;
  width: 100%;
  padding: 2px 6px;
  border: none;
  border-radius: 5px;
  font-size: 12px;
  line-height: 1.5;
  text-align: left;
  cursor: pointer;
  background: var(--color-info-soft);
  color: var(--color-info);
}

.plan-chip:hover {
  filter: brightness(0.96);
}

.chip-dot {
  width: 7px;
  height: 7px;
  border-radius: 50%;
  flex-shrink: 0;
}

.chip-title {
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

/* 状态语义色（chip 与下拉、状态单选共用） */
.chip-idea { background: var(--color-info-soft); color: var(--color-info); }
.chip-in_progress { background: var(--color-warning-soft); color: var(--color-warning); }
.chip-ready { background: var(--primary-light); color: var(--primary); }
.chip-published { background: var(--color-success-soft); color: var(--color-success); }

.calendar-hint {
  margin: 12px 0 0;
  font-size: 12px;
  color: var(--text-placeholder, #bbb);
  text-align: center;
}

/* 列表视图 */
.plan-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
  margin-bottom: 40px;
}

.plan-row {
  display: flex;
  align-items: center;
  gap: 16px;
  padding: 14px 18px;
}

.plan-row-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  min-width: 64px;
  padding: 6px 8px;
  border-radius: 10px;
  background: var(--bg-soft, #fafafa);
  border: 1px solid var(--border-color, #f0f0f0);
}

.date-day {
  font-size: 20px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
  line-height: 1.2;
}

.date-month {
  font-size: 11px;
  color: var(--text-secondary, #999);
}

.plan-row-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.plan-row-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main, #1a1a1a);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-row-meta {
  display: flex;
  align-items: center;
  gap: 10px;
  min-width: 0;
}

.platform-tag {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-sub, #666);
  padding: 2px 8px;
  border-radius: 100px;
  border: 1px solid var(--border-color, #eee);
}

.plan-notes {
  font-size: 12px;
  color: var(--text-secondary, #999);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.plan-row-actions {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-shrink: 0;
}

.status-select {
  border: none;
  border-radius: 100px;
  font-weight: 600;
  padding: 5px 10px;
  cursor: pointer;
}

.btn-mini {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-color, #eee);
  background: white;
  cursor: pointer;
  border-radius: 8px;
}

.btn-mini:hover {
  border-color: var(--border-hover, #e0e0e0);
}

.btn-mini.btn-danger {
  color: var(--color-danger);
}

.btn-mini.btn-danger:hover {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

/* 「开始创作」按钮：主色描边，强调从计划进入创作的入口 */
.btn-create {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  border-color: var(--primary) !important;
}

.btn-create:hover {
  background: var(--primary-light);
}

/* 弹窗内的「开始创作」靠左，与取消/保存分组区分 */
.modal-create-btn {
  margin-right: auto;
  border: 1px solid var(--primary);
}

/* 新建/编辑弹窗 */
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
  max-width: 520px;
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

.plan-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color, #eee);
  margin-top: 8px;
}

.plan-modal-foot .btn {
  border: 1px solid var(--border-color, #eee);
}

.plan-modal-foot .btn-primary {
  border: none;
}

/* 表单 */
.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main, #333);
}

.form-field .required {
  color: var(--color-danger);
}

.form-field textarea.input {
  resize: vertical;
  min-height: 60px;
  line-height: 1.5;
}

.form-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
}

.status-radio-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-radio {
  padding: 6px 14px;
  border: 1px solid transparent;
  border-radius: 100px;
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity 0.15s, box-shadow 0.15s;
}

.status-radio.selected {
  opacity: 1;
  box-shadow: 0 0 0 2px currentColor inset;
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .stats-row {
    grid-template-columns: repeat(5, 1fr);
    gap: 6px;
  }

  .stat-card {
    padding: 10px 4px;
  }

  .stat-num {
    font-size: 17px;
  }

  .toolbar {
    flex-direction: column;
    align-items: stretch;
  }

  .month-nav {
    justify-content: center;
  }

  .toolbar-right {
    justify-content: center;
  }

  .calendar-wrap {
    padding: 10px;
  }

  .day-cell {
    min-height: 62px;
    padding: 4px;
  }

  .plan-chip .chip-title {
    display: none;
  }

  .plan-chip {
    justify-content: center;
    padding: 2px 0;
  }

  .plan-row {
    flex-wrap: wrap;
    gap: 10px;
  }

  .plan-row-main {
    flex-basis: calc(100% - 80px);
  }

  .plan-row-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .form-grid {
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
