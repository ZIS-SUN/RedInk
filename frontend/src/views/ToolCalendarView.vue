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
        <button
          type="button"
          class="btn btn-mini hotspot-toggle"
          :class="{ active: hotspotLayerEnabled }"
          :aria-pressed="hotspotLayerEnabled"
          title="在日历上叠加节日/电商/季节营销节点"
          @click="toggleHotspotLayer"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>
          节点图层
        </button>
        <button type="button" class="btn btn-mini btn-ai" @click="openAiModal">
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2"></polygon></svg>
          AI 排期
        </button>
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

    <!-- 加载中：轻量骨架占位 -->
    <div v-if="loading" class="card skeleton-panel" aria-hidden="true">
      <span class="skeleton skeleton-line" style="width: 26%;"></span>
      <span v-for="i in 5" :key="i" class="skeleton skeleton-line" style="width: 100%; height: 40px;"></span>
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
            <div
              v-if="hotspotLayerEnabled && (hotspotsByDate[cell.date] || []).length > 0"
              class="day-hotspots"
            >
              <span
                v-for="node in hotspotsByDate[cell.date]"
                :key="node.id"
                class="hotspot-mark"
                :class="`hotspot-${node.type}`"
                :title="`${node.name} · ${hotspotTypeLabel(node.type)}节点\n${node.platform_hint}`"
              >{{ node.name }}</span>
            </div>
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
                <span v-if="plan.publish_time" class="chip-time">{{ plan.publish_time }}</span>
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
          <div class="empty-icon-wrap">
            <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>
          </div>
          <h3 class="empty-title">{{ monthDisplay }} 还没有计划</h3>
          <p class="empty-tips">添加一条内容计划，开始规划你的发布节奏</p>
          <button type="button" class="btn btn-primary empty-cta" @click="openCreateModal()">立即添加</button>
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
                <span v-if="plan.publish_time" class="plan-time">
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 16 14"></polyline></svg>
                  {{ plan.publish_time }}
                </span>
                <button
                  v-if="plan.record_id"
                  type="button"
                  class="record-link"
                  :aria-label="`查看「${plan.title}」关联的作品`"
                  title="该计划已关联历史作品"
                  @click.stop="viewLinkedRecord()"
                >
                  <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>
                  查看作品
                </button>
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

      <!-- 即将到来的营销节点（未来 30 天，按临近排序） -->
      <div v-if="hotspotLayerEnabled && upcomingNodes.length > 0" class="card hotspot-upcoming">
        <div class="hotspot-upcoming-head">
          <h3 class="hotspot-upcoming-title">
            <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><path d="M8.5 14.5A2.5 2.5 0 0 0 11 12c0-1.38-.5-2-1-3-1.072-2.143-.224-4.054 2-6 .5 2.5 2 4.9 4 6.5 2 1.6 3 3.5 3 5.5a7 7 0 1 1-14 0c0-1.153.433-2.294 1-3a2.5 2.5 0 0 0 2.5 2.5z"></path></svg>
            即将到来的节点（未来 30 天）
          </h3>
          <span class="hotspot-upcoming-sub">提前备稿，抢占节点流量</span>
        </div>
        <div class="hotspot-node-list">
          <div v-for="node in upcomingNodes" :key="node.id" class="hotspot-node-row">
            <div class="hotspot-node-date">
              <span class="hotspot-node-countdown">{{ countdownText(node, todayDate) }}</span>
              <span class="hotspot-node-day">{{ node.date.slice(5) }}</span>
            </div>
            <div class="hotspot-node-main">
              <div class="hotspot-node-title">
                <span class="hotspot-mark" :class="`hotspot-${node.type}`">{{ hotspotTypeLabel(node.type) }}</span>
                <span class="hotspot-node-name">{{ node.name }}</span>
                <span class="hotspot-node-prep">{{ prepWindowText(node, todayDate) }}</span>
              </div>
              <div class="hotspot-node-hint">{{ node.platform_hint }}</div>
              <div class="hotspot-node-niche">适配赛道：{{ node.niche_hint }}</div>
            </div>
            <div class="hotspot-node-actions">
              <button
                type="button"
                class="btn btn-mini btn-create"
                :disabled="hotspotTopicGeneratingId !== null"
                :aria-label="`为「${node.name}」生成节点选题`"
                @click="handleHotspotTopics(node)"
              >
                {{ hotspotTopicGeneratingId === node.id ? '生成中...' : '生成节点选题' }}
              </button>
            </div>
          </div>
        </div>
      </div>
    </template>

    <!-- 节点选题结果弹窗 -->
    <Teleport to="body">
      <div v-if="hotspotTopicNode" class="plan-modal-overlay" @click.self="closeHotspotTopicModal">
        <div class="plan-modal" role="dialog" aria-modal="true" :aria-label="`「${hotspotTopicNode.name}」节点选题`">
          <div class="plan-modal-head">
            <h3>「{{ hotspotTopicNode.name }}」节点选题</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeHotspotTopicModal">×</button>
          </div>
          <div class="plan-modal-body">
            <p class="log-hint">已结合节点的平台侧重提示生成，点选题即可进入创作。</p>
            <div class="hotspot-topic-list">
              <div v-for="idea in hotspotTopicIdeas" :key="idea.title" class="hotspot-topic-item">
                <div class="hotspot-topic-main">
                  <div class="hotspot-topic-title">{{ idea.title }}</div>
                  <div v-if="idea.angle" class="hotspot-topic-angle">{{ idea.angle }}</div>
                </div>
                <button type="button" class="btn btn-mini btn-create" @click="useHotspotTopic(idea)">
                  用这个创作
                </button>
              </div>
            </div>
          </div>
          <div class="plan-modal-foot">
            <button type="button" class="btn" @click="closeHotspotTopicModal">关闭</button>
          </div>
        </div>
      </div>
    </Teleport>

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
              <label>发布时间（可选）</label>
              <input v-model="form.publish_time" class="input" type="time" />
              <button
                v-if="bestSlot && suggestedTime"
                type="button"
                class="slot-hint"
                :title="`点击填入 ${suggestedTime}`"
                @click="applySuggestedTime"
              >
                📊 根据你的数据，「{{ bestSlot.name }}」互动率最高
              </button>
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

    <!-- AI 一周排期弹窗 -->
    <Teleport to="body">
      <div v-if="showAiModal" class="plan-modal-overlay" @click.self="closeAiModal">
        <div class="plan-modal ai-modal" role="dialog" aria-modal="true" aria-label="AI 一周排期">
          <div class="plan-modal-head">
            <h3>AI 一周排期</h3>
            <button type="button" class="close-btn" aria-label="关闭" :disabled="aiGenerating || aiAdding" @click="closeAiModal">×</button>
          </div>

          <div class="plan-modal-body">
            <div class="form-field">
              <label>领域 / 赛道 <span class="required">*</span></label>
              <input
                v-model="aiForm.niche"
                class="input"
                type="text"
                placeholder="如：健身减脂、职场干货、家常菜教程"
                maxlength="50"
                :disabled="aiGenerating"
                @keyup.enter="handleAiGenerate"
              />
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>发布平台</label>
                <select v-model="aiForm.platform" class="input" :disabled="aiGenerating">
                  <option v-for="p in PLATFORM_OPTIONS" :key="p.value" :value="p.value">{{ p.label }}</option>
                </select>
              </div>
              <div class="form-field">
                <label>每周条数（1-7）</label>
                <input v-model.number="aiForm.frequency" class="input" type="number" min="1" max="7" :disabled="aiGenerating" />
              </div>
            </div>

            <label class="ai-switch">
              <input v-model="aiForm.useAccountData" type="checkbox" :disabled="aiGenerating" />
              <span>结合我的账号数据（发布时间优先安排在高互动时段）</span>
            </label>

            <p v-if="aiError" class="form-error" role="alert">{{ aiError }}</p>

            <!-- 预览列表 -->
            <template v-if="aiPreview.length > 0">
              <div class="ai-preview-head">
                <span>排期预览（已勾选 {{ aiSelectedCount }}/{{ aiPreview.length }} 条）</span>
                <span v-if="aiAccountContextUsed" class="ai-context-badge">已结合账号数据</span>
              </div>
              <div class="ai-preview-list">
                <label v-for="(item, idx) in aiPreview" :key="idx" class="ai-preview-item" :class="{ unchecked: !item.selected }">
                  <input v-model="item.selected" type="checkbox" :disabled="aiAdding" />
                  <div class="ai-preview-main">
                    <div class="ai-preview-title">{{ item.title }}</div>
                    <div class="ai-preview-meta">
                      <span>{{ item.publish_date }}</span>
                      <span v-if="item.publish_time">{{ item.publish_time }}</span>
                      <span>{{ platformLabel(item.platform) }}</span>
                    </div>
                    <div v-if="item.notes" class="ai-preview-notes">{{ item.notes }}</div>
                  </div>
                </label>
              </div>
            </template>
          </div>

          <div class="plan-modal-foot">
            <button type="button" class="btn" :disabled="aiGenerating || aiAdding" @click="closeAiModal">取消</button>
            <button type="button" class="btn" :disabled="!canGenerateAi || aiAdding" @click="handleAiGenerate">
              {{ aiGenerating ? '生成中...' : (aiPreview.length > 0 ? '重新生成' : '生成排期') }}
            </button>
            <button
              v-if="aiPreview.length > 0"
              type="button"
              class="btn btn-primary"
              :disabled="aiSelectedCount === 0 || aiAdding || aiGenerating"
              @click="handleAiAddToCalendar"
            >
              {{ aiAdding ? '添加中...' : `添加到日历（${aiSelectedCount} 条）` }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 转录到数据复盘弹窗（条目标记为已发布后弹出） -->
    <Teleport to="body">
      <div v-if="showLogModal" class="plan-modal-overlay" @click.self="closeLogModal">
        <div class="plan-modal" role="dialog" aria-modal="true" aria-label="转录到数据复盘">
          <div class="plan-modal-head">
            <h3>转录到数据复盘</h3>
            <button type="button" class="close-btn" aria-label="关闭" :disabled="logSaving" @click="closeLogModal">×</button>
          </div>

          <div class="plan-modal-body">
            <p class="log-hint">
              已标记为「已发布」。补充播放、点赞等指标即可一键转录到数据复盘；
              也可以先跳过，之后再次转录会更新同一条记录，不会重复新建。
            </p>

            <div class="form-field">
              <label>内容标题</label>
              <input v-model="logForm.title" class="input" type="text" maxlength="100" :disabled="logSaving" />
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>发布平台</label>
                <input v-model="logForm.platform" class="input" type="text" maxlength="30" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>发布日期</label>
                <input v-model="logForm.publish_date" class="input" type="date" :disabled="logSaving" />
              </div>
            </div>

            <div class="form-field">
              <label>发布时间（可选）</label>
              <input v-model="logForm.publish_time" class="input" type="time" :disabled="logSaving" />
            </div>

            <div class="form-grid three">
              <div class="form-field">
                <label>曝光 / 播放</label>
                <input v-model.number="logForm.views" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>点赞</label>
                <input v-model.number="logForm.likes" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>收藏</label>
                <input v-model.number="logForm.collects" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>评论</label>
                <input v-model.number="logForm.comments" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>转发</label>
                <input v-model.number="logForm.shares" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
              <div class="form-field">
                <label>涨粉</label>
                <input v-model.number="logForm.followers_gained" class="input" type="number" min="0" placeholder="0" :disabled="logSaving" />
              </div>
            </div>

            <p v-if="logError" class="form-error" role="alert">{{ logError }}</p>
          </div>

          <div class="plan-modal-foot">
            <button type="button" class="btn" :disabled="logSaving" @click="closeLogModal">跳过</button>
            <button type="button" class="btn btn-primary" :disabled="logSaving || !canLogSubmit" @click="handleLogSubmit">
              {{ logSaving ? '转录中...' : '转录到复盘' }}
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
  generateWeekPlan,
  getPlanList,
  getPlanStats,
  logPlanPerformance,
  updatePlan,
  type PlanItem,
  type PlanPlatform,
  type PlanStats,
  type PlanStatus,
  type WeekPlanPreviewItem
} from '../api/calendar'
import { getAnalyticsStats, type AnalyticsTimeSlot } from '../api/analytics'
import { getHotspots, type HotspotNode } from '../api/hotspot'
import { generateTopics, type TopicIdea } from '../api/topic'
import { pickBestTimeSlot, slotToSuggestedTime } from '../utils/calendarSuggest'
import {
  addDays,
  buildHotspotTopicNiche,
  calendarGridRange,
  countdownText,
  groupHotspotsByDate,
  hotspotTypeLabel,
  loadHotspotLayerEnabled,
  prepWindowText,
  saveHotspotLayerEnabled,
  upcomingHotspots
} from '../utils/hotspotLayer'
import { useGeneratorStore } from '../stores/generator'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 内容日历（发布计划）页面
 *
 * 功能：
 * - 月历 / 列表两种视图，按月切换
 * - 计划条目的新建 / 编辑 / 删除（删除二次确认）
 * - 可选发布时间 + 基于账号数据的最佳时段推荐
 * - 关联历史作品（record_id）的「查看作品」入口
 * - AI 一周排期（生成预览 → 勾选 → 逐条添加到日历）
 * - 状态流转（想法 → 制作中 → 待发布 → 已发布）
 * - 标记「已发布」后一键转录到数据复盘（标题/平台/日期预填，补充指标即可）
 * - 按平台 / 状态筛选
 * - 本月统计（计划总数 + 各状态数量）
 * - 热点节点图层（可开关，偏好存 localStorage）：月历叠加节日/电商/季节节点，
 *   「即将到来的节点」区块展示未来 30 天倒计时与备稿窗口，可一键生成节点选题
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
  return PLATFORM_OPTIONS.find(p => p.value === value)?.color || 'var(--border-hover)'
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
  publish_time: string
  status: PlanStatus
  notes: string
}>({
  title: '',
  platform: 'xiaohongshu',
  publish_date: todayDate,
  publish_time: '',
  status: 'idea',
  notes: ''
})

// ==================== 最佳发布时段推荐（基于数据复盘的账号数据） ====================

/** 互动率最高的时段（拉取失败或无数据时为 null，提示静默不显示） */
const bestSlot = ref<AnalyticsTimeSlot | null>(null)
let bestSlotLoaded = false

/** 最佳时段对应的建议发布时间（时段起始整点），未知时段为 null */
const suggestedTime = computed(() =>
  bestSlot.value ? slotToSuggestedTime(bestSlot.value.name) : null
)

/**
 * 异步拉取账号时段统计（每次进入页面只拉一次；失败/为空静默）
 */
async function loadBestSlot() {
  if (bestSlotLoaded) return
  bestSlotLoaded = true
  const res = await getAnalyticsStats()
  if (res.success && res.stats) {
    bestSlot.value = pickBestTimeSlot(res.stats.time_slots)
  }
}

/** 点击提示：把最佳时段的起始整点填入发布时间 */
function applySuggestedTime() {
  if (suggestedTime.value) form.publish_time = suggestedTime.value
}

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
  form.publish_time = ''
  form.status = 'idea'
  form.notes = ''
  formError.value = ''
  showModal.value = true
  loadBestSlot()
}

/**
 * 打开编辑弹窗
 */
function openEditModal(plan: PlanItem) {
  editingPlan.value = plan
  form.title = plan.title
  form.platform = plan.platform
  form.publish_date = plan.publish_date
  form.publish_time = plan.publish_time || ''
  form.status = plan.status
  form.notes = plan.notes
  formError.value = ''
  showModal.value = true
  loadBestSlot()
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
    publish_time: form.publish_time,
    status: form.status,
    notes: form.notes.trim()
  }

  // 保存前记录是否为「新流转到已发布」（弹窗保存也可能把状态改成已发布）
  const becamePublished = form.status === 'published'
    && (!editingPlan.value || editingPlan.value.status !== 'published')

  const res = editingPlan.value
    ? await updatePlan(editingPlan.value.id, payload)
    : await createPlan(payload)

  saving.value = false

  if (res.success) {
    successMessage.value = editingPlan.value ? '计划已更新' : '计划已添加'
    showModal.value = false
    await loadData()
    if (becamePublished && res.plan) openLogModal(res.plan)
  } else {
    formError.value = res.error_message || '保存失败，请重试'
  }
}

/**
 * 状态流转（列表视图内联下拉）
 * 流转为「已发布」时弹出转录到数据复盘的预填弹窗
 */
async function handleStatusChange(plan: PlanItem, status: PlanStatus) {
  if (status === plan.status || statusUpdatingId.value) return
  statusUpdatingId.value = plan.id
  const res = await updatePlan(plan.id, { status })
  statusUpdatingId.value = null

  if (res.success) {
    successMessage.value = `「${plan.title}」已流转为「${statusLabel(status)}」`
    await loadData()
    if (status === 'published') openLogModal(res.plan || plan)
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
 * 查看条目关联的历史作品（简单跳转到历史页）
 */
function viewLinkedRecord() {
  router.push('/history')
}

// ==================== 转录到数据复盘（发布闭环） ====================

/** 数值输入归一化：空串/NaN/负数 -> 0 */
function toSafeInt(value: unknown): number {
  const num = Number(value)
  if (!Number.isFinite(num) || num < 0) return 0
  return Math.floor(num)
}

const showLogModal = ref(false)
const logPlan = ref<PlanItem | null>(null)
const logSaving = ref(false)
const logError = ref('')

const logForm = reactive({
  title: '',
  platform: '',
  publish_date: '',
  publish_time: '',
  views: 0,
  likes: 0,
  collects: 0,
  comments: 0,
  shares: 0,
  followers_gained: 0
})

/** 标题、平台非空才允许提交（与数据复盘录入的必填约束一致） */
const canLogSubmit = computed(() =>
  logForm.title.trim().length > 0 && logForm.platform.trim().length > 0
)

/**
 * 打开转录弹窗：标题 / 平台（转中文名）/ 日期 / 时间从日历条目预填，
 * 用户只需补充播放、点赞等指标（也可跳过）。
 */
function openLogModal(plan: PlanItem) {
  logPlan.value = plan
  logForm.title = plan.title
  logForm.platform = platformLabel(plan.platform)
  logForm.publish_date = plan.publish_date
  logForm.publish_time = plan.publish_time || ''
  logForm.views = 0
  logForm.likes = 0
  logForm.collects = 0
  logForm.comments = 0
  logForm.shares = 0
  logForm.followers_gained = 0
  logError.value = ''
  showLogModal.value = true
}

function closeLogModal() {
  if (logSaving.value) return
  showLogModal.value = false
}

/**
 * 提交转录：调用后端一键转录端点，写入数据复盘并回写关联。
 * 同一条目重复转录时后端会更新已有关联记录（created 为 false）。
 */
async function handleLogSubmit() {
  if (!logPlan.value || logSaving.value || !canLogSubmit.value) return
  logSaving.value = true
  logError.value = ''

  const res = await logPlanPerformance(logPlan.value.id, {
    title: logForm.title.trim(),
    platform: logForm.platform.trim(),
    publish_date: logForm.publish_date,
    publish_time: logForm.publish_time,
    views: toSafeInt(logForm.views),
    likes: toSafeInt(logForm.likes),
    collects: toSafeInt(logForm.collects),
    comments: toSafeInt(logForm.comments),
    shares: toSafeInt(logForm.shares),
    followers_gained: toSafeInt(logForm.followers_gained)
  })

  logSaving.value = false

  if (res.success) {
    successMessage.value = res.created
      ? `「${logForm.title.trim()}」已转录到数据复盘`
      : `已更新数据复盘中「${logForm.title.trim()}」的关联记录`
    showLogModal.value = false
  } else {
    logError.value = res.error_message || '转录失败，请重试'
  }
}

// ==================== 热点节点图层 ====================

/** 图层开关（偏好持久化到 localStorage，默认开启） */
const hotspotLayerEnabled = ref(loadHotspotLayerEnabled())

/** 已拉取的节点（覆盖当前月历网格 + 未来 30 天） */
const hotspotNodes = ref<HotspotNode[]>([])

/** 按日期分组，供月历叠加图层渲染 */
const hotspotsByDate = computed(() => groupHotspotsByDate(hotspotNodes.value))

/** 未来 30 天的节点，按临近排序（侧栏区块） */
const upcomingNodes = computed(() => upcomingHotspots(hotspotNodes.value, todayDate, 30))

function toggleHotspotLayer() {
  hotspotLayerEnabled.value = !hotspotLayerEnabled.value
  saveHotspotLayerEnabled(hotspotLayerEnabled.value)
}

/**
 * 拉取节点数据：区间覆盖当前月历网格与未来 30 天。
 * 静态数据接口不依赖 AI 模型；拉取失败静默（不影响日历主功能）。
 */
async function loadHotspots() {
  const grid = calendarGridRange(currentMonth.value)
  const start = grid.start < todayDate ? grid.start : todayDate
  const upcomingEnd = addDays(todayDate, 30)
  const end = grid.end > upcomingEnd ? grid.end : upcomingEnd

  const res = await getHotspots({ start, end })
  if (res.success) {
    hotspotNodes.value = res.hotspots
  }
}

// ==================== 节点选题（调现有选题 API） ====================

/** 正在生成选题的节点 ID（同一时间只允许一个请求） */
const hotspotTopicGeneratingId = ref<string | null>(null)

/** 选题结果弹窗对应的节点（null 表示关闭） */
const hotspotTopicNode = ref<HotspotNode | null>(null)
const hotspotTopicIdeas = ref<TopicIdea[]>([])

/**
 * 为节点生成选题：把节点名称 + 平台侧重提示拼进选题请求。
 * 未配置模型等失败场景走页面现有的 ErrorCard 展示，不影响节点数据展示。
 */
async function handleHotspotTopics(node: HotspotNode) {
  if (hotspotTopicGeneratingId.value) return
  hotspotTopicGeneratingId.value = node.id
  error.value = null

  try {
    const res = await generateTopics({
      niche: buildHotspotTopicNiche(node),
      platform: '小红书'
    })

    if (res.success && res.topics?.length) {
      hotspotTopicIdeas.value = res.topics
      hotspotTopicNode.value = node
    } else {
      error.value = normalizeApiError(
        res.error || res.error_message || '生成节点选题失败',
        '生成节点选题失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成节点选题失败')
  } finally {
    hotspotTopicGeneratingId.value = null
  }
}

function closeHotspotTopicModal() {
  hotspotTopicNode.value = null
  hotspotTopicIdeas.value = []
}

/** 选中一条节点选题进入创作流程（与选题工具的「用这个选题创作」一致） */
function useHotspotTopic(idea: TopicIdea) {
  const lines = [idea.title]
  if (idea.angle.trim()) {
    lines.push(`切入角度：${idea.angle.trim()}`)
  }
  generatorStore.setTopic(lines.join('\n'))
  router.push({ name: 'home' })
}

// ==================== AI 一周排期 ====================

/** 预览条目（在预览列表中可勾选，默认全选） */
type AiPreviewItem = WeekPlanPreviewItem & { selected: boolean }

const showAiModal = ref(false)
const aiGenerating = ref(false)
const aiAdding = ref(false)
const aiError = ref('')
const aiPreview = ref<AiPreviewItem[]>([])
const aiAccountContextUsed = ref(false)

const aiForm = reactive<{
  niche: string
  platform: PlanPlatform
  frequency: number
  useAccountData: boolean
}>({
  niche: '',
  platform: 'xiaohongshu',
  frequency: 3,
  useAccountData: false
})

const aiSelectedCount = computed(() => aiPreview.value.filter(p => p.selected).length)

const canGenerateAi = computed(() => aiForm.niche.trim().length > 0 && !aiGenerating.value)

function openAiModal() {
  aiError.value = ''
  aiPreview.value = []
  aiAccountContextUsed.value = false
  showAiModal.value = true
}

function closeAiModal() {
  if (aiGenerating.value || aiAdding.value) return
  showAiModal.value = false
}

/**
 * 调用后端生成一周排期预览（不落盘）
 */
async function handleAiGenerate() {
  if (!canGenerateAi.value) return
  aiGenerating.value = true
  aiError.value = ''
  aiPreview.value = []

  const res = await generateWeekPlan({
    niche: aiForm.niche.trim(),
    platform: aiForm.platform,
    frequency: Math.min(7, Math.max(1, Math.round(aiForm.frequency) || 3)),
    use_account_data: aiForm.useAccountData
  })

  aiGenerating.value = false

  if (res.success && res.plans?.length) {
    aiPreview.value = res.plans.map(p => ({ ...p, selected: true }))
    aiAccountContextUsed.value = !!res.account_context_used
  } else {
    aiError.value = res.error_message || 'AI 排期生成失败，请重试'
  }
}

/**
 * 把勾选的预览条目逐条调现有创建接口落盘，然后刷新视图
 */
async function handleAiAddToCalendar() {
  const selected = aiPreview.value.filter(p => p.selected)
  if (selected.length === 0 || aiAdding.value) return

  aiAdding.value = true
  aiError.value = ''

  let created = 0
  let failedMessage = ''
  for (const item of selected) {
    const res = await createPlan({
      title: item.title,
      platform: item.platform,
      publish_date: item.publish_date,
      publish_time: item.publish_time,
      status: item.status,
      notes: item.notes
    })
    if (res.success) {
      created += 1
    } else if (!failedMessage) {
      failedMessage = res.error_message || '部分计划创建失败'
    }
  }

  aiAdding.value = false

  if (created > 0) {
    successMessage.value = failedMessage
      ? `已添加 ${created}/${selected.length} 条计划（${failedMessage}）`
      : `已添加 ${created} 条计划到日历`
    showAiModal.value = false
    await loadData()
  } else {
    aiError.value = failedMessage || '添加失败，请重试'
  }
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

// 月份切换时同步刷新节点图层数据；开关打开且尚无数据时补拉
watch(currentMonth, () => {
  if (hotspotLayerEnabled.value) loadHotspots()
})

watch(hotspotLayerEnabled, enabled => {
  if (enabled && hotspotNodes.value.length === 0) loadHotspots()
})

onMounted(() => {
  loadData()
  if (hotspotLayerEnabled.value) loadHotspots()
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
  padding: 16px 8px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-base), border-color var(--transition-base);
}

.stat-card:hover {
  box-shadow: var(--shadow-sm);
  border-color: var(--border-hover);
}

.stat-num {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: var(--tracking-tighter);
  color: var(--text-main);
  font-variant-numeric: tabular-nums;
}

.stat-label {
  font-size: 12px;
  color: var(--text-secondary);
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
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
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
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  overflow: hidden;
}

.view-toggle-btn {
  padding: 6px 14px;
  font-size: 13px;
  border: none;
  background: var(--bg-card);
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.view-toggle-btn:hover:not(.active) {
  background: var(--gray-1);
  color: var(--text-main);
}

.view-toggle-btn.active {
  background: var(--primary);
  color: white;
  font-weight: 600;
}

/* 加载骨架 */
.skeleton-panel {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
  pointer-events: none;
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
  color: var(--text-secondary);
  padding: 6px 0;
}

.day-cell {
  min-height: 88px;
  border: 1px solid var(--gray-2);
  border-radius: var(--radius-sm);
  padding: 6px;
  display: flex;
  flex-direction: column;
  gap: 4px;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast),
    box-shadow var(--transition-fast);
}

.day-cell:hover {
  border-color: var(--border-hover);
  background: var(--gray-0);
  box-shadow: var(--shadow-xs);
}

.day-cell.other-month {
  opacity: 0.35;
  cursor: default;
}

.day-cell.other-month:hover {
  border-color: var(--gray-2);
  background: transparent;
  box-shadow: none;
}

.day-cell.today {
  border-color: var(--primary);
  background: var(--primary-fade);
  box-shadow: inset 0 0 0 1px var(--primary);
}

.day-num {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  min-width: 20px;
  line-height: 20px;
}

.day-cell.today .day-num {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--primary);
  color: white;
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
  border-radius: var(--radius-xs);
  font-size: 12px;
  line-height: 1.5;
  text-align: left;
  cursor: pointer;
  background: var(--color-info-soft);
  color: var(--color-info);
  transition: filter var(--transition-fast), transform var(--transition-fast);
}

.plan-chip:hover {
  filter: brightness(0.96);
  transform: translateY(-1px);
}

.plan-chip:active {
  transform: translateY(0);
}

.chip-dot {
  width: 7px;
  height: 7px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  box-shadow: 0 0 0 1px rgba(255, 255, 255, 0.7);
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
  color: var(--text-placeholder);
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
  margin-bottom: 0;
}

.plan-row:hover {
  box-shadow: var(--shadow-hover);
  border-color: var(--border-hover);
  transform: translateY(-2px);
}

.plan-row-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  flex-shrink: 0;
  min-width: 64px;
  padding: 6px 8px;
  border-radius: var(--radius-sm);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
}

.date-day {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  line-height: 1.2;
  font-variant-numeric: tabular-nums;
}

.date-month {
  font-size: 11px;
  color: var(--text-secondary);
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
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
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
  color: var(--text-sub);
  padding: 2px 8px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--gray-0);
}

.plan-notes {
  font-size: 12px;
  color: var(--text-secondary);
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
  border-radius: var(--radius-full);
  font-weight: 600;
  padding: 5px 10px;
  cursor: pointer;
}

.btn-mini {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  cursor: pointer;
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

.plan-modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 520px;
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
  .plan-modal-overlay,
  .plan-modal {
    animation: none;
  }
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
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.plan-modal-foot .btn {
  border: 1px solid var(--border-color);
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

/* 转录到数据复盘弹窗的提示文案 */
.log-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-sub);
}

.status-radio-group {
  display: flex;
  gap: 8px;
  flex-wrap: wrap;
}

.status-radio {
  padding: 6px 14px;
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  font-size: 13px;
  font-weight: 600;
  cursor: pointer;
  opacity: 0.55;
  transition: opacity var(--transition-fast), box-shadow var(--transition-fast);
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

/* 月历 chip 上的发布时间 */
.chip-time {
  flex-shrink: 0;
  font-size: 11px;
  font-weight: 600;
  font-variant-numeric: tabular-nums;
  opacity: 0.85;
}

/* 列表行的发布时间 */
.plan-time {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  font-size: 12px;
  color: var(--text-sub);
  font-variant-numeric: tabular-nums;
}

/* 「查看作品」小链接 */
.record-link {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  flex-shrink: 0;
  padding: 0;
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--primary);
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.record-link:hover {
  opacity: 0.75;
  text-decoration: underline;
}

/* 最佳时段推荐提示（可点击填入） */
.slot-hint {
  align-self: flex-start;
  padding: 0;
  border: none;
  background: transparent;
  font-size: 12px;
  color: var(--text-sub);
  cursor: pointer;
  text-align: left;
  transition: color var(--transition-fast);
}

.slot-hint:hover {
  color: var(--primary);
  text-decoration: underline;
}

/* 工具栏「AI 排期」按钮 */
.btn-ai {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  color: var(--primary);
  border-color: var(--primary) !important;
}

.btn-ai:hover {
  background: var(--primary-light);
}

/* AI 排期弹窗 */
.ai-modal {
  max-width: 560px;
}

.ai-switch {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-main);
  cursor: pointer;
}

.ai-switch input {
  accent-color: var(--primary);
}

.ai-preview-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  margin-top: 4px;
}

.ai-context-badge {
  font-size: 11px;
  font-weight: 600;
  color: var(--color-success);
  background: var(--color-success-soft);
  padding: 2px 8px;
  border-radius: var(--radius-full);
}

.ai-preview-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.ai-preview-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-0);
  cursor: pointer;
  transition: border-color var(--transition-fast), opacity var(--transition-fast);
}

.ai-preview-item:hover {
  border-color: var(--border-hover);
}

.ai-preview-item.unchecked {
  opacity: 0.55;
}

.ai-preview-item input {
  margin-top: 3px;
  accent-color: var(--primary);
  flex-shrink: 0;
}

.ai-preview-main {
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.ai-preview-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.ai-preview-meta {
  display: flex;
  gap: 10px;
  font-size: 12px;
  color: var(--text-sub);
  font-variant-numeric: tabular-nums;
}

.ai-preview-notes {
  font-size: 12px;
  color: var(--text-secondary);
}

/* ==================== 热点节点图层 ==================== */

/* 工具栏「节点图层」开关按钮 */
.hotspot-toggle {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

.hotspot-toggle.active {
  color: var(--color-danger);
  border-color: var(--color-danger) !important;
  background: var(--color-danger-soft);
}

/* 月历格子上的节点标记（虚线边框色条，与实心的计划 chip 视觉区分） */
.day-hotspots {
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.hotspot-mark {
  display: inline-block;
  max-width: 100%;
  padding: 1px 6px;
  border: 1px dashed currentColor;
  border-radius: var(--radius-xs);
  font-size: 11px;
  font-weight: 600;
  line-height: 1.5;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-festival { color: var(--color-danger); background: var(--color-danger-soft); }
.hotspot-ecommerce { color: var(--color-warning); background: var(--color-warning-soft); }
.hotspot-season { color: var(--color-success); background: var(--color-success-soft); }

/* 即将到来的节点区块 */
.hotspot-upcoming {
  padding: 16px;
  margin-bottom: 40px;
}

.hotspot-upcoming-head {
  display: flex;
  justify-content: space-between;
  align-items: baseline;
  gap: 8px;
  flex-wrap: wrap;
  margin-bottom: 12px;
}

.hotspot-upcoming-title {
  display: inline-flex;
  align-items: center;
  gap: 6px;
  margin: 0;
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.hotspot-upcoming-title svg {
  color: var(--color-danger);
}

.hotspot-upcoming-sub {
  font-size: 12px;
  color: var(--text-secondary);
}

.hotspot-node-list {
  display: flex;
  flex-direction: column;
  gap: 10px;
}

.hotspot-node-row {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-0);
}

.hotspot-node-date {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 2px;
  flex-shrink: 0;
  min-width: 72px;
}

.hotspot-node-countdown {
  font-size: 13px;
  font-weight: 700;
  color: var(--color-danger);
  white-space: nowrap;
}

.hotspot-node-day {
  font-size: 11px;
  color: var(--text-secondary);
  font-variant-numeric: tabular-nums;
}

.hotspot-node-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.hotspot-node-title {
  display: flex;
  align-items: center;
  gap: 8px;
  flex-wrap: wrap;
}

.hotspot-node-name {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.hotspot-node-prep {
  font-size: 12px;
  color: var(--text-sub);
}

.hotspot-node-hint,
.hotspot-node-niche {
  font-size: 12px;
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.hotspot-node-actions {
  flex-shrink: 0;
}

/* 节点选题结果弹窗 */
.hotspot-topic-list {
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.hotspot-topic-item {
  display: flex;
  align-items: center;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-0);
}

.hotspot-topic-main {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 3px;
}

.hotspot-topic-title {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.hotspot-topic-angle {
  font-size: 12px;
  color: var(--text-secondary);
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

  /* 移动端月历格子里节点名太长，缩成小圆点色标 */
  .day-cell .hotspot-mark {
    padding: 0;
    width: 8px;
    height: 8px;
    border-radius: var(--radius-full);
    align-self: center;
    font-size: 0;
  }

  .hotspot-node-row {
    flex-wrap: wrap;
    gap: 8px;
  }

  .hotspot-node-main {
    flex-basis: calc(100% - 90px);
  }

  .hotspot-node-actions {
    width: 100%;
    display: flex;
    justify-content: flex-end;
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

  .form-grid.three {
    grid-template-columns: 1fr 1fr;
  }

  .plan-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .plan-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
}
</style>
