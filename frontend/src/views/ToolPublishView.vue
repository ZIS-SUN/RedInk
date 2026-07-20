<template>
  <div class="container publish-page">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">发布助手</h1>
        <p class="page-subtitle">管理多平台账号，一键备好图文，去各平台手动发布</p>
      </div>
    </div>

    <!-- 安全说明：半自动定位，让用户放心且知情 -->
    <div class="safety-note" role="note">
      <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 22s8-4 8-10V5l-8-3-8 3v7c0 6 8 10 8 10z"></path></svg>
      <span>发布助手不会保存你的账号密码，也不会自动操作你的账号；它只帮你备好图片和文案，发布由你在官网手动完成，安全无封号风险。</span>
    </div>

    <ErrorCard
      v-if="pageError"
      :error="pageError"
      dismissible
      style="margin-bottom: 16px;"
      @dismiss="pageError = null"
      @retry="loadPage"
    />

    <!-- ==================== 区块 1：账号清单 ==================== -->
    <section class="card section-card">
      <div class="section-head">
        <div>
          <h2 class="section-title">1 · 账号清单</h2>
          <p class="section-sub">记录你在各平台的账号昵称与备注，仅作为清单标签，不含任何登录信息</p>
        </div>
        <button type="button" class="btn btn-primary" @click="openAccountModal()">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          添加账号
        </button>
      </div>

      <div v-if="accountsLoading" class="section-loading" aria-hidden="true">
        <div class="spinner"></div>
        <span>加载账号中...</span>
      </div>

      <div v-else-if="accounts.length === 0" class="empty-block">
        <p class="empty-text">还没有账号，把你在各平台的账号昵称记进来，备料后就知道该去哪儿发</p>
        <button type="button" class="btn btn-primary" @click="openAccountModal()">添加第一个账号</button>
      </div>

      <ul v-else class="account-list">
        <li v-for="account in accounts" :key="account.id" class="account-item">
          <span class="platform-badge" :class="`tone-${platformMeta(account.platform).tone}`">
            {{ platformMeta(account.platform).label }}
          </span>
          <div class="account-body">
            <span class="account-nickname">{{ account.nickname }}</span>
            <span v-if="account.notes" class="account-notes">{{ account.notes }}</span>
          </div>
          <div class="account-actions">
            <button type="button" class="btn btn-mini" :aria-label="`编辑「${account.nickname}」`" @click="openAccountModal(account)">编辑</button>
            <button type="button" class="btn btn-mini btn-danger" :aria-label="`删除「${account.nickname}」`" @click="deleteTarget = account">删除</button>
          </div>
        </li>
      </ul>
    </section>

    <!-- ==================== 区块 2：选作品备料 ==================== -->
    <section class="card section-card">
      <div class="section-head">
        <div>
          <h2 class="section-title">2 · 选作品备料</h2>
          <p class="section-sub">选一个已完成的作品，把图片导出到本地文件夹、文案备好随时复制</p>
        </div>
      </div>

      <div v-if="recordsLoading" class="section-loading" aria-hidden="true">
        <div class="spinner"></div>
        <span>加载作品中...</span>
      </div>

      <div v-else-if="readyRecords.length === 0" class="empty-block">
        <p class="empty-text">还没有已完成的作品。先去创作一篇图文，生成完成后就能在这里备料</p>
        <RouterLink to="/" class="btn btn-primary">去创作</RouterLink>
      </div>

      <template v-else>
        <div class="record-grid" role="radiogroup" aria-label="选择作品">
          <button
            v-for="record in readyRecords"
            :key="record.id"
            type="button"
            class="record-card"
            :class="{ selected: selectedRecordId === record.id }"
            role="radio"
            :aria-checked="selectedRecordId === record.id"
            @click="selectRecord(record.id)"
          >
            <img
              :src="`/api/images/${record.task_id}/${record.thumbnail}`"
              alt=""
              loading="lazy"
              class="record-thumb"
            />
            <span class="record-title" :title="record.title">{{ record.title }}</span>
            <span class="record-meta">{{ record.page_count }} 页</span>
          </button>
        </div>

        <div class="prepare-bar">
          <button
            type="button"
            class="btn btn-primary"
            :disabled="!selectedRecordId || preparing"
            @click="handlePrepare"
          >
            {{ preparing ? '备料中...' : '一键备好发布物料' }}
          </button>
          <span v-if="!selectedRecordId" class="prepare-hint">先在上方选择一个作品</span>
        </div>

        <ErrorCard
          v-if="prepareError"
          :error="prepareError"
          dismissible
          style="margin-top: 16px;"
          @dismiss="prepareError = null"
          @retry="handlePrepare"
        />

        <!-- 备料结果 -->
        <div v-if="prepared" class="prepare-result">
          <div class="result-files">
            <div class="result-files-info">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M22 19a2 2 0 0 1-2 2H4a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h5l2 3h9a2 2 0 0 1 2 2z"></path></svg>
              <div>
                <div class="result-files-title">图片已导出到本地文件夹（{{ fileCountLabel(prepared.files) }}）</div>
                <div class="result-files-path" :title="prepared.folder">{{ prepared.folder }}</div>
              </div>
            </div>
            <button type="button" class="btn" :disabled="openingFolder" @click="handleOpenFolder">
              {{ openingFolder ? '打开中...' : '打开文件夹' }}
            </button>
          </div>

          <p v-if="missingParts.length" class="text-warning" role="status">
            注意：该作品缺少{{ missingParts.join('、') }}，可回到作品页补全后重新备料
          </p>

          <div class="text-blocks">
            <div class="text-block">
              <div class="text-block-head">
                <h3>标题候选</h3>
                <button type="button" class="copy-btn" :class="{ copied: copiedBlock === 'titles' }" @click="copyBlock('titles')">
                  {{ copiedBlock === 'titles' ? '已复制' : '复制' }}
                </button>
              </div>
              <p v-if="prepared.text.titles.length === 0" class="text-block-empty">暂无标题</p>
              <ul v-else class="titles-list">
                <li v-for="(title, i) in prepared.text.titles" :key="i">{{ title }}</li>
              </ul>
            </div>

            <div class="text-block">
              <div class="text-block-head">
                <h3>正文</h3>
                <button type="button" class="copy-btn" :class="{ copied: copiedBlock === 'copywriting' }" @click="copyBlock('copywriting')">
                  {{ copiedBlock === 'copywriting' ? '已复制' : '复制' }}
                </button>
              </div>
              <p v-if="!prepared.text.copywriting.trim()" class="text-block-empty">暂无正文</p>
              <p v-else class="copywriting-text">{{ prepared.text.copywriting }}</p>
            </div>

            <div class="text-block">
              <div class="text-block-head">
                <h3>标签</h3>
                <button type="button" class="copy-btn" :class="{ copied: copiedBlock === 'tags' }" @click="copyBlock('tags')">
                  {{ copiedBlock === 'tags' ? '已复制' : '复制' }}
                </button>
              </div>
              <p v-if="prepared.text.tags.length === 0" class="text-block-empty">暂无标签</p>
              <div v-else class="tags-row">
                <span v-for="(tag, i) in prepared.text.tags" :key="i" class="tag-chip">#{{ tag }}</span>
              </div>
            </div>
          </div>
        </div>
      </template>
    </section>

    <!-- ==================== 区块 3：去平台发布 ==================== -->
    <section class="card section-card">
      <div class="section-head">
        <div>
          <h2 class="section-title">3 · 去平台发布</h2>
          <p class="section-sub">打开各平台创作者发布页，拖入图片、粘贴文案，由你手动完成发布</p>
        </div>
      </div>

      <!-- 四步引导 -->
      <ol class="steps-guide">
        <li v-for="(step, i) in guideSteps" :key="i" class="step-card">
          <span class="step-num">{{ i + 1 }}</span>
          <span class="step-text">{{ step }}</span>
        </li>
      </ol>

      <div v-if="platformsLoading" class="section-loading" aria-hidden="true">
        <div class="spinner"></div>
        <span>加载平台中...</span>
      </div>

      <div v-else-if="platforms.length === 0" class="empty-block">
        <p class="empty-text">暂未获取到平台列表，请稍后重试</p>
        <button type="button" class="btn" @click="loadPage">重新加载</button>
      </div>

      <div v-else class="platform-grid">
        <button
          v-for="platform in platforms"
          :key="platform.key"
          type="button"
          class="platform-open-btn"
          @click="openCreatorPage(platform)"
        >
          <span class="platform-badge" :class="`tone-${platformMeta(platform.key, platform.label).tone}`">
            {{ platformMeta(platform.key, platform.label).label }}
          </span>
          <span class="platform-open-text">打开创作者发布页</span>
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path><polyline points="15 3 21 3 21 9"></polyline><line x1="10" y1="14" x2="21" y2="3"></line></svg>
        </button>
      </div>
    </section>

    <!-- 添加/编辑账号弹窗 -->
    <Teleport to="body">
      <div v-if="showAccountModal" class="publish-modal-overlay" @click.self="closeAccountModal">
        <div class="publish-modal" role="dialog" aria-modal="true" :aria-label="editingAccount ? '编辑账号' : '添加账号'">
          <div class="publish-modal-head">
            <h3>{{ editingAccount ? '编辑账号' : '添加账号' }}</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeAccountModal">×</button>
          </div>

          <div class="publish-modal-body">
            <div class="form-field">
              <label for="publish-platform">平台 <span class="required">*</span></label>
              <select id="publish-platform" v-model="accountForm.platform" class="input">
                <option value="" disabled>选择平台</option>
                <option v-for="platform in platforms" :key="platform.key" :value="platform.key">
                  {{ platform.label }}
                </option>
              </select>
            </div>
            <div class="form-field">
              <label for="publish-nickname">昵称 <span class="required">*</span></label>
              <input
                id="publish-nickname"
                v-model="accountForm.nickname"
                class="input"
                type="text"
                placeholder="如：小红书主号 / 深夜护肤日记"
                maxlength="50"
              />
            </div>
            <div class="form-field">
              <label for="publish-notes">备注</label>
              <textarea
                id="publish-notes"
                v-model="accountForm.notes"
                class="input"
                rows="2"
                placeholder="如：主发干货教程，周三周五更新（可选）"
                maxlength="200"
              ></textarea>
            </div>
            <p v-if="accountFormError" class="form-error" role="alert">{{ accountFormError }}</p>
          </div>

          <div class="publish-modal-foot">
            <button type="button" class="btn" @click="closeAccountModal">取消</button>
            <button type="button" class="btn btn-primary" :disabled="savingAccount || !canSaveAccount" @click="handleSaveAccount">
              {{ savingAccount ? '保存中...' : '保存' }}
            </button>
          </div>
        </div>
      </div>
    </Teleport>

    <!-- 删除账号二次确认 -->
    <ConfirmDialog
      :visible="!!deleteTarget"
      title="删除这个账号？"
      :message="deleteMessage"
      confirm-text="删除"
      danger
      @confirm="doDeleteAccount"
      @cancel="deleteTarget = null"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import { RouterLink } from 'vue-router'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import { getHistoryList } from '../api/history'
import {
  createPublishAccount,
  deletePublishAccount,
  getPublishAccounts,
  getPublishPlatforms,
  openPublishFolder,
  preparePublishMaterial,
  updatePublishAccount,
  type PublishAccount,
  type PublishPlatform,
  type PublishPrepareResult
} from '../api/publish'
import type { HistoryRecord } from '../api/types'
import { fileCountLabel, getPlatformMeta, missingTextParts } from '../utils/publishHelper'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 发布助手（半自动）：
 * - 账号清单：只记录平台 + 昵称 + 备注，不存密码、不自动登录
 * - 选作品备料：把已完成作品的图片导出到本地文件夹、文案备好一键复制
 * - 去平台发布：打开各平台创作者页，由用户手动拖图、粘贴、发布
 */

// ==================== 页面级状态 ====================
const pageError = ref<AppError | null>(null)

// 账号清单
const accounts = ref<PublishAccount[]>([])
const accountsLoading = ref(false)

// 平台列表（账号弹窗下拉 + 区块 3 共用）
const platforms = ref<PublishPlatform[]>([])
const platformsLoading = ref(false)

// 作品列表
const records = ref<HistoryRecord[]>([])
const recordsLoading = ref(false)
const selectedRecordId = ref('')

// 备料状态
const preparing = ref(false)
const prepareError = ref<AppError | null>(null)
const prepared = ref<PublishPrepareResult | null>(null)
const openingFolder = ref(false)

/** 平台 key → 展示信息（后端 label 优先，未知 key 安全回退） */
function platformMeta(key: string, backendLabel?: string) {
  const fromList = platforms.value.find(p => p.key === key)
  return getPlatformMeta(key, backendLabel ?? fromList?.label)
}

/** 可备料的作品：已完成且有缩略图（即有已生成的图片） */
const readyRecords = computed(() =>
  records.value.filter(r => r.status === 'completed' && r.thumbnail && r.task_id)
)

/** 备料结果缺失的文案块 */
const missingParts = computed(() => prepared.value ? missingTextParts(prepared.value.text) : [])

const guideSteps = [
  '备好物料：选作品导出图片',
  '复制文案：标题 / 正文 / 标签',
  '打开创作者页：跳到官网',
  '拖入图片、粘贴文案，手动发布'
]

// ==================== 数据加载 ====================
async function loadPage() {
  pageError.value = null
  accountsLoading.value = true
  platformsLoading.value = true
  recordsLoading.value = true

  const [accountsRes, platformsRes, historyRes] = await Promise.all([
    getPublishAccounts(),
    getPublishPlatforms(),
    getHistoryList(1, 20)
  ])

  accountsLoading.value = false
  platformsLoading.value = false
  recordsLoading.value = false

  if (accountsRes.success) {
    accounts.value = accountsRes.accounts
  } else {
    pageError.value = normalizeApiError(accountsRes.error || accountsRes.error_message || '获取账号列表失败', '获取账号列表失败')
  }

  if (platformsRes.success) {
    platforms.value = platformsRes.platforms
  } else if (!pageError.value) {
    pageError.value = normalizeApiError(platformsRes.error || platformsRes.error_message || '获取平台列表失败', '获取平台列表失败')
  }

  if (historyRes.success) {
    records.value = historyRes.records
  } else if (!pageError.value) {
    pageError.value = normalizeApiError(historyRes.error || historyRes.error_message || '获取作品列表失败', '获取作品列表失败')
  }
}

onMounted(loadPage)

// ==================== 账号 CRUD ====================
const showAccountModal = ref(false)
const editingAccount = ref<PublishAccount | null>(null)
const savingAccount = ref(false)
const accountFormError = ref('')

const accountForm = reactive({
  platform: '',
  nickname: '',
  notes: ''
})

const canSaveAccount = computed(
  () => accountForm.platform.trim().length > 0 && accountForm.nickname.trim().length > 0
)

function openAccountModal(account?: PublishAccount) {
  editingAccount.value = account ?? null
  accountForm.platform = account?.platform ?? ''
  accountForm.nickname = account?.nickname ?? ''
  accountForm.notes = account?.notes ?? ''
  accountFormError.value = ''
  showAccountModal.value = true
}

function closeAccountModal() {
  showAccountModal.value = false
}

async function handleSaveAccount() {
  if (!canSaveAccount.value || savingAccount.value) return
  savingAccount.value = true
  accountFormError.value = ''

  const payload = {
    platform: accountForm.platform.trim(),
    nickname: accountForm.nickname.trim(),
    notes: accountForm.notes.trim()
  }

  const result = editingAccount.value
    ? await updatePublishAccount(editingAccount.value.id, payload)
    : await createPublishAccount(payload)

  savingAccount.value = false

  if (result.success && result.account) {
    if (editingAccount.value) {
      const index = accounts.value.findIndex(a => a.id === editingAccount.value!.id)
      if (index !== -1) accounts.value[index] = result.account
    } else {
      accounts.value.push(result.account)
    }
    showAccountModal.value = false
  } else {
    accountFormError.value = normalizeApiError(
      result.error || result.error_message || '保存失败',
      '保存失败'
    ).detail || '保存失败，请重试'
  }
}

// 删除（二次确认）
const deleteTarget = ref<PublishAccount | null>(null)

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  const meta = platformMeta(deleteTarget.value.platform)
  return `${meta.label} · 「${deleteTarget.value.nickname}」删除后无法恢复（只删除清单记录，不影响你的平台账号）。`
})

async function doDeleteAccount() {
  const target = deleteTarget.value
  if (!target) return
  deleteTarget.value = null

  const result = await deletePublishAccount(target.id)
  if (result.success) {
    accounts.value = accounts.value.filter(a => a.id !== target.id)
  } else {
    pageError.value = normalizeApiError(result.error || result.error_message || '删除账号失败', '删除账号失败')
  }
}

// ==================== 备料 ====================
function selectRecord(id: string) {
  selectedRecordId.value = id
  // 换作品后旧的备料结果不再对应，清掉避免误导
  prepared.value = null
  prepareError.value = null
}

async function handlePrepare() {
  if (!selectedRecordId.value || preparing.value) return
  preparing.value = true
  prepareError.value = null
  prepared.value = null

  const result = await preparePublishMaterial(selectedRecordId.value)
  preparing.value = false

  if (result.success && result.folder && result.text) {
    prepared.value = {
      folder: result.folder,
      files: result.files ?? [],
      text: {
        titles: result.text.titles ?? [],
        copywriting: result.text.copywriting ?? '',
        tags: result.text.tags ?? []
      }
    }
  } else {
    prepareError.value = normalizeApiError(result.error || result.error_message || '备料失败', '备料失败')
  }
}

async function handleOpenFolder() {
  if (!prepared.value || openingFolder.value) return
  openingFolder.value = true
  const result = await openPublishFolder(prepared.value.folder)
  openingFolder.value = false
  if (!result.success) {
    prepareError.value = normalizeApiError(result.error || result.error_message || '打开文件夹失败', '打开文件夹失败')
  }
}

// ==================== 复制（与 ContentDisplay 一致：clipboard API + execCommand 降级） ====================
type CopyBlock = 'titles' | 'copywriting' | 'tags'
const copiedBlock = ref<CopyBlock | null>(null)
let copyTimer: number | null = null

onUnmounted(() => {
  if (copyTimer !== null) clearTimeout(copyTimer)
})

async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // 降级方案：pywebview / 非安全上下文中 clipboard API 可能不可用
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      return true
    } catch {
      return false
    } finally {
      document.body.removeChild(textarea)
    }
  }
}

async function copyBlock(block: CopyBlock) {
  if (!prepared.value) return
  const text = prepared.value.text
  const content = block === 'titles'
    ? text.titles.join('\n')
    : block === 'copywriting'
      ? text.copywriting
      : text.tags.map(t => `#${t}`).join(' ')

  if (await copyToClipboard(content)) {
    copiedBlock.value = block
    if (copyTimer !== null) clearTimeout(copyTimer)
    copyTimer = window.setTimeout(() => {
      copiedBlock.value = null
      copyTimer = null
    }, 2000)
  }
}

// ==================== 打开创作者页 ====================
function openCreatorPage(platform: PublishPlatform) {
  // 桌面 pywebview 环境 window.open 同样会拉起系统浏览器
  window.open(platform.creator_url, '_blank', 'noopener')
}
</script>

<style scoped>
.publish-page {
  max-width: 1000px;
  padding-bottom: var(--space-8);
}

/* 安全说明 */
.safety-note {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  padding: var(--space-4);
  margin-bottom: var(--space-5);
  border-radius: var(--radius-lg);
  background: var(--color-success-soft);
  color: var(--color-success);
  font-size: var(--font-size-caption);
  line-height: 1.6;
}

.safety-note svg {
  flex-shrink: 0;
  margin-top: 2px;
}

/* 区块卡片 */
.section-card {
  padding: var(--space-5);
  margin-bottom: var(--space-5);
}

.section-head {
  display: flex;
  align-items: flex-start;
  justify-content: space-between;
  gap: var(--space-4);
  margin-bottom: var(--space-4);
  flex-wrap: wrap;
}

.section-title {
  margin: 0 0 4px;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.section-sub {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  line-height: 1.5;
}

.section-loading {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-5) 0;
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}

/* 空态 */
.empty-block {
  text-align: center;
  padding: var(--space-6) var(--space-4);
}

.empty-text {
  margin: 0 0 var(--space-4);
  font-size: var(--font-size-body);
  color: var(--text-sub);
  line-height: 1.6;
}

/* 账号列表 */
.account-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.account-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.account-item:hover {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-xs);
}

/* 平台徽标：不同平台不同 -soft 底色 */
.platform-badge {
  flex-shrink: 0;
  display: inline-flex;
  align-items: center;
  padding: 3px 10px;
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  white-space: nowrap;
}

.platform-badge.tone-primary { background: var(--primary-light); color: var(--primary); }
.platform-badge.tone-info { background: var(--color-info-soft); color: var(--color-info); }
.platform-badge.tone-success { background: var(--color-success-soft); color: var(--color-success); }
.platform-badge.tone-warning { background: var(--color-warning-soft); color: var(--color-warning); }
.platform-badge.tone-danger { background: var(--color-danger-soft); color: var(--color-danger); }
.platform-badge.tone-neutral { background: var(--gray-2); color: var(--gray-7); }

.account-body {
  flex: 1;
  min-width: 0;
  display: flex;
  align-items: baseline;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.account-nickname {
  font-size: var(--font-size-body);
  font-weight: 600;
  color: var(--text-main);
}

.account-notes {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
  max-width: 100%;
}

.account-actions {
  flex-shrink: 0;
  display: flex;
  gap: var(--space-2);
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

/* 作品选择 */
.record-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(140px, 1fr));
  gap: var(--space-3);
}

.record-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
  padding: var(--space-2);
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  cursor: pointer;
  text-align: left;
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.record-card:hover {
  border-color: var(--border-hover);
  transform: translateY(-2px);
  box-shadow: var(--shadow-sm);
}

.record-card.selected {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.record-thumb {
  width: 100%;
  aspect-ratio: 3 / 4;
  object-fit: cover;
  border-radius: var(--radius-sm);
  background: var(--gray-2);
}

.record-title {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.4;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.record-meta {
  font-size: 12px;
  color: var(--text-secondary);
}

.prepare-bar {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-top: var(--space-4);
  flex-wrap: wrap;
}

.prepare-hint {
  font-size: var(--font-size-caption);
  color: var(--text-placeholder);
}

/* 备料结果 */
.prepare-result {
  margin-top: var(--space-5);
  padding-top: var(--space-5);
  border-top: 1px solid var(--border-color);
}

.result-files {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-4);
  padding: var(--space-4);
  border-radius: var(--radius-md);
  background: var(--color-success-soft);
  flex-wrap: wrap;
}

.result-files-info {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
  color: var(--color-success);
  min-width: 0;
}

.result-files-info svg { flex-shrink: 0; margin-top: 2px; }

.result-files-title {
  font-size: var(--font-size-body);
  font-weight: 600;
  color: var(--text-main);
}

.result-files-path {
  font-size: 12px;
  font-family: var(--font-mono);
  color: var(--text-secondary);
  margin-top: 2px;
  word-break: break-all;
}

.text-warning {
  margin: var(--space-3) 0 0;
  font-size: var(--font-size-caption);
  color: var(--color-warning);
}

.text-blocks {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.text-block {
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: var(--space-4);
}

.text-block-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-3);
}

.text-block-head h3 {
  margin: 0;
  font-size: var(--font-size-body);
  font-weight: 600;
  color: var(--text-main);
}

.text-block-empty {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--text-placeholder);
}

.copy-btn {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  padding: 5px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--gray-0);
  color: var(--text-sub);
  font-size: 12px;
  font-weight: 600;
  font-family: inherit;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.copy-btn:hover {
  background: var(--bg-card);
  color: var(--text-main);
  border-color: var(--border-hover);
}

.copy-btn.copied {
  background: var(--color-success-soft);
  color: var(--color-success);
  border-color: var(--color-success);
}

.titles-list {
  margin: 0;
  padding-left: 20px;
  display: flex;
  flex-direction: column;
  gap: var(--space-1);
}

.titles-list li {
  font-size: var(--font-size-body);
  color: var(--text-main);
  line-height: 1.6;
}

.copywriting-text {
  margin: 0;
  font-size: var(--font-size-body);
  color: var(--text-main);
  line-height: 1.7;
  white-space: pre-wrap;
  word-break: break-word;
}

.tags-row {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.tag-chip {
  padding: 4px 10px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  color: var(--gray-7);
  font-size: var(--font-size-caption);
  font-weight: 500;
}

/* 四步引导 */
.steps-guide {
  list-style: none;
  margin: 0 0 var(--space-4);
  padding: 0;
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(180px, 1fr));
  gap: var(--space-3);
}

.step-card {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--gray-0);
}

.step-num {
  flex-shrink: 0;
  width: 24px;
  height: 24px;
  border-radius: var(--radius-full);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
}

.step-text {
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  line-height: 1.5;
}

/* 平台按钮 */
.platform-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(220px, 1fr));
  gap: var(--space-3);
}

.platform-open-btn {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--bg-card);
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
  color: var(--text-sub);
}

.platform-open-btn:hover {
  border-color: var(--border-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.platform-open-btn:active {
  transform: translateY(0);
  box-shadow: none;
}

.platform-open-text {
  flex: 1;
  text-align: left;
  font-size: var(--font-size-caption);
  font-weight: 500;
}

/* 弹窗（结构与 ConfirmDialog / 其他工具页弹窗保持一致的视觉语言） */
.publish-modal-overlay {
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
  animation: publish-fade 0.2s var(--ease-out);
}

.publish-modal {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  width: 100%;
  max-width: 440px;
  max-height: 90vh;
  overflow-y: auto;
  box-shadow: var(--shadow-lg);
  animation: publish-pop 0.2s var(--ease-out);
}

@keyframes publish-fade {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes publish-pop {
  from { opacity: 0; transform: scale(0.96) translateY(10px); }
  to { opacity: 1; transform: scale(1) translateY(0); }
}

@media (prefers-reduced-motion: reduce) {
  .publish-modal-overlay,
  .publish-modal {
    animation: none;
  }
  .record-card,
  .platform-open-btn {
    transition: none;
  }
}

.publish-modal-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  padding: var(--space-5) var(--space-5) 0;
}

.publish-modal-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.close-btn {
  border: none;
  background: none;
  font-size: 22px;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
  padding: 4px 8px;
  border-radius: var(--radius-sm);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.close-btn:hover {
  background: var(--gray-2);
  color: var(--text-main);
}

.publish-modal-body {
  padding: var(--space-4) var(--space-5);
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.form-field label {
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-sub);
}

.required { color: var(--primary); }

.form-error {
  margin: 0;
  font-size: var(--font-size-caption);
  color: var(--color-danger);
}

.publish-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  padding: 0 var(--space-5) var(--space-5);
}

/* 移动端 */
@media (max-width: 640px) {
  .section-card { padding: var(--space-4); }
  .section-head { flex-direction: column; align-items: stretch; }
  .section-head .btn { width: 100%; }
  .account-item { flex-wrap: wrap; }
  .account-actions { width: 100%; justify-content: flex-end; }
  .record-grid { grid-template-columns: repeat(2, 1fr); }
  .result-files { flex-direction: column; align-items: stretch; }
  .prepare-bar .btn { width: 100%; }
  .steps-guide { grid-template-columns: 1fr; }
  .platform-grid { grid-template-columns: 1fr; }
}
</style>
