<template>
  <div class="container" style="max-width: 1000px;">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">数据复盘</h1>
        <p class="page-subtitle">手动录入已发布内容的表现数据，用数据找到下一个爆款方向</p>
      </div>
      <div class="page-actions">
        <button type="button" class="btn btn-import" @click="showOcrModal = true">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
          截图导入
        </button>
        <button type="button" class="btn btn-import" @click="openImportModal">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="7 10 12 15 17 10"></polyline><line x1="12" y1="15" x2="12" y2="3"></line></svg>
          批量导入
        </button>
        <button type="button" class="btn btn-primary" @click="openCreateModal">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          录入数据
        </button>
      </div>
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

    <!-- 加载中：轻量骨架占位 -->
    <div v-if="loading" aria-hidden="true">
      <div class="stats-grid">
        <div v-for="i in 4" :key="i" class="card stat-card skeleton-block">
          <span class="skeleton skeleton-line" style="width: 56%; height: 12px;"></span>
          <span class="skeleton skeleton-line" style="width: 40%; height: 24px;"></span>
        </div>
      </div>
      <div class="card records-panel skeleton-block">
        <span class="skeleton skeleton-line" style="width: 30%;"></span>
        <span v-for="i in 4" :key="i" class="skeleton skeleton-line" style="width: 100%;"></span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="records.length === 0" class="empty-state-large">
      <div class="empty-icon-wrap">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>
      </div>
      <h3 class="empty-title">还没有表现数据</h3>
      <p class="empty-tips">截图创作者后台数据页让 AI 自动识别，或手动录入曝光、点赞等数据，就能看到统计和 AI 复盘建议</p>
      <div class="empty-cta">
        <button type="button" class="btn btn-primary" @click="showOcrModal = true">截图导入</button>
        <button type="button" class="btn btn-import" @click="openCreateModal">手动录入</button>
        <button type="button" class="btn btn-import" @click="openImportModal">从表格批量导入</button>
      </div>
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
          <span class="stat-value">
            {{ stats.avg_engagement_rate }}%
            <BenchmarkDot
              :rating="metricRating('engagement_rate')?.rating"
              :tooltip="metricTooltip('engagement_rate')"
            />
          </span>
        </div>
        <div class="card stat-card">
          <span class="stat-label">累计涨粉</span>
          <span class="stat-value">{{ formatNumber(stats.total_followers_gained) }}</span>
        </div>
      </div>

      <!-- 行业基准对照（B10 红绿灯） -->
      <div v-if="benchmarkItems.length" class="card benchmark-strip">
        <div class="benchmark-items">
          <span
            v-for="item in benchmarkItems"
            :key="item.key"
            class="benchmark-item"
            :title="metricTooltip(item.key)"
          >
            <BenchmarkDot :rating="item.rating" :tooltip="metricTooltip(item.key)" />
            <span class="benchmark-item-label">{{ item.label }}</span>
            <span class="benchmark-item-value">{{ item.value === null ? '—' : `${item.value}%` }}</span>
            <span class="benchmark-item-target">基准 ≥{{ item.green_at }}%</span>
          </span>
        </div>
        <p class="benchmark-source">
          红 = 低于基准下限，黄 = 待提升，绿 = 达标；{{ stats?.benchmarks_meta?.source || '公开行业经验值，仅供参考' }}
        </p>
      </div>

      <!-- 平台/类型对比 + 趋势 + 发布时段 -->
      <div v-if="stats" class="panel-grid">
        <div class="card panel">
          <h3 class="panel-title">各平台表现（互动率）</h3>
          <div v-if="stats.platforms.length === 0" class="panel-empty">暂无数据</div>
          <CompareBarChart v-else :items="platformBars" rate-label="互动率" />

          <h3 class="panel-title" style="margin-top: 18px;">各内容类型表现（互动率）</h3>
          <div v-if="stats.content_types.length === 0" class="panel-empty">暂无数据</div>
          <CompareBarChart v-else :items="contentTypeBars" rate-label="互动率" />
        </div>

        <div class="card panel">
          <h3 class="panel-title">按月趋势（曝光 × 互动率）</h3>
          <div v-if="stats.trend.length === 0" class="panel-empty">记录中填写发布日期后即可查看趋势</div>
          <TrendLineChart v-else :points="stats.trend" />

          <h3 class="panel-title" style="margin-top: 18px;">最佳发布时段</h3>
          <div v-if="timeSlotBars.length === 0" class="panel-empty">记录中填写发布时间后即可查看时段分析</div>
          <template v-else>
            <CompareBarChart :items="timeSlotBars" rate-label="平均互动率" />
            <p v-if="bestTimeSlot" class="slot-conclusion">
              你的内容在【{{ bestTimeSlot.name }}】表现最好，平均互动率 {{ bestTimeSlot.avg_engagement }}%
            </p>
          </template>
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
            <!-- T14：每条建议可直接转成动作（生成选题 / 加入内容日历） -->
            <ol class="insight-list suggestion-list">
              <li v-for="(item, i) in insight.suggestions" :key="'s' + i">
                <div class="suggestion-row">
                  <span class="suggestion-text">{{ item }}</span>
                  <span class="suggestion-actions">
                    <button
                      type="button"
                      class="btn btn-mini btn-suggestion"
                      :aria-label="`以建议 ${i + 1} 为方向生成选题`"
                      title="把这条建议作为领域方向，跳转选题灵感工具"
                      @click="goTopicWithSuggestion(item)"
                    >生成选题</button>
                    <button
                      type="button"
                      class="btn btn-mini btn-suggestion"
                      :aria-label="`把建议 ${i + 1} 加入内容日历`"
                      title="把这条建议作为待办排进内容日历"
                      @click="calendarSuggestion = item"
                    >加入日历</button>
                  </span>
                </div>
              </li>
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
                <td class="title-cell" :title="record.title">
                  <span
                    v-if="record.calendar_plan_id || record.record_id"
                    class="linked-badge"
                    :title="record.calendar_plan_id ? '由内容日历转录，已关联日历条目' : '已关联历史作品'"
                  >
                    <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                    已关联
                  </span>
                  {{ record.title }}
                </td>
                <td><span class="platform-tag">{{ record.platform }}</span></td>
                <td>{{ record.content_type || '—' }}</td>
                <td>
                  {{ record.publish_date || '—' }}
                  <span v-if="record.publish_time" class="time-sub">{{ record.publish_time }}</span>
                </td>
                <td class="num">{{ formatNumber(record.views) }}</td>
                <td class="num">{{ formatNumber(record.likes) }}</td>
                <td class="num">{{ formatNumber(record.collects) }}</td>
                <td class="num">{{ formatNumber(record.comments) }}</td>
                <td class="num">{{ formatNumber(record.shares) }}</td>
                <td class="num">{{ formatNumber(record.followers_gained) }}</td>
                <td class="num rate-cell">
                  <BenchmarkDot
                    :rating="record.metrics?.engagement_rate?.rating"
                    :tooltip="metricTooltip('engagement_rate', record.metrics?.engagement_rate?.value)"
                  />
                  {{ engagementRateText(record) }}
                </td>
                <td class="actions-cell">
                  <button
                    v-if="record.record_id"
                    type="button"
                    class="btn btn-mini btn-view-work"
                    :aria-label="`查看「${record.title}」关联的作品`"
                    title="跳转到关联的历史作品详情"
                    @click="viewLinkedWork(record)"
                  >查看作品</button>
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

            <!-- U9：日期/时间并排两列，与下方曝光/点赞/收藏三列网格保持节奏 -->
            <div class="form-grid">
              <div class="form-field">
                <label>发布日期</label>
                <input v-model="form.publish_date" class="input" type="date" />
              </div>
              <div class="form-field">
                <label>发布时间</label>
                <input v-model="form.publish_time" class="input" type="time" />
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

    <!-- 批量导入弹窗 -->
    <Teleport to="body">
      <div v-if="showImportModal" class="analytics-modal-overlay" @click.self="closeImportModal">
        <div class="analytics-modal import-modal" role="dialog" aria-modal="true" aria-label="批量导入表现数据">
          <div class="analytics-modal-head">
            <h3>批量导入</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeImportModal">×</button>
          </div>

          <div class="analytics-modal-body">
            <!-- 导入结果 -->
            <template v-if="importResult">
              <div class="import-result" role="status">
                <p class="import-result-main">成功导入 {{ importResult.created }} 条记录</p>
                <template v-if="importResult.failed.length">
                  <p class="import-result-sub">以下 {{ importResult.failed.length }} 条被后端拒绝，未导入：</p>
                  <ul class="import-errors">
                    <li v-for="f in importResult.failed" :key="f.index">第 {{ f.index + 1 }} 条：{{ f.error }}</li>
                  </ul>
                </template>
              </div>
            </template>

            <!-- 粘贴 + 预览 -->
            <template v-else>
              <p class="import-hint">
                从 Excel / 创作者中心表格直接复制粘贴（制表符分隔），或粘贴 CSV 文本。首行为表头，
                支持：标题、平台、日期、发布时间、类型/标签、曝光/播放、点赞、收藏、评论、转发、涨粉。
              </p>
              <textarea
                v-model="importText"
                class="input import-textarea"
                rows="8"
                :placeholder="importPlaceholder"
                aria-label="粘贴表格内容"
              ></textarea>

              <template v-if="importText.trim()">
                <div class="import-summary">
                  <span>识别出 <strong>{{ importParse.records.length }}</strong> 条记录（{{ importParse.delimiter === 'tab' ? '制表符分隔' : 'CSV 逗号分隔' }}）</span>
                  <span v-if="importParse.errors.length" class="import-error-count">{{ importParse.errors.length }} 行无法解析</span>
                </div>

                <ul v-if="importParse.errors.length" class="import-errors">
                  <li v-for="err in importParse.errors" :key="err.line">第 {{ err.line }} 行：{{ err.reason }}</li>
                </ul>

                <div v-if="importParse.records.length" class="records-table-wrap import-preview-wrap">
                  <table class="records-table import-preview-table">
                    <thead>
                      <tr>
                        <th>标题</th>
                        <th>平台</th>
                        <th>日期</th>
                        <th>时间</th>
                        <th>类型</th>
                        <th class="num">曝光</th>
                        <th class="num">点赞</th>
                        <th class="num">收藏</th>
                        <th class="num">评论</th>
                        <th class="num">转发</th>
                        <th class="num">涨粉</th>
                      </tr>
                    </thead>
                    <tbody>
                      <tr v-for="(r, i) in importPreviewRows" :key="i">
                        <td class="title-cell" :title="r.title">{{ r.title }}</td>
                        <td>{{ r.platform }}</td>
                        <td>{{ r.publish_date || '—' }}</td>
                        <td>{{ r.publish_time || '—' }}</td>
                        <td>{{ r.content_type || '—' }}</td>
                        <td class="num">{{ formatNumber(r.views ?? 0) }}</td>
                        <td class="num">{{ formatNumber(r.likes ?? 0) }}</td>
                        <td class="num">{{ formatNumber(r.collects ?? 0) }}</td>
                        <td class="num">{{ formatNumber(r.comments ?? 0) }}</td>
                        <td class="num">{{ formatNumber(r.shares ?? 0) }}</td>
                        <td class="num">{{ formatNumber(r.followers_gained ?? 0) }}</td>
                      </tr>
                    </tbody>
                  </table>
                  <p v-if="importParse.records.length > 10" class="import-more">
                    仅预览前 10 条，实际将导入 {{ importParse.records.length }} 条
                  </p>
                </div>
              </template>

              <p v-if="importError" class="form-error" role="alert">{{ importError }}</p>
            </template>
          </div>

          <div class="analytics-modal-foot">
            <template v-if="importResult">
              <button type="button" class="btn btn-primary" @click="closeImportModal">完成</button>
            </template>
            <template v-else>
              <button type="button" class="btn" @click="closeImportModal">取消</button>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="importing || importParse.records.length === 0"
                @click="handleImport"
              >
                {{ importing ? '导入中...' : importParse.records.length > 0 ? `确认导入 ${importParse.records.length} 条` : '确认导入' }}
              </button>
            </template>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 截图导入弹窗（B3：上传/粘贴截图 → AI 识别 → 可编辑预览 → 批量入库） -->
    <OcrImportModal
      v-if="showOcrModal"
      @close="showOcrModal = false"
      @imported="onOcrImported"
    />

    <!-- 复盘建议加入日历弹窗（T14，复用通用加入日历弹窗，标题即建议文本） -->
    <AddToCalendarDialog
      v-if="suggestionCalendarIdea"
      :idea="suggestionCalendarIdea"
      @close="calendarSuggestion = ''"
      @added="onSuggestionCalendarAdded"
    />

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
import { useRouter } from 'vue-router'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import AddToCalendarDialog from '../components/common/AddToCalendarDialog.vue'
import CompareBarChart from '../components/analytics/CompareBarChart.vue'
import TrendLineChart from '../components/analytics/TrendLineChart.vue'
import BenchmarkDot from '../components/analytics/BenchmarkDot.vue'
import OcrImportModal from '../components/analytics/OcrImportModal.vue'
import {
  batchCreateAnalyticsRecords,
  createAnalyticsRecord,
  deleteAnalyticsRecord,
  generateAnalyticsInsight,
  getAnalyticsRecords,
  getAnalyticsStats,
  updateAnalyticsRecord,
  type AnalyticsBatchFailure,
  type AnalyticsInsight,
  type AnalyticsMetricRating,
  type AnalyticsRecord,
  type AnalyticsStats,
  type AnalyticsTimeSlot
} from '../api/analytics'
import { parseAnalyticsImport } from '../utils/analyticsImport'
import type { CalendarIdeaLike } from '../utils/ideaArchive'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 数据复盘（表现分析）页面
 *
 * 功能：
 * - 手动录入已发布内容的表现数据（CRUD）
 * - 截图导入：上传/粘贴创作者后台数据截图，AI 多模态识别后预览入库（B3）
 * - 批量导入：粘贴 Excel / CSV 表格文本，预览后一键入库
 * - 统计概览：总数、各平台/各类型对比（SVG 柱状图）、按月趋势（SVG 折线图）、最佳发布时段
 * - 行业基准红绿灯：互动率/点赞率/收藏率/评论率对照行业基准展示红黄绿评级（B10）
 * - 一键 AI 复盘洞察：哪类内容/标题/平台/时段表现更好 + 下一步建议
 * - 建议转动作：每条 AI 建议可一键「生成选题」或「加入日历」（T14）
 * - 关联展示：带 record_id 的记录可一键跳转到历史作品详情，带关联的行有小标识
 */

/**
 * 「生成选题」跳转预填的 sessionStorage 键（T14）。
 * 值为 JSON：{ niche: 建议文本, from: 'analytics' }。
 * 约定：选题工具页（/tools/topic，ToolTopicView）挂载时读取该键预填
 * 「领域/赛道」输入框，读取后应立即删除该键（读后即清，避免反复预填）。
 */
const TOPIC_NICHE_PREFILL_KEY = 'redink_topic_niche_prefill'

const router = useRouter()

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
  publish_time: '',
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

// 批量导入状态
const showImportModal = ref(false)
const importText = ref('')
const importing = ref(false)
const importError = ref('')
const importResult = ref<{ created: number; failed: AnalyticsBatchFailure[] } | null>(null)

// 截图导入弹窗（B3）
const showOcrModal = ref(false)

// T14：待加入日历的建议文本（非空时弹出加入日历弹窗）
const calendarSuggestion = ref('')

/** 建议文本 → 通用加入日历弹窗的选题结构（标题即建议文本） */
const suggestionCalendarIdea = computed<CalendarIdeaLike | null>(() =>
  calendarSuggestion.value
    ? { title: calendarSuggestion.value, angle: '', tags: [] }
    : null
)

/** 粘贴文本的实时解析结果（纯函数，见 utils/analyticsImport.ts） */
const importParse = computed(() => parseAnalyticsImport(importText.value))

/** 预览表格只显示前 10 行 */
const importPreviewRows = computed(() => importParse.value.records.slice(0, 10))

const importPlaceholder = [
  '标题\t平台\t日期\t发布时间\t类型\t曝光\t点赞\t收藏\t评论\t转发\t涨粉',
  '敏感肌自救指南\t小红书\t2026-07-01\t20:30\t干货教程\t1.2万\t1,024\t300\t56\t18\t120'
].join('\n')

// ==================== 图表数据 ====================

/** 各平台对比条目（互动率 + 篇数） */
const platformBars = computed(() =>
  (stats.value?.platforms ?? []).map(p => ({ name: p.name, count: p.count, rate: p.engagement_rate }))
)

/** 各内容类型对比条目 */
const contentTypeBars = computed(() =>
  (stats.value?.content_types ?? []).map(c => ({ name: c.name, count: c.count, rate: c.engagement_rate }))
)

/** 发布时段条目（按平均互动率倒序） */
const sortedTimeSlots = computed<AnalyticsTimeSlot[]>(() =>
  [...(stats.value?.time_slots ?? [])].sort((a, b) => b.avg_engagement - a.avg_engagement)
)

const timeSlotBars = computed(() =>
  sortedTimeSlots.value.map(s => ({ name: s.name, count: s.count, rate: s.avg_engagement }))
)

const bestTimeSlot = computed<AnalyticsTimeSlot | null>(() => sortedTimeSlots.value[0] ?? null)

// ==================== 行业基准红绿灯（B10） ====================

/** 基准对照条的展示顺序 */
const BENCHMARK_ORDER = ['engagement_rate', 'like_rate', 'collect_rate', 'comment_rate'] as const

/** 基准对照条目（旧后端无 metric_ratings 字段时为空，整块隐藏） */
const benchmarkItems = computed(() => {
  const ratings = stats.value?.metric_ratings
  if (!ratings) return []
  return BENCHMARK_ORDER.filter(key => ratings[key]).map(key => ({ key, ...ratings[key] }))
})

/** 取某个指标的汇总评级（含基准阈值与说明） */
function metricRating(key: string): AnalyticsMetricRating | null {
  return stats.value?.metric_ratings?.[key] ?? null
}

/**
 * 红绿灯 hover 的基准说明文案。
 * value 不传时用汇总值（指标卡）；传入时用单条记录的值（记录列表）。
 */
function metricTooltip(key: string, value?: number | null): string {
  const rule = metricRating(key)
  if (!rule) return ''
  const shown = value !== undefined ? value : rule.value
  const valueText = shown === null || shown === undefined ? '暂无曝光数据' : `${shown}%`
  const source = stats.value?.benchmarks_meta?.source || '公开行业经验值，仅供参考'
  return `${rule.label} ${valueText}｜达标线 ≥${rule.green_at}%，低于 ${rule.red_below}% 偏低。${rule.note}（${source}）`
}

// ==================== 建议转动作（T14） ====================

/**
 * 「生成选题」：把建议文本写入 sessionStorage 后跳转选题工具，
 * 由选题页挂载时读取 TOPIC_NICHE_PREFILL_KEY 预填领域输入（键约定见常量注释）。
 */
function goTopicWithSuggestion(suggestion: string) {
  try {
    sessionStorage.setItem(
      TOPIC_NICHE_PREFILL_KEY,
      // 选题页领域输入框上限 100 字，超长建议截断后传递
      JSON.stringify({ niche: suggestion.trim().slice(0, 100), from: 'analytics' })
    )
  } catch {
    // sessionStorage 不可用（隐私模式等）时放弃预填，仅跳转
  }
  router.push('/tools/topic')
}

/** 建议加入日历成功 */
function onSuggestionCalendarAdded() {
  calendarSuggestion.value = ''
  successMessage.value = '已把建议加入内容日历'
}

// ==================== 截图导入（B3） ====================

/** 截图导入成功入库后刷新列表与统计 */
async function onOcrImported(created: number) {
  successMessage.value = `截图导入完成：成功 ${created} 条`
  await loadData()
}

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

/** 跳转到记录关联的历史作品详情 */
function viewLinkedWork(record: AnalyticsRecord) {
  if (!record.record_id) return
  router.push({ name: 'history-detail', params: { id: record.record_id } })
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
  form.publish_time = ''
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
  form.publish_time = record.publish_time || ''
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
    publish_time: form.publish_time,
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
 * 打开批量导入弹窗
 */
function openImportModal() {
  importText.value = ''
  importError.value = ''
  importResult.value = null
  showImportModal.value = true
}

function closeImportModal() {
  showImportModal.value = false
}

/**
 * 确认批量导入：把解析出的记录提交批量接口，展示成功/失败结果
 */
async function handleImport() {
  if (importing.value) return
  const parsedRecords = importParse.value.records
  if (parsedRecords.length === 0) return
  if (parsedRecords.length > 200) {
    importError.value = `一次最多导入 200 条（当前 ${parsedRecords.length} 条），请分批粘贴`
    return
  }

  importing.value = true
  importError.value = ''

  const res = await batchCreateAnalyticsRecords(parsedRecords)
  importing.value = false

  if (res.success) {
    importResult.value = { created: res.created ?? 0, failed: res.failed ?? [] }
    successMessage.value = `批量导入完成：成功 ${res.created ?? 0} 条`
    await loadData()
  } else {
    importError.value = res.error_message || '批量导入失败，请重试'
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
  border-radius: var(--radius-sm);
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

/* 加载骨架 */
.skeleton-block {
  pointer-events: none;
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.skeleton {
  display: block;
  background: var(--gray-2);
  border-radius: var(--radius-xs);
  animation: skeleton-pulse 1.4s var(--ease-out) infinite;
}

.skeleton-line {
  height: 13px;
}

@keyframes skeleton-pulse {
  0%, 100% { opacity: 1; }
  50% { opacity: 0.55; }
}

@media (prefers-reduced-motion: reduce) {
  .skeleton {
    animation: none;
  }
}

/* 空状态 */
.empty-state-large {
  text-align: center;
  padding: var(--space-8) var(--space-5);
  color: var(--text-sub);
}

.empty-icon-wrap {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 72px;
  height: 72px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  color: var(--gray-6);
  margin-bottom: var(--space-4);
}

.empty-title {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.empty-tips {
  margin-top: var(--space-2);
  color: var(--text-secondary);
  font-size: 14px;
}

.empty-cta {
  margin-top: var(--space-5);
  display: flex;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

/* 页头操作区 */
.page-actions {
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

/* 次级按钮（批量导入） */
.btn-import {
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
}

.btn-import:hover {
  border-color: var(--border-hover);
  background: var(--gray-0);
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
  padding: 18px 20px;
  margin-bottom: 0;
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--border-hover);
}

.stat-label {
  font-size: 12px;
  font-weight: 500;
  color: var(--text-secondary);
}

.stat-value {
  font-size: 28px;
  font-weight: 700;
  letter-spacing: var(--tracking-tighter);
  color: var(--text-main);
  font-variant-numeric: tabular-nums;
  line-height: 1.15;
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

/* 行业基准对照条（B10 红绿灯） */
.benchmark-strip {
  display: flex;
  flex-direction: column;
  gap: 8px;
  padding: 12px 20px;
  margin-bottom: 16px;
}

.benchmark-items {
  display: flex;
  gap: 8px 22px;
  flex-wrap: wrap;
}

.benchmark-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  font-size: 13px;
  cursor: help;
}

.benchmark-item-label {
  color: var(--text-secondary);
}

.benchmark-item-value {
  font-weight: 700;
  color: var(--text-main);
  font-variant-numeric: tabular-nums;
}

.benchmark-item-target {
  font-size: 12px;
  color: var(--text-placeholder);
}

.benchmark-source {
  margin: 0;
  font-size: 12px;
  color: var(--text-placeholder);
}

/* 汇总 / 趋势面板 */
.panel-grid {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 14px;
  margin-bottom: 16px;
}

.panel {
  padding: 20px 22px;
  margin-bottom: 0;
}

.panel-title {
  margin: 0 0 12px;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.panel-empty {
  font-size: 13px;
  color: var(--text-placeholder);
  padding: 6px 0;
}

/* 最佳发布时段结论 */
.slot-conclusion {
  margin: 10px 0 0;
  padding: 10px 12px;
  font-size: 13px;
  line-height: 1.6;
  color: var(--color-success);
  background: var(--color-success-soft);
  border-radius: var(--radius-sm);
}

/* AI 洞察面板 */
.insight-panel {
  padding: 20px 22px;
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
  color: var(--text-sub);
}

.insight-loading {
  display: flex;
  align-items: center;
  gap: 12px;
  padding: 20px 0 6px;
  font-size: 14px;
  color: var(--text-sub);
}

.insight-body {
  margin-top: 14px;
  padding-top: 14px;
  border-top: 1px solid var(--border-color);
}

.insight-summary {
  margin: 0 0 12px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-main);
}

.insight-section-title {
  margin: 14px 0 8px;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.insight-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-main);
}

/* T14：建议列表的「生成选题 / 加入日历」动作按钮
   （flex 放在 li 内层的 .suggestion-row 上，保住 ol 的序号 marker） */
.suggestion-row {
  display: flex;
  align-items: baseline;
  gap: 10px;
  flex-wrap: wrap;
}

.suggestion-text {
  flex: 1;
  min-width: 200px;
}

.suggestion-actions {
  display: inline-flex;
  gap: 6px;
  flex-shrink: 0;
}

.btn-suggestion {
  color: var(--primary);
  border-color: var(--primary) !important;
  white-space: nowrap;
}

.btn-suggestion:hover {
  background: var(--primary-light);
}

/* 记录列表 */
.records-panel {
  padding: 20px 22px;
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
  padding: 10px 12px;
  text-align: left;
  border-bottom: 1px solid var(--gray-2);
  white-space: nowrap;
}

.records-table th {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  border-bottom: 1px solid var(--border-color);
  background: var(--gray-0);
}

.records-table th:first-child {
  border-top-left-radius: var(--radius-xs);
}

.records-table th:last-child {
  border-top-right-radius: var(--radius-xs);
}

.records-table td {
  color: var(--text-main);
}

.records-table tbody tr {
  transition: background var(--transition-fast);
}

.records-table tbody tr:hover {
  background: var(--gray-0);
}

.records-table tbody tr:last-child td {
  border-bottom: none;
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

/* 关联标识（由内容日历转录 / 已关联历史作品） */
.linked-badge {
  display: inline-flex;
  align-items: center;
  gap: 3px;
  margin-right: 4px;
  padding: 1px 6px;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-light);
  vertical-align: middle;
}

/* 「查看作品」小按钮 */
.btn-view-work {
  color: var(--primary);
  border-color: var(--primary) !important;
}

.btn-view-work:hover {
  background: var(--primary-light);
}

.platform-tag {
  display: inline-block;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 12px;
  background: var(--gray-2);
  color: var(--text-sub);
}

/* 日期单元格里的发布时间 */
.time-sub {
  margin-left: 4px;
  font-size: 12px;
  color: var(--text-sub);
  font-variant-numeric: tabular-nums;
}

/* 互动率单元格：红绿灯点 + 数值（B10） */
.rate-cell .benchmark-dot {
  margin-right: 5px;
  margin-top: -2px;
}

.actions-cell {
  display: flex;
  gap: 6px;
}

.btn-mini {
  padding: 5px 10px;
  font-size: 12px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
  transition: border-color var(--transition-fast), background var(--transition-fast),
    color var(--transition-fast), transform var(--transition-fast);
}

.btn-mini:hover {
  border-color: var(--border-hover);
  background: var(--gray-0);
}

.btn-mini:active {
  transform: translateY(1px);
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
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: overlay-in 150ms var(--ease-out);
}

.analytics-modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: modal-in 200ms var(--ease-out);
}

@keyframes overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modal-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .analytics-modal-overlay,
  .analytics-modal {
    animation: none;
  }
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
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-btn:hover {
  color: var(--text-main);
  background: var(--gray-2);
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
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.analytics-modal-foot .btn {
  border: 1px solid var(--border-color);
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
  color: var(--text-main);
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

/* U9：原生日期/时间控件对齐项目 .input 风格（高度/内边距/字体/圆角），
   否则 WebKit 默认渲染的高度与字体和文本框不一致，两列并排时参差不齐 */
.analytics-modal .input[type='date'],
.analytics-modal .input[type='time'] {
  height: 52px; /* 与 .input（14px 上下内边距 + 16px 字号 + 边框）视觉高度一致 */
  padding: 0 16px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  -webkit-appearance: none;
  appearance: none;
}

.analytics-modal .input[type='date']::-webkit-calendar-picker-indicator,
.analytics-modal .input[type='time']::-webkit-calendar-picker-indicator {
  cursor: pointer;
  opacity: 0.55;
  transition: opacity var(--transition-fast);
}

.analytics-modal .input[type='date']:hover::-webkit-calendar-picker-indicator,
.analytics-modal .input[type='time']:hover::-webkit-calendar-picker-indicator {
  opacity: 0.85;
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

/* 批量导入弹窗 */
.import-modal {
  max-width: 760px;
}

.import-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-sub);
}

.import-textarea {
  resize: vertical;
  min-height: 140px;
  line-height: 1.5;
  font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace;
  font-size: 12px;
  white-space: pre;
  overflow-x: auto;
}

.import-summary {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
  font-size: 13px;
  color: var(--text-main);
}

.import-error-count {
  color: var(--color-warning);
  background: var(--color-warning-soft);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  font-size: 12px;
}

.import-errors {
  margin: 0;
  padding: 10px 12px 10px 28px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border-radius: var(--radius-sm);
  max-height: 120px;
  overflow-y: auto;
}

.import-preview-wrap {
  border: 1px solid var(--gray-2);
  border-radius: var(--radius-sm);
  max-height: 240px;
  overflow-y: auto;
}

.import-preview-table {
  min-width: 720px;
}

.import-more {
  margin: 0;
  padding: 8px 12px;
  font-size: 12px;
  color: var(--text-sub);
  border-top: 1px solid var(--gray-2);
}

.import-result {
  padding: 8px 0;
}

.import-result-main {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
  color: var(--color-success);
}

.import-result-sub {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-main);
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
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
}
</style>
