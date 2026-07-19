<template>
  <div class="container" style="max-width: 1000px;">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">数据复盘</h1>
        <p class="page-subtitle">手动录入已发布内容的表现数据，用数据找到下一个爆款方向</p>
      </div>
      <button type="button" class="btn btn-primary" @click="openCreateModal">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        录入数据
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

    <!-- 加载中 -->
    <div v-if="loading" class="loading-state">
      <div class="spinner"></div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
      </div>
      <h3>还没有表现数据</h3>
      <p class="empty-tips">把已发布内容的曝光、点赞等数据录进来，就能看到统计和 AI 复盘建议</p>
      <button type="button" class="btn btn-primary" style="margin-top: 16px;" @click="openCreateModal">立即录入</button>
    </div>

    <template v-else>
      <!-- 统计卡片 -->
      <div v-if="stats" class="stats-grid">
        <div class="card stat-card">
          <span class="stat-label">内容总数</span>
          <span class="stat-value">{{ stats.total_records }}</span>
        </div>
        <div class="card stat-card">
          <span class="stat-label">总曝光 / 播放</span>
          <span class="stat-value">{{ formatNumber(stats.total_views) }}</span>
        </div>
        <div class="card stat-card">
          <span class="stat-label">平均互动率</span>
          <span class="stat-value">{{ stats.avg_engagement_rate }}%</span>
        </div>
        <div class="card stat-card">
          <span class="stat-label">累计涨粉</span>
          <span class="stat-value">{{ formatNumber(stats.total_followers_gained) }}</span>
        </div>
      </div>

      <!-- 平台汇总 + 趋势 -->
      <div v-if="stats" class="panel-grid">
        <div class="card panel">
          <h3 class="panel-title">各平台表现</h3>
          <div v-if="stats.platforms.length === 0" class="panel-empty">暂无数据</div>
          <div v-for="p in stats.platforms" :key="p.name" class="summary-row">
            <span class="summary-name">{{ p.name }}</span>
            <span class="summary-meta">{{ p.count }} 条 · 曝光 {{ formatNumber(p.views) }} · 互动率 {{ p.engagement_rate }}%</span>
          </div>

          <h3 class="panel-title" style="margin-top: 18px;">各内容类型表现</h3>
          <div v-if="stats.content_types.length === 0" class="panel-empty">暂无数据</div>
          <div v-for="c in stats.content_types" :key="c.name" class="summary-row">
            <span class="summary-name">{{ c.name }}</span>
            <span class="summary-meta">{{ c.count }} 条 · 曝光 {{ formatNumber(c.views) }} · 互动率 {{ c.engagement_rate }}%</span>
          </div>
        </div>

        <div class="card panel">
          <h3 class="panel-title">按月趋势（曝光）</h3>
          <div v-if="stats.trend.length === 0" class="panel-empty">记录中填写发布日期后即可查看趋势</div>
          <div v-else class="trend-list">
            <div v-for="t in stats.trend" :key="t.month" class="trend-row">
              <span class="trend-month">{{ t.month }}</span>
              <div class="trend-bar-track">
                <div class="trend-bar" :style="{ width: trendBarWidth(t.views) }"></div>
              </div>
              <span class="trend-value">{{ formatNumber(t.views) }}</span>
            </div>
          </div>
        </div>
      </div>

      <!-- AI 复盘洞察 -->
      <div class="card insight-panel">
        <div class="insight-head">
          <div>
            <h3 class="panel-title" style="margin-bottom: 4px;">AI 复盘洞察</h3>
            <p class="insight-subtitle">把你的数据摘要发给 AI，分析哪类内容 / 标题 / 平台表现更好</p>
          </div>
          <button type="button" class="btn btn-primary" :disabled="insightLoading" @click="handleInsight">
            {{ insightLoading ? '分析中...' : insight ? '重新分析' : '生成 AI 复盘' }}
          </button>
        </div>

        <div v-if="insightLoading" class="insight-loading">
          <div class="spinner"></div>
          <span>AI 正在复盘你的数据，通常需要 10~30 秒...</span>
        </div>

        <div v-else-if="insight" class="insight-body">
          <p v-if="insight.summary" class="insight-summary">{{ insight.summary }}</p>

          <template v-if="insight.highlights.length">
            <h4 class="insight-section-title">复盘洞察</h4>
            <ul class="insight-list">
              <li v-for="(item, i) in insight.highlights" :key="'h' + i">{{ item }}</li>
            </ul>
          </template>

          <template v-if="insight.suggestions.length">
            <h4 class="insight-section-title">下一步建议</h4>
            <ol class="insight-list">
              <li v-for="(item, i) in insight.suggestions" :key="'s' + i">{{ item }}</li>
            </ol>
          </template>
        </div>
      </div>

      <!-- 记录列表 -->
      <div class="card records-panel">
        <h3 class="panel-title">全部记录（{{ records.length }}）</h3>
        <div class="records-table-wrap">
          <table class="records-table">
            <thead>
              <tr>
                <th>标题</th>
                <th>平台</th>
                <th>类型</th>
                <th>发布日期</th>
                <th class="num">曝光</th>
                <th class="num">点赞</th>
                <th class="num">收藏</th>
                <th class="num">评论</th>
                <th class="num">转发</th>
                <th class="num">涨粉</th>
                <th class="num">互动率</th>
                <th>操作</th>
              </tr>
            </thead>
            <tbody>
              <tr v-for="record in records" :key="record.id">
                <td class="title-cell" :title="record.title">{{ record.title }}</td>
                <td><span class="platform-tag">{{ record.platform }}</span></td>
                <td>{{ record.content_type || '—' }}</td>
                <td>{{ record.publish_date || '—' }}</td>
                <td class="num">{{ formatNumber(record.views) }}</td>
                <td class="num">{{ formatNumber(record.likes) }}</td>
                <td class="num">{{ formatNumber(record.collects) }}</td>
                <td class="num">{{ formatNumber(record.comments) }}</td>
                <td class="num">{{ formatNumber(record.shares) }}</td>
                <td class="num">{{ formatNumber(record.followers_gained) }}</td>
                <td class="num">{{ engagementRateText(record) }}</td>
                <td class="actions-cell">
                  <button type="button" class="btn btn-mini" :aria-label="`编辑「${record.title}」`" @click="openEditModal(record)">编辑</button>
                  <button type="button" class="btn btn-mini btn-danger" :aria-label="`删除「${record.title}」`" @click="deleteTarget = record">删除</button>
                </td>
              </tr>
            </tbody>
          </table>
        </div>
      </div>
    </template>

    <!-- 录入/编辑弹窗 -->
    <Teleport to="body">
      <div v-if="showModal" class="analytics-modal-overlay" @click.self="closeModal">
        <div class="analytics-modal" role="dialog" aria-modal="true" :aria-label="editingRecord ? '编辑表现数据' : '录入表现数据'">
          <div class="analytics-modal-head">
            <h3>{{ editingRecord ? '编辑表现数据' : '录入表现数据' }}</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeModal">×</button>
          </div>

          <div class="analytics-modal-body">
            <div class="form-field">
              <label>内容标题 <span class="required">*</span></label>
              <input v-model="form.title" class="input" type="text" placeholder="如：3 个方法让敏感肌稳住不烂脸" maxlength="100" />
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>发布平台 <span class="required">*</span></label>
                <input v-model="form.platform" class="input" type="text" placeholder="如：小红书 / 抖音" maxlength="30" list="platform-presets" />
                <datalist id="platform-presets">
                  <option value="小红书"></option>
                  <option value="抖音"></option>
                  <option value="B站"></option>
                  <option value="视频号"></option>
                  <option value="快手"></option>
                  <option value="公众号"></option>
                </datalist>
              </div>
              <div class="form-field">
                <label>发布日期</label>
                <input v-model="form.publish_date" class="input" type="date" />
              </div>
            </div>

            <div class="form-field">
              <label>内容类型 / 标签</label>
              <input v-model="form.content_type" class="input" type="text" placeholder="如：干货教程 / 好物种草 / 日常vlog" maxlength="30" list="type-presets" />
              <datalist id="type-presets">
                <option value="干货教程"></option>
                <option value="好物种草"></option>
                <option value="测评对比"></option>
                <option value="日常vlog"></option>
                <option value="热点话题"></option>
              </datalist>
            </div>

            <div class="form-grid three">
              <div class="form-field">
                <label>曝光 / 播放</label>
                <input v-model.number="form.views" class="input" type="number" min="0" placeholder="0" />
              </div>
              <div class="form-field">
                <label>点赞</label>
                <input v-model.number="form.likes" class="input" type="number" min="0" placeholder="0" />
              </div>
              <div class="form-field">
                <label>收藏</label>
                <input v-model.number="form.collects" class="input" type="number" min="0" placeholder="0" />
              </div>
              <div class="form-field">
                <label>评论</label>
                <input v-model.number="form.comments" class="input" type="number" min="0" placeholder="0" />
              </div>
              <div class="form-field">
                <label>转发</label>
                <input v-model.number="form.shares" class="input" type="number" min="0" placeholder="0" />
              </div>
              <div class="form-field">
                <label>涨粉</label>
                <input v-model.number="form.followers_gained" class="input" type="number" min="0" placeholder="0" />
              </div>
            </div>

            <div class="form-field">
              <label>备注</label>
              <textarea v-model="form.notes" class="input" rows="2" placeholder="其他想记录的信息（可选）"></textarea>
            </div>

            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
          </div>

          <div class="analytics-modal-foot">
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
      title="删除这条表现记录？"
      :message="deleteMessage"
      confirm-text="删除"
      danger
      @confirm="doDelete"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, reactive, ref } from 'vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import {
  createAnalyticsRecord,
  deleteAnalyticsRecord,
  generateAnalyticsInsight,
  getAnalyticsRecords,
  getAnalyticsStats,
  updateAnalyticsRecord,
  type AnalyticsInsight,
  type AnalyticsRecord,
  type AnalyticsStats
} from '../api/analytics'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 数据复盘（表现分析）页面
 *
 * 功能：
 * - 手动录入已发布内容的表现数据（CRUD）
 * - 统计概览：总数、各平台/各类型汇总、平均互动率、按月趋势
 * - 一键 AI 复盘洞察：哪类内容/标题/平台表现更好 + 下一步建议
 */

// 列表与统计状态
const records = ref<AnalyticsRecord[]>([])
const stats = ref<AnalyticsStats | null>(null)
const loading = ref(false)
const error = ref<AppError | null>(null)
const successMessage = ref('')

// AI 洞察状态
const insight = ref<AnalyticsInsight | null>(null)
const insightLoading = ref(false)

// 弹窗表单状态
const showModal = ref(false)
const editingRecord = ref<AnalyticsRecord | null>(null)
const saving = ref(false)
const formError = ref('')

const form = reactive({
  title: '',
  platform: '',
  publish_date: '',
  content_type: '',
  views: 0,
  likes: 0,
  collects: 0,
  comments: 0,
  shares: 0,
  followers_gained: 0,
  notes: ''
})

/** 必填项（标题、平台）非空才允许保存 */
const canSave = computed(() => form.title.trim().length > 0 && form.platform.trim().length > 0)

// 删除确认状态
const deleteTarget = ref<AnalyticsRecord | null>(null)

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  return `「${deleteTarget.value.title}」删除后无法恢复。`
})

const maxTrendViews = computed(() => {
  if (!stats.value || stats.value.trend.length === 0) return 0
  return Math.max(...stats.value.trend.map(t => t.views))
})

/** 数字千分位格式化 */
function formatNumber(value: number): string {
  return (value || 0).toLocaleString('zh-CN')
}

/** 单条记录的互动率文本 */
function engagementRateText(record: AnalyticsRecord): string {
  if (!record.views) return '—'
  const engagements = record.likes + record.collects + record.comments + record.shares
  return `${Math.round((engagements / record.views) * 10000) / 100}%`
}

/** 趋势条宽度（相对当月最大曝光） */
function trendBarWidth(views: number): string {
  if (!maxTrendViews.value) return '0%'
  return `${Math.max((views / maxTrendViews.value) * 100, 2)}%`
}

/** 数值输入归一化：空串/NaN/负数 -> 0 */
function toSafeInt(value: unknown): number {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) return 0
  return Math.floor(num)
}

/**
 * 加载记录列表和统计概览
 */
async function loadData() {
  loading.value = true
  error.value = null

  const [recordsRes, statsRes] = await Promise.all([
    getAnalyticsRecords(),
    getAnalyticsStats()
  ])

  if (recordsRes.success) {
    records.value = recordsRes.records
  } else {
    error.value = normalizeApiError(recordsRes.error || recordsRes.error_message || '获取表现记录失败', '获取表现记录失败')
  }

  if (statsRes.success && statsRes.stats) {
    stats.value = statsRes.stats
  } else if (!error.value) {
    error.value = normalizeApiError(statsRes.error || statsRes.error_message || '获取统计概览失败', '获取统计概览失败')
  }

  loading.value = false
}

/**
 * 错误重试
 */
function handleRetry() {
  error.value = null
  loadData()
}

/**
 * 打开录入弹窗
 */
function openCreateModal() {
  editingRecord.value = null
  form.title = ''
  form.platform = ''
  form.publish_date = ''
  form.content_type = ''
  form.views = 0
  form.likes = 0
  form.collects = 0
  form.comments = 0
  form.shares = 0
  form.followers_gained = 0
  form.notes = ''
  formError.value = ''
  showModal.value = true
}

/**
 * 打开编辑弹窗
 */
function openEditModal(record: AnalyticsRecord) {
  editingRecord.value = record
  form.title = record.title
  form.platform = record.platform
  form.publish_date = record.publish_date
  form.content_type = record.content_type
  form.views = record.views
  form.likes = record.likes
  form.collects = record.collects
  form.comments = record.comments
  form.shares = record.shares
  form.followers_gained = record.followers_gained
  form.notes = record.notes
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
    formError.value = '请填写内容标题'
    return
  }
  if (!form.platform.trim()) {
    formError.value = '请填写发布平台'
    return
  }

  saving.value = true
  formError.value = ''

  const payload = {
    title: form.title.trim(),
    platform: form.platform.trim(),
    publish_date: form.publish_date,
    content_type: form.content_type.trim(),
    views: toSafeInt(form.views),
    likes: toSafeInt(form.likes),
    collects: toSafeInt(form.collects),
    comments: toSafeInt(form.comments),
    shares: toSafeInt(form.shares),
    followers_gained: toSafeInt(form.followers_gained),
    notes: form.notes.trim()
  }

  const res = editingRecord.value
    ? await updateAnalyticsRecord(editingRecord.value.id, payload)
    : await createAnalyticsRecord(payload)

  saving.value = false

  if (res.success) {
    successMessage.value = editingRecord.value ? '记录已更新' : '记录已保存'
    showModal.value = false
    await loadData()
  } else {
    formError.value = res.error_message || '保存失败，请重试'
  }
}

/**
 * 执行删除
 */
async function doDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  deleteTarget.value = null

  const res = await deleteAnalyticsRecord(target.id)
  if (res.success) {
    successMessage.value = `已删除「${target.title}」`
    await loadData()
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '删除表现记录失败', '删除表现记录失败')
  }
}

/**
 * 生成 AI 复盘洞察
 */
async function handleInsight() {
  if (insightLoading.value) return
  insightLoading.value = true
  error.value = null

  const res = await generateAnalyticsInsight()
  insightLoading.value = false

  if (res.success && res.insight) {
    insight.value = res.insight
    successMessage.value = 'AI 复盘完成'
  } else {
    error.value = normalizeApiError(res.error || res.error_message || 'AI 复盘洞察失败', 'AI 复盘洞察失败')
  }
}

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

/* 统计卡片 */
.stats-grid {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 14px;
  margin-bottom: 16px;
}

.stat-card {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 16px 18px;
}

.stat-label {
  font-size: 13px;
  color: var(--text-secondary, #999);
}

.stat-value {
  font-size: 24px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

/* 汇总 / 趋势面板 */
.panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}

.panel {
  padding: 18px 20px;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

.panel-empty {
  font-size: 13px;
  color: var(--text-placeholder, #bbb);
  padding: 6px 0;
}

.summary-row {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 10px;
  padding: 6px 0;
  border-bottom: 1px dashed var(--border-color, #eee);
  font-size: 13px;
}

.summary-row:last-child {
  border-bottom: none;
}

.summary-name {
  font-weight: 600;
  color: var(--text-main, #333);
  flex-shrink: 0;
}

.summary-meta {
  color: var(--text-sub, #666);
  text-align: right;
}

/* 趋势条 */
.trend-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.trend-row {
  display: flex;
  align-items: center;
  gap: 10px;
  font-size: 13px;
}

.trend-month {
  flex-shrink: 0;
  width: 60px;
  color: var(--text-sub, #666);
}

.trend-bar-track {
  flex: 1;
  height: 10px;
  background: var(--bg-soft, #f5f5f5);
  border-radius: 100px;
  overflow: hidden;
}

.trend-bar {
  height: 100%;
  border-radius: 100px;
  background: var(--primary);
  transition: width 0.3s ease;
}

.trend-value {
  flex-shrink: 0;
  min-width: 56px;
  text-align: right;
  color: var(--text-main, #333);
  font-variant-numeric: tabular-nums;
}

/* AI 洞察面板 */
.insight-panel {
  padding: 18px 20px;
  margin-bottom: 16px;
}

.insight-head {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: 14px;
  flex-wrap: wrap;
}

.insight-subtitle {
  margin: 0;
  font-size: 13px;
  color: var(--text-sub, #666);
}

.insight-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 0 6px;
  font-size: 14px;
  color: var(--text-sub, #666);
}

.insight-body {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color, #eee);
}

.insight-summary {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-main, #333);
}

.insight-section-title {
  margin: 14px 0 8px;
  font-size: 14px;
  font-weight: 700;
  color: var(--text-main, #1a1a1a);
}

.insight-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-main, #333);
}

/* 记录列表 */
.records-panel {
  padding: 18px 20px;
  margin-bottom: 40px;
}

.records-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.records-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 860px;
}

.records-table th,
.records-table td {
  padding: 9px 10px;
  text-align: left;
  border-bottom: 1px solid var(--border-color, #eee);
  white-space: nowrap;
}

.records-table th {
  font-weight: 600;
  color: var(--text-secondary, #999);
  font-size: 12px;
}

.records-table td {
  color: var(--text-main, #333);
}

.records-table .num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.title-cell {
  max-width: 220px;
  overflow: hidden;
  text-overflow: ellipsis;
}

.platform-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: 100px;
  font-size: 12px;
  background: var(--primary-light);
  color: var(--primary);
}

.actions-cell {
  display: flex;
  gap: 6px;
}

.btn-mini {
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid var(--border-color, #eee);
  background: white;
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

/* 录入/编辑弹窗 */
.analytics-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.45);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
}

.analytics-modal {
  background: white;
  border-radius: 14px;
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: 0 20px 60px rgba(0, 0, 0, 0.2);
}

.analytics-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 12px;
}

.analytics-modal-head h3 {
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

.analytics-modal-body {
  padding: 8px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.analytics-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color, #eee);
  margin-top: 8px;
}

.analytics-modal-foot .btn {
  border: 1px solid var(--border-color, #eee);
}

.analytics-modal-foot .btn-primary {
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

.form-grid.three {
  grid-template-columns: repeat(3, 1fr);
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .stats-grid {
    grid-template-columns: repeat(2, 1fr);
    gap: 10px;
  }

  .stat-value {
    font-size: 20px;
  }

  .panel-grid {
    grid-template-columns: 1fr;
  }

  .insight-head {
    flex-direction: column;
    align-items: stretch;
  }

  .form-grid,
  .form-grid.three {
    grid-template-columns: 1fr 1fr;
  }

  .analytics-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .analytics-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: 14px 14px 0 0;
  }
}
</style>
