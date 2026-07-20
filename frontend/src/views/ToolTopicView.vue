<template>
  <div class="container topic-container">
    <!-- 页头（与其他工具页一致的左对齐 page-header 范式） -->
    <div class="page-header">
      <div>
        <h1 class="page-title">选题灵感</h1>
        <p class="page-subtitle">生成选题、手动喂热点、把好选题先攒进选题库——解决「今天发什么」</p>
      </div>
    </div>

    <!-- 视图切换：生成选题 / 我的选题库 -->
    <div class="view-tabs" role="tablist" aria-label="选题工具视图">
      <button
        type="button"
        role="tab"
        class="view-tab"
        :class="{ active: activeTab === 'generate' }"
        :aria-selected="activeTab === 'generate'"
        @click="activeTab = 'generate'"
      >生成选题</button>
      <button
        type="button"
        role="tab"
        class="view-tab"
        :class="{ active: activeTab === 'library' }"
        :aria-selected="activeTab === 'library'"
        @click="activeTab = 'library'"
      >
        我的选题库
        <span v-if="ideasLoaded && ideas.length > 0" class="tab-count">{{ ideas.length }}</span>
      </button>
    </div>

    <!-- ==================== 生成选题视图 ==================== -->
    <template v-if="activeTab === 'generate'">
      <!-- 输入区 -->
      <div class="card input-card">
        <!-- 模式切换：常规选题 / 蹭热点 -->
        <div class="mode-switch" role="radiogroup" aria-label="选题模式">
          <button
            type="button"
            class="mode-btn"
            role="radio"
            :aria-checked="mode === 'normal'"
            :class="{ active: mode === 'normal' }"
            @click="mode = 'normal'"
          >常规选题</button>
          <button
            type="button"
            class="mode-btn"
            role="radio"
            :aria-checked="mode === 'hotspot'"
            :class="{ active: mode === 'hotspot' }"
            @click="mode = 'hotspot'"
          >蹭热点</button>
        </div>

        <!-- 蹭热点模式：官方热榜入口 + 热点粘贴框 -->
        <template v-if="mode === 'hotspot'">
          <div class="hotboard-tip">
            <p class="hotboard-label">先去官方免费热榜逛一圈，把看中的热榜词粘回来：</p>
            <div class="hotboard-links">
              <a
                class="hotboard-link"
                href="https://creator.xiaohongshu.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                小红书创作中心 · 笔记灵感
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
              <a
                class="hotboard-link"
                href="https://douhot.douyin.com"
                target="_blank"
                rel="noopener noreferrer"
              >
                抖音热点宝
                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"/><polyline points="15 3 21 3 21 9"/><line x1="10" y1="14" x2="21" y2="3"/></svg>
              </a>
            </div>
          </div>

          <label class="field-label" for="topic-hot-input">
            把热榜词 / 热点标题粘贴进来（每行一条，最多 {{ MAX_HOT_TOPICS }} 条）
          </label>
          <textarea
            id="topic-hot-input"
            v-model="hotTopicsInput"
            class="hot-topics-input"
            rows="5"
            maxlength="2000"
            placeholder="一行一条，例如：&#10;秋天的第一杯奶茶&#10;全民健身热潮&#10;打工人早八现状"
          ></textarea>
          <p class="hot-topics-hint" :class="{ overflow: hotTopicsOverflow }">
            已识别 {{ parsedHotTopics.length }} 条热点<template v-if="hotTopicsOverflow">，超出上限，仅取前 {{ MAX_HOT_TOPICS }} 条</template>
          </p>

          <div class="field-group">
            <label class="field-label" for="topic-niche">你的领域 / 赛道（AI 会评估热点与赛道的关联度）</label>
            <input
              id="topic-niche"
              v-model="niche"
              class="niche-input"
              type="text"
              maxlength="100"
              placeholder="例如：健身减脂、职场干货、亲子育儿、家常菜教程……"
              @keydown.enter.prevent="handleGenerate"
            />
          </div>
        </template>

        <!-- 常规模式：领域输入 -->
        <template v-else>
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
        </template>

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
          <span class="account-data-hint">
            需先在<RouterLink to="/tools/analytics" class="account-data-link">数据复盘工具</RouterLink>录入笔记数据
          </span>
        </div>

        <button
          type="button"
          class="btn btn-primary generate-btn"
          :disabled="loading || !niche.trim() || (mode === 'hotspot' && parsedHotTopics.length === 0)"
          @click="handleGenerate"
        >
          <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
          {{ generateBtnText }}
        </button>
      </div>

      <!-- 历史记录（本地存档） -->
      <div v-if="archive.length > 0" class="card history-card">
        <button type="button" class="history-toggle" @click="showArchive = !showArchive">
          <span class="history-title">历史记录（{{ archive.length }}）</span>
          <svg
            class="history-chevron"
            :class="{ open: showArchive }"
            width="16" height="16" viewBox="0 0 24 24" fill="none"
            stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"
            aria-hidden="true"
          ><polyline points="6 9 12 15 18 9"/></svg>
        </button>
        <ul v-if="showArchive" class="history-list">
          <li v-for="entry in archive" :key="entry.id">
            <button type="button" class="history-item" @click="restoreFromArchive(entry)">
              <span class="history-summary">{{ entry.niche }} · {{ entry.platform }} · {{ entry.topics.length }} 条灵感</span>
              <span class="history-time">{{ formatTime(entry.createdAt) }}</span>
            </button>
          </li>
        </ul>
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
              <!-- 蹭热点模式的增量信息：热点原词 / 发布窗口 / 关联度 -->
              <div
                v-if="item.hot_topic || item.publish_window || item.relevance"
                class="hotspot-meta"
              >
                <span v-if="item.hot_topic" class="hotspot-chip">热点：{{ item.hot_topic }}</span>
                <span v-if="item.publish_window" class="hotspot-chip window">发布窗口：{{ item.publish_window }}</span>
                <span v-if="item.relevance" class="hotspot-chip relevance">关联度：{{ item.relevance }}</span>
              </div>
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
                <button
                  type="button"
                  class="save-btn"
                  :class="{ saved: savedTitles.has(item.title) }"
                  :disabled="savedTitles.has(item.title) || savingTitle === item.title"
                  @click="handleSaveToLibrary(item)"
                >
                  {{ savedTitles.has(item.title) ? '已入库 ✓' : (savingTitle === item.title ? '入库中…' : '存入选题库') }}
                </button>
                <template v-if="addedTitles.has(item.title)">
                  <button type="button" class="calendar-btn added" disabled>已加入 ✓</button>
                  <RouterLink class="calendar-link" to="/tools/calendar">去日历看看</RouterLink>
                </template>
                <button
                  v-else
                  type="button"
                  class="calendar-btn"
                  @click="openCalendarDialog(item)"
                >
                  加入日历
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
        <p class="empty-desc">{{ hasGenerated ? '换个领域描述再试试吧' : '输入你的领域赛道，选好平台后点「生成选题灵感」，好选题可以先存进选题库慢慢挑' }}</p>
        <p v-if="!hasGenerated" class="empty-example">试试：健身减脂、职场干货、亲子育儿</p>
      </div>
    </template>

    <!-- ==================== 我的选题库视图 ==================== -->
    <template v-else>
      <div class="library-section">
        <div class="library-toolbar">
          <div class="filter-row library-filter-row">
            <button
              v-for="option in LIBRARY_FILTER_OPTIONS"
              :key="option.value"
              type="button"
              class="filter-chip"
              :class="{ active: libraryFilter === option.value }"
              @click="libraryFilter = option.value"
            >{{ option.label }}</button>
          </div>
          <button type="button" class="add-idea-btn" @click="openAddDialog">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><line x1="12" y1="5" x2="12" y2="19"/><line x1="5" y1="12" x2="19" y2="12"/></svg>
            手动添加
          </button>
        </div>

        <!-- 选题库加载失败（页内提示，可重试） -->
        <ErrorCard
          v-if="libraryError"
          :error="libraryError"
          dismissible
          style="margin-bottom: 14px;"
          @dismiss="libraryError = null"
          @retry="loadIdeas"
        />

        <!-- 加载骨架 -->
        <div v-if="ideasLoading" class="skeleton-section library-skeleton" aria-hidden="true">
          <div v-for="n in 3" :key="n" class="skeleton-card">
            <span class="sk-lines">
              <span class="sk-line sk-wide"></span>
              <span class="sk-line sk-narrow"></span>
            </span>
          </div>
        </div>

        <!-- 列表 -->
        <div v-else-if="displayIdeas.length > 0" class="idea-list">
          <div v-for="idea in displayIdeas" :key="idea.id" class="idea-card">
            <div class="idea-main">
              <div class="idea-top">
                <span class="source-badge" :class="`source-${idea.source}`">{{ ideaSourceLabel(idea.source) }}</span>
                <p class="idea-title">{{ idea.title }}</p>
              </div>
              <p v-if="idea.angle" class="idea-angle">{{ idea.angle }}</p>
              <div v-if="idea.tags.length > 0" class="card-tags">
                <span v-for="tag in idea.tags" :key="tag" class="tag-item">#{{ tag }}</span>
              </div>
              <div class="idea-footer">
                <span v-if="idea.niche" class="idea-niche">{{ idea.niche }}</span>
                <span class="idea-time">{{ formatIsoTime(idea.created_at) }} 收录</span>
              </div>
            </div>

            <div class="idea-actions">
              <select
                class="idea-status-select"
                :class="`idea-status-${idea.status}`"
                :value="idea.status"
                :disabled="ideaStatusUpdatingId === idea.id"
                :aria-label="`流转「${idea.title}」的状态`"
                @change="handleIdeaStatusChange(idea, ($event.target as HTMLSelectElement).value as IdeaStatus)"
              >
                <option v-for="s in IDEA_STATUS_OPTIONS" :key="s.value" :value="s.value">{{ s.label }}</option>
              </select>
              <button type="button" class="use-btn" @click="handleUse(idea)">用这个创作</button>
              <button type="button" class="calendar-btn" @click="openCalendarDialog(idea)">加入日历</button>
              <button
                type="button"
                class="idea-delete-btn"
                :aria-label="`删除「${idea.title}」`"
                @click="ideaDeleteTarget = idea"
              >删除</button>
            </div>
          </div>
        </div>

        <!-- 空态 -->
        <div v-else-if="!libraryError" class="empty-state">
          <div class="empty-icon" aria-hidden="true">
            <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"><path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/><path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/></svg>
          </div>
          <p class="empty-title">{{ ideas.length === 0 ? '选题库还是空的' : '该状态下还没有选题' }}</p>
          <p class="empty-desc">{{ ideas.length === 0 ? '在「生成选题」或评论洞察里点「存入选题库」，也可以手动添加，把好选题先攒起来' : '试试切换其他状态，或把别的选题流转过来' }}</p>
        </div>
      </div>
    </template>

    <!-- 加入日历弹窗 -->
    <AddToCalendarDialog
      v-if="calendarTarget"
      :idea="calendarTarget"
      :default-platform="defaultPlanPlatform"
      @close="calendarTarget = null"
      @added="onCalendarAdded"
    />

    <!-- 手动添加选题弹窗 -->
    <div v-if="showAddDialog" class="idea-dialog-mask" @click.self="closeAddDialog">
      <div class="card idea-dialog" role="dialog" aria-modal="true" aria-labelledby="add-idea-title">
        <h3 id="add-idea-title" class="idea-dialog-title">手动添加选题</h3>

        <div class="idea-dialog-field">
          <label class="idea-dialog-label" for="add-idea-title-input">选题标题 <span class="required-mark">*</span></label>
          <input
            id="add-idea-title-input"
            v-model="addForm.title"
            class="idea-dialog-input"
            type="text"
            maxlength="100"
            placeholder="如：租房 5 年才懂的收纳心得"
            :disabled="addSaving"
          />
        </div>

        <div class="idea-dialog-field">
          <label class="idea-dialog-label" for="add-idea-angle">切入角度（选填）</label>
          <textarea
            id="add-idea-angle"
            v-model="addForm.angle"
            class="idea-dialog-input"
            rows="2"
            maxlength="200"
            placeholder="为什么这个选题可能火，戳中了什么痛点"
            :disabled="addSaving"
          ></textarea>
        </div>

        <div class="idea-dialog-field">
          <label class="idea-dialog-label" for="add-idea-tags">建议标签（选填，空格或逗号分隔）</label>
          <input
            id="add-idea-tags"
            v-model="addForm.tags"
            class="idea-dialog-input"
            type="text"
            maxlength="100"
            placeholder="如：收纳 租房改造 小户型"
            :disabled="addSaving"
          />
        </div>

        <div class="idea-dialog-field">
          <label class="idea-dialog-label" for="add-idea-niche">赛道 / 领域（选填）</label>
          <input
            id="add-idea-niche"
            v-model="addForm.niche"
            class="idea-dialog-input"
            type="text"
            maxlength="100"
            placeholder="如：家居收纳"
            :disabled="addSaving"
          />
        </div>

        <p v-if="addError" class="idea-dialog-error" role="alert">{{ addError }}</p>

        <div class="idea-dialog-actions">
          <button type="button" class="btn btn-secondary" :disabled="addSaving" @click="closeAddDialog">取消</button>
          <button
            type="button"
            class="btn btn-primary"
            :disabled="addSaving || !addForm.title.trim()"
            @click="handleAddIdea"
          >
            <span v-if="addSaving" class="spinner-sm" aria-hidden="true"></span>
            {{ addSaving ? '正在添加…' : '添加到选题库' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <ConfirmDialog
      :visible="!!ideaDeleteTarget"
      title="删除这条选题？"
      :message="ideaDeleteMessage"
      confirm-text="删除"
      danger
      @confirm="doDeleteIdea"
      @cancel="ideaDeleteTarget = null"
    />

    <!-- 轻提示（已入库等） -->
    <div v-if="toast" class="lib-toast" role="status" aria-live="polite">{{ toast }}</div>

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
import { computed, onUnmounted, reactive, ref, watch } from 'vue'
import { useRouter } from 'vue-router'
import { generateTopics, type TopicIdea } from '../api/topic'
import {
  createIdea,
  deleteIdea,
  listIdeas,
  updateIdea,
  type IdeaItem,
  type IdeaSource,
  type IdeaStatus,
} from '../api/ideaLibrary'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'
import {
  addArchiveEntry,
  createTopicArchiveEntry,
  loadTopicArchive,
  platformLabelToPlanPlatform,
  saveTopicArchive,
  type CalendarIdeaLike,
  type TopicArchiveEntry,
} from '../utils/ideaArchive'
import ErrorCard from '../components/common/ErrorCard.vue'
import AddToCalendarDialog from '../components/common/AddToCalendarDialog.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'

const PLATFORMS = ['小红书', '抖音', '视频号', 'B站', '公众号'] as const
const ALL_FORMATS = '全部形式'

/** 蹭热点模式单次最多提交的热点条数（与后端 MAX_HOT_TOPICS 对齐） */
const MAX_HOT_TOPICS = 20

const router = useRouter()
const store = useGeneratorStore()

// 顶部视图切换：生成选题 / 我的选题库
const activeTab = ref<'generate' | 'library'>('generate')

const niche = ref('')
const platform = ref<string>(PLATFORMS[0])

// 跨页预填：数据复盘「生成选题」会把建议写入该键（读后即清，来源约定见 ToolAnalyticsView）
const NICHE_PREFILL_KEY = 'redink_topic_niche_prefill'
try {
  const rawPrefill = sessionStorage.getItem(NICHE_PREFILL_KEY)
  if (rawPrefill) {
    sessionStorage.removeItem(NICHE_PREFILL_KEY)
    const parsed = JSON.parse(rawPrefill) as { niche?: unknown }
    if (typeof parsed?.niche === 'string' && parsed.niche.trim()) {
      niche.value = parsed.niche.trim().slice(0, 100)
    }
  }
} catch {
  // 预填数据损坏时静默忽略，不影响页面正常使用
}

const useAccountData = ref(false)
const accountContextUsed = ref(false)
const loading = ref(false)
const hasGenerated = ref(false)
const error = ref<AppError | null>(null)
const topics = ref<TopicIdea[]>([])
const sortByHeat = ref(true)
const formatFilter = ref(ALL_FORMATS)
const copiedTitle = ref('')

// 生成模式：常规选题 / 蹭热点
const mode = ref<'normal' | 'hotspot'>('normal')
const hotTopicsInput = ref('')

// 当前结果的生成上下文（决定「存入选题库」的 source 与 niche）
const resultMode = ref<'normal' | 'hotspot'>('normal')
const resultNiche = ref('')

// 本地存档（最近 10 次生成结果）
const archive = ref<TopicArchiveEntry[]>(loadTopicArchive())
const showArchive = ref(false)

// 加入日历：当前弹窗对应的选题 + 已加入的选题标题集合
const calendarTarget = ref<CalendarIdeaLike | null>(null)
const addedTitles = ref<Set<string>>(new Set())

// 存入选题库：已入库的标题集合 + 正在入库的标题
const savedTitles = ref<Set<string>>(new Set())
const savingTitle = ref('')

/** 工具页选中的平台（中文名）映射为日历平台枚举，未知平台回退小红书 */
const defaultPlanPlatform = computed(() => platformLabelToPlanPlatform(platform.value))

let copyTimer: ReturnType<typeof setTimeout> | undefined
let toastTimer: ReturnType<typeof setTimeout> | undefined

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  if (toastTimer !== undefined) clearTimeout(toastTimer)
})

// ==================== 轻提示 ====================

const toast = ref('')

function showToast(message: string) {
  toast.value = message
  if (toastTimer !== undefined) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => { toast.value = '' }, 2000)
}

// ==================== 生成选题 ====================

/** 热点粘贴框逐行解析（去空白行） */
const parsedHotTopics = computed(() =>
  hotTopicsInput.value
    .split('\n')
    .map(line => line.trim())
    .filter(line => line.length > 0)
)

const hotTopicsOverflow = computed(() => parsedHotTopics.value.length > MAX_HOT_TOPICS)

const generateBtnText = computed(() => {
  if (loading.value) {
    return mode.value === 'hotspot' ? '正在结合热点生成…' : '正在生成选题灵感…'
  }
  return mode.value === 'hotspot' ? '生成蹭点选题' : '生成选题灵感'
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

// 新一批结果生成后重置筛选，避免残留的筛选项把结果全部过滤掉；
// 同时重置「已加入日历」「已入库」标记，避免同名标题跨批次误显示
watch(topics, () => {
  formatFilter.value = ALL_FORMATS
  addedTitles.value = new Set()
  savedTitles.value = new Set()
})

function heatClass(heat: number): string {
  if (heat >= 85) return 'heat-high'
  if (heat >= 70) return 'heat-mid'
  return 'heat-low'
}

async function handleGenerate() {
  if (!niche.value.trim() || loading.value) return
  if (mode.value === 'hotspot' && parsedHotTopics.value.length === 0) return

  loading.value = true
  error.value = null

  try {
    const result = await generateTopics({
      niche: niche.value.trim(),
      platform: platform.value,
      ...(useAccountData.value ? { use_account_data: true } : {}),
      ...(mode.value === 'hotspot'
        ? { hot_topics: parsedHotTopics.value.slice(0, MAX_HOT_TOPICS) }
        : {})
    })

    if (result.success && result.topics) {
      topics.value = result.topics
      accountContextUsed.value = result.account_context_used === true
      hasGenerated.value = true
      resultMode.value = mode.value
      resultNiche.value = niche.value.trim()
      recordArchive(result.topics)
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

// ==================== 本地存档 ====================

function recordArchive(resultTopics: TopicIdea[]) {
  if (resultTopics.length === 0) return
  const entry = createTopicArchiveEntry({
    niche: niche.value.trim(),
    platform: platform.value,
    accountContextUsed: accountContextUsed.value,
    topics: resultTopics,
  })
  archive.value = addArchiveEntry(archive.value, entry)
  saveTopicArchive(archive.value)
}

/** 从选题结构反推生成模式（存档条目不显式记录模式，用增量字段判断） */
function detectEntryMode(entryTopics: TopicIdea[]): 'normal' | 'hotspot' {
  return entryTopics.some(t => t.hot_topic || t.publish_window || t.relevance)
    ? 'hotspot'
    : 'normal'
}

/** 点击存档条目：回填输入与完整结果，不重新调 AI */
function restoreFromArchive(entry: TopicArchiveEntry) {
  if (loading.value) return
  niche.value = entry.niche
  if ((PLATFORMS as readonly string[]).includes(entry.platform)) {
    platform.value = entry.platform
  }
  topics.value = entry.topics
  accountContextUsed.value = entry.accountContextUsed
  hasGenerated.value = true
  resultMode.value = detectEntryMode(entry.topics)
  resultNiche.value = entry.niche
  error.value = null
}

function formatTime(timestamp: number): string {
  const d = new Date(timestamp)
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

// ==================== 存入选题库（收集入口） ====================

async function handleSaveToLibrary(item: TopicIdea) {
  if (savedTitles.value.has(item.title) || savingTitle.value) return
  savingTitle.value = item.title

  const res = await createIdea({
    title: item.title,
    angle: item.angle,
    tags: item.tags,
    source: resultMode.value === 'hotspot' ? 'hotspot' : 'topic',
    niche: resultNiche.value,
  })
  savingTitle.value = ''

  if (res.success && res.idea) {
    savedTitles.value.add(item.title)
    // 选题库已加载过时同步头插，切过去即可见
    if (ideasLoaded.value) ideas.value.unshift(res.idea)
    showToast('已入库')
  } else {
    showToast(res.error_message || '存入选题库失败，请重试')
  }
}

// ==================== 加入内容日历 ====================

function openCalendarDialog(item: CalendarIdeaLike) {
  calendarTarget.value = item
}

function onCalendarAdded() {
  if (calendarTarget.value) {
    addedTitles.value.add(calendarTarget.value.title)
  }
  calendarTarget.value = null
}

/**
 * 把选题用于创作：把标题、切入角度、建议标签组合成更丰富的主题文本
 * 写入 generator store，跳回首页创作流程（空字段跳过对应行）。
 * 选题库条目与生成结果同构（title/angle/tags），共用此入口。
 */
function handleUse(item: CalendarIdeaLike) {
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

// ==================== 我的选题库 ====================

const IDEA_STATUS_OPTIONS: Array<{ value: IdeaStatus; label: string }> = [
  { value: 'idea', label: '想法' },
  { value: 'todo', label: '待做' },
  { value: 'done', label: '已做' },
  { value: 'viral', label: '已爆' },
]

const LIBRARY_FILTER_OPTIONS: Array<{ value: 'all' | IdeaStatus; label: string }> = [
  { value: 'all', label: '全部' },
  ...IDEA_STATUS_OPTIONS,
]

const IDEA_SOURCE_LABELS: Record<IdeaSource, string> = {
  manual: '手动',
  topic: '选题灵感',
  insight: '评论洞察',
  hotspot: '蹭热点',
}

const ideas = ref<IdeaItem[]>([])
const ideasLoading = ref(false)
const ideasLoaded = ref(false)
const libraryError = ref<AppError | null>(null)
const libraryFilter = ref<'all' | IdeaStatus>('all')
const ideaStatusUpdatingId = ref('')
const ideaDeleteTarget = ref<IdeaItem | null>(null)

const displayIdeas = computed(() =>
  libraryFilter.value === 'all'
    ? ideas.value
    : ideas.value.filter(idea => idea.status === libraryFilter.value)
)

const ideaDeleteMessage = computed(() =>
  ideaDeleteTarget.value ? `「${ideaDeleteTarget.value.title}」删除后无法恢复。` : ''
)

function ideaSourceLabel(source: IdeaSource): string {
  return IDEA_SOURCE_LABELS[source] || source
}

function ideaStatusLabel(status: IdeaStatus): string {
  return IDEA_STATUS_OPTIONS.find(s => s.value === status)?.label || status
}

function formatIsoTime(iso: string): string {
  const d = new Date(iso)
  if (Number.isNaN(d.getTime())) return ''
  const pad = (n: number) => String(n).padStart(2, '0')
  return `${d.getMonth() + 1}/${d.getDate()} ${pad(d.getHours())}:${pad(d.getMinutes())}`
}

async function loadIdeas() {
  ideasLoading.value = true
  libraryError.value = null

  const res = await listIdeas()
  ideasLoading.value = false

  if (res.success) {
    ideas.value = res.ideas
    ideasLoaded.value = true
  } else {
    libraryError.value = normalizeApiError(
      res.error || res.error_message || '获取选题库列表失败',
      '获取选题库列表失败'
    )
  }
}

// 首次切到选题库视图时才拉取（惰性加载）
watch(activeTab, tab => {
  if (tab === 'library' && !ideasLoaded.value && !ideasLoading.value) {
    loadIdeas()
  }
})

/** 状态流转（想法/待做/已做/已爆） */
async function handleIdeaStatusChange(idea: IdeaItem, status: IdeaStatus) {
  if (status === idea.status || ideaStatusUpdatingId.value) return
  ideaStatusUpdatingId.value = idea.id

  const res = await updateIdea(idea.id, { status })
  ideaStatusUpdatingId.value = ''

  if (res.success && res.idea) {
    const index = ideas.value.findIndex(item => item.id === idea.id)
    if (index !== -1) ideas.value[index] = res.idea
    showToast(`已流转为「${ideaStatusLabel(status)}」`)
  } else {
    showToast(res.error_message || '更新选题状态失败')
    // 失败时回拉列表，纠正下拉框的显示值
    await loadIdeas()
  }
}

async function doDeleteIdea() {
  if (!ideaDeleteTarget.value) return
  const target = ideaDeleteTarget.value
  ideaDeleteTarget.value = null

  const res = await deleteIdea(target.id)
  if (res.success) {
    ideas.value = ideas.value.filter(idea => idea.id !== target.id)
    showToast(`已删除「${target.title}」`)
  } else {
    showToast(res.error_message || '删除选题失败')
  }
}

// ==================== 手动添加选题 ====================

const showAddDialog = ref(false)
const addSaving = ref(false)
const addError = ref('')

const addForm = reactive({
  title: '',
  angle: '',
  tags: '',
  niche: '',
})

function openAddDialog() {
  addForm.title = ''
  addForm.angle = ''
  addForm.tags = ''
  addForm.niche = ''
  addError.value = ''
  showAddDialog.value = true
}

function closeAddDialog() {
  if (addSaving.value) return
  showAddDialog.value = false
}

/** 标签输入解析：支持空格 / 中英文逗号 / 顿号分隔，去 # 前缀 */
function parseTagsInput(text: string): string[] {
  return text
    .split(/[,，、\s]+/)
    .map(tag => tag.replace(/^#/, '').trim())
    .filter(Boolean)
}

async function handleAddIdea() {
  if (!addForm.title.trim() || addSaving.value) return
  addSaving.value = true
  addError.value = ''

  const res = await createIdea({
    title: addForm.title.trim(),
    angle: addForm.angle.trim(),
    tags: parseTagsInput(addForm.tags),
    source: 'manual',
    niche: addForm.niche.trim(),
  })
  addSaving.value = false

  if (res.success && res.idea) {
    ideas.value.unshift(res.idea)
    ideasLoaded.value = true
    showAddDialog.value = false
    showToast('已入库')
  } else {
    addError.value = res.error_message || '添加失败，请重试'
  }
}
</script>

<style scoped>
.topic-container {
  max-width: 860px;
  margin: 0 auto;
  padding: 24px 16px 60px;
}

/* ── 页头（左对齐 page-header，标题排版走 base.css 全局样式） ── */
.page-header {
  margin-bottom: var(--space-4);
  animation: fadeIn 0.5s var(--ease-out);
}

/* ── 视图切换 tab（生成选题 / 我的选题库） ── */
.view-tabs {
  display: inline-flex;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  overflow: hidden;
  background: var(--bg-card);
  margin-bottom: 20px;
}

.view-tab {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  padding: 8px 20px;
  font-size: 14px;
  border: none;
  background: transparent;
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.view-tab:hover:not(.active) {
  background: var(--gray-1);
  color: var(--text-main);
}

.view-tab.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

.tab-count {
  min-width: 18px;
  height: 18px;
  padding: 0 5px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.25);
  font-size: 11px;
  line-height: 18px;
  text-align: center;
  font-variant-numeric: tabular-nums;
}

.view-tab:not(.active) .tab-count {
  background: var(--gray-2);
  color: var(--text-sub);
}

/* ── 输入卡片（基于全局 .card，内距走 --space-6） ───────────────────── */
.input-card {
  padding: var(--space-6);
  margin-bottom: 0;
  animation: fadeIn 0.5s var(--ease-out);
}

/* ── 模式切换（常规选题 / 蹭热点） ── */
.mode-switch {
  display: inline-flex;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  overflow: hidden;
  margin-bottom: 18px;
}

.mode-btn {
  padding: 6px 18px;
  font-size: 13.5px;
  border: none;
  background: var(--bg-card);
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.mode-btn:hover:not(.active) {
  background: var(--gray-1);
  color: var(--text-main);
}

.mode-btn.active {
  background: var(--primary);
  color: #fff;
  font-weight: 600;
}

/* ── 蹭热点模式：官方热榜入口 ── */
.hotboard-tip {
  margin-bottom: 18px;
  padding: 12px 14px;
  border-radius: var(--radius-md);
  border: 1px dashed var(--primary);
  background: var(--primary-fade);
}

.hotboard-label {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-main);
}

.hotboard-links {
  display: flex;
  flex-wrap: wrap;
  gap: 14px;
}

.hotboard-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  text-decoration: none;
}

.hotboard-link:hover {
  text-decoration: underline;
}

/* ── 蹭热点模式：热点粘贴框 ── */
.hot-topics-input {
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
  min-height: 110px;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    background var(--transition-fast);
  background: var(--gray-1);
}

.hot-topics-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
  box-shadow: var(--shadow-focus);
}

.hot-topics-hint {
  margin: 8px 2px 0;
  font-size: 13px;
  color: var(--text-sub);
}

.hot-topics-hint.overflow {
  color: var(--color-warning);
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

/* 提示内嵌的「数据复盘工具」跳转（参照品牌空态「去创建」的链接写法） */
.account-data-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.account-data-link:hover {
  text-decoration: underline;
}

/* 生成按钮基于全局 .btn btn-primary，仅覆盖布局 */
.generate-btn {
  margin-top: 22px;
  width: 100%;
}

/* ── 历史记录（本地存档，样式参照对标拆解的历史区） ── */
.history-card {
  margin-top: var(--space-4);
  padding: var(--space-3) var(--space-4);
}

.history-toggle {
  display: flex;
  align-items: center;
  justify-content: space-between;
  width: 100%;
  border: none;
  background: transparent;
  padding: 4px 0;
  cursor: pointer;
  color: var(--text-main);
}

.history-title {
  font-size: 14px;
  font-weight: 600;
}

.history-chevron {
  color: var(--text-sub);
  transition: transform var(--transition-fast);
}

.history-chevron.open {
  transform: rotate(180deg);
}

.history-list {
  list-style: none;
  padding: 0;
  margin: var(--space-3) 0 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  max-height: 280px;
  overflow-y: auto;
}

.history-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-1);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.history-item:hover {
  border-color: var(--primary);
  background: var(--primary-fade);
}

.history-summary {
  flex: 1;
  min-width: 0;
  font-size: 13.5px;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.history-time {
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-sub);
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

/* ── 蹭热点模式的增量信息 chips ── */
.hotspot-meta {
  display: flex;
  flex-wrap: wrap;
  gap: 6px;
}

.hotspot-chip {
  padding: 2px 10px;
  border-radius: var(--radius-full);
  background: var(--color-danger-soft);
  color: var(--color-danger);
  font-size: 12px;
  font-weight: 500;
  word-break: break-word;
}

.hotspot-chip.window {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.hotspot-chip.relevance {
  background: var(--gray-2);
  color: var(--text-sub);
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

/* ── 存入选题库按钮 ── */
.save-btn {
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

.save-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.save-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.save-btn.saved {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
  cursor: default;
}

.calendar-btn {
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

.calendar-btn:hover:not(:disabled) {
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.calendar-btn:active:not(:disabled) {
  transform: translateY(0);
  box-shadow: none;
}

.calendar-btn.added {
  background: var(--color-success-soft);
  border-color: var(--color-success);
  color: var(--color-success);
  cursor: default;
}

.calendar-link {
  font-size: 12px;
  color: var(--primary);
  text-align: center;
  text-decoration: none;
  white-space: nowrap;
}

.calendar-link:hover {
  text-decoration: underline;
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

/* ==================== 我的选题库 ==================== */

.library-section {
  animation: fadeIn 0.4s var(--ease-out);
}

.library-toolbar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 10px;
  flex-wrap: wrap;
  margin-bottom: 14px;
}

.library-filter-row {
  margin-bottom: 0;
  padding: 0;
}

.add-idea-btn {
  display: inline-flex;
  align-items: center;
  gap: 5px;
  padding: 6px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--primary);
  background: var(--bg-card);
  color: var(--primary);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
}

.add-idea-btn:hover {
  background: var(--primary-light);
  box-shadow: var(--shadow-xs);
}

.library-skeleton {
  margin-top: 0;
}

.idea-list {
  display: flex;
  flex-direction: column;
  gap: 12px;
}

.idea-card {
  display: flex;
  align-items: stretch;
  gap: 14px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  padding: var(--space-4) 18px;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base), border-color var(--transition-base);
}

.idea-card:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-sm);
}

.idea-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
}

.idea-top {
  display: flex;
  align-items: flex-start;
  gap: 8px;
}

.source-badge {
  flex-shrink: 0;
  margin-top: 2px;
  padding: 2px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
}

.source-badge.source-manual { background: var(--gray-2); color: var(--text-sub); }
.source-badge.source-topic { background: var(--primary-light); color: var(--primary); }
.source-badge.source-insight { background: var(--color-info-soft); color: var(--color-info); }
.source-badge.source-hotspot { background: var(--color-danger-soft); color: var(--color-danger); }

.idea-title {
  margin: 0;
  font-size: 15.5px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.55;
  word-break: break-word;
}

.idea-angle {
  margin: 0;
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.6;
  word-break: break-word;
}

.idea-footer {
  display: flex;
  align-items: center;
  gap: 10px;
  flex-wrap: wrap;
}

.idea-niche {
  padding: 1px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--gray-0);
  font-size: 12px;
  color: var(--text-sub);
}

.idea-time {
  font-size: 12px;
  color: var(--text-secondary);
}

.idea-actions {
  flex-shrink: 0;
  display: flex;
  flex-direction: column;
  align-items: stretch;
  justify-content: center;
  gap: 6px;
}

/* 状态流转下拉（语义色与状态对应：想法/待做/已做/已爆） */
.idea-status-select {
  border: none;
  border-radius: var(--radius-full);
  padding: 5px 10px;
  font-size: 12.5px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  text-align: center;
}

.idea-status-select:disabled {
  opacity: 0.6;
  cursor: wait;
}

.idea-status-select.idea-status-idea { background: var(--color-info-soft); color: var(--color-info); }
.idea-status-select.idea-status-todo { background: var(--color-warning-soft); color: var(--color-warning); }
.idea-status-select.idea-status-done { background: var(--color-success-soft); color: var(--color-success); }
.idea-status-select.idea-status-viral { background: var(--primary-light); color: var(--primary); }

.idea-delete-btn {
  padding: 5px 14px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--color-danger);
  font-size: 12.5px;
  font-weight: 500;
  cursor: pointer;
  white-space: nowrap;
  transition: background var(--transition-fast), border-color var(--transition-fast);
}

.idea-delete-btn:hover {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

/* ── 手动添加选题弹窗（样式参照加入日历弹窗） ── */
.idea-dialog-mask {
  position: fixed;
  inset: 0;
  background: rgba(0, 0, 0, 0.4);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1100;
  padding: 16px;
  animation: maskIn 0.2s var(--ease-out);
}

.idea-dialog {
  width: min(460px, 100%);
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.idea-dialog-title {
  font-size: 17px;
  font-weight: 700;
  color: var(--text-main);
  margin: 0;
}

.idea-dialog-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.idea-dialog-label {
  font-size: 13.5px;
  font-weight: 600;
  color: var(--text-main);
}

.required-mark {
  color: var(--color-danger);
}

.idea-dialog-input {
  width: 100%;
  box-sizing: border-box;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

textarea.idea-dialog-input {
  resize: vertical;
  line-height: 1.6;
}

.idea-dialog-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.idea-dialog-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

.idea-dialog-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

/* ── 轻提示 toast ── */
.lib-toast {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 22px;
  border-radius: var(--radius-full);
  background: var(--text-main);
  color: #fff;
  font-size: 13.5px;
  font-weight: 500;
  box-shadow: var(--shadow-lg);
  z-index: 1200;
  animation: slideUp 0.3s var(--ease-out);
  white-space: nowrap;
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

  .input-card {
    padding: 18px 16px;
    border-radius: var(--radius-lg);
  }

  .option-chip {
    padding: 6px 13px;
    font-size: 13px;
  }

  .topic-card,
  .idea-card {
    flex-wrap: wrap;
    padding: 14px;
    gap: 10px;
  }

  .card-main,
  .idea-main {
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
    flex-wrap: wrap;
    justify-content: flex-end;
  }

  .idea-actions {
    flex-direction: row;
    flex-wrap: wrap;
    width: 100%;
    justify-content: flex-end;
    padding-top: 10px;
    border-top: 1px dashed var(--border-color);
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

@keyframes maskIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 降低动效偏好：关闭入场、stagger 与 shimmer */
@media (prefers-reduced-motion: reduce) {
  .page-header,
  .input-card,
  .result-section,
  .library-section,
  .topic-card,
  .empty-state,
  .idea-dialog-mask,
  .lib-toast,
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
  .save-btn,
  .save-btn:hover,
  .topic-card:hover {
    transform: none;
  }
}
</style>
