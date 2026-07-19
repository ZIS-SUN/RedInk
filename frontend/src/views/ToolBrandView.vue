<template>
  <div class="container" style="max-width: 1000px;">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">品牌记忆</h1>
        <p class="page-subtitle">管理你的个人 IP / 品牌档案，让文案始终保持统一人设</p>
      </div>
      <button type="button" class="btn btn-primary" @click="openCreateModal">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
        新建档案
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
    <div v-else-if="brands.length === 0" class="empty-state-large">
      <div class="empty-img">
        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
      </div>
      <h3>还没有品牌档案</h3>
      <p class="empty-tips">创建一个档案，记录你的人设定位、语气风格和常用话术</p>
      <button type="button" class="btn btn-primary" style="margin-top: 16px;" @click="openCreateModal">立即创建</button>
    </div>

    <!-- 档案列表 -->
    <div v-else class="brand-grid">
      <div
        v-for="brand in brands"
        :key="brand.id"
        class="card brand-card"
        :class="{ active: brand.id === activeId }"
      >
        <div class="brand-card-head">
          <span
            class="color-dot"
            :style="{ background: brand.primary_color || 'var(--border-hover)' }"
            :title="brand.primary_color || '未设置主色调'"
          ></span>
          <h3 class="brand-name">{{ brand.name }}</h3>
          <span v-if="brand.id === activeId" class="active-badge">当前启用</span>
        </div>

        <p v-if="brand.tagline" class="brand-tagline">{{ brand.tagline }}</p>

        <div class="brand-meta">
          <div v-if="brand.tone" class="meta-row">
            <span class="meta-label">语气风格</span>
            <span class="meta-value">{{ brand.tone }}</span>
          </div>
          <div v-if="brand.audience" class="meta-row">
            <span class="meta-label">目标人群</span>
            <span class="meta-value">{{ brand.audience }}</span>
          </div>
          <div v-if="brand.catchphrases.length" class="meta-row">
            <span class="meta-label">口头禅</span>
            <span class="meta-value">{{ brand.catchphrases.slice(0, 3).join(' / ') }}<template v-if="brand.catchphrases.length > 3"> 等 {{ brand.catchphrases.length }} 条</template></span>
          </div>
          <div v-if="brand.banned_words.length" class="meta-row">
            <span class="meta-label">禁用词</span>
            <span class="meta-value danger-text">{{ brand.banned_words.slice(0, 5).join('、') }}<template v-if="brand.banned_words.length > 5"> 等 {{ brand.banned_words.length }} 个</template></span>
          </div>
        </div>

        <div class="brand-actions">
          <button
            v-if="brand.id !== activeId"
            type="button"
            class="btn btn-mini"
            :disabled="activatingId === brand.id"
            @click="handleActivate(brand)"
          >
            {{ activatingId === brand.id ? '启用中...' : '设为启用' }}
          </button>
          <span v-else class="btn btn-mini is-active-hint">✓ 使用中</span>
          <button type="button" class="btn btn-mini" :aria-label="`编辑「${brand.name}」`" @click="openEditModal(brand)">编辑</button>
          <button type="button" class="btn btn-mini btn-danger" :aria-label="`删除「${brand.name}」`" @click="deleteTarget = brand">删除</button>
        </div>
      </div>
    </div>

    <!-- 新建/编辑弹窗 -->
    <Teleport to="body">
      <div v-if="showModal" class="brand-modal-overlay" @click.self="closeModal">
        <div class="brand-modal" role="dialog" aria-modal="true" :aria-label="editingBrand ? '编辑品牌档案' : '新建品牌档案'">
          <div class="brand-modal-head">
            <h3>{{ editingBrand ? '编辑品牌档案' : '新建品牌档案' }}</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeModal">×</button>
          </div>

          <div class="brand-modal-body">
            <div class="form-field">
              <label>品牌 / IP 名称 <span class="required">*</span></label>
              <input v-model="form.name" class="input" type="text" placeholder="如：阿真的护肤日记" maxlength="50" />
            </div>

            <div class="form-field">
              <label>一句话定位</label>
              <input v-model="form.tagline" class="input" type="text" placeholder="如：帮敏感肌女生避坑的成分党博主" maxlength="100" />
            </div>

            <div class="form-grid">
              <div class="form-field">
                <label>目标人群</label>
                <input v-model="form.audience" class="input" type="text" placeholder="如：18-30 岁敏感肌女生" maxlength="100" />
              </div>
              <div class="form-field">
                <label>语气风格</label>
                <input v-model="form.tone" class="input" type="text" placeholder="如：专业克制 / 活泼种草" maxlength="50" list="tone-presets" />
                <datalist id="tone-presets">
                  <option value="专业克制"></option>
                  <option value="活泼种草"></option>
                  <option value="亲切闺蜜风"></option>
                  <option value="幽默段子手"></option>
                  <option value="高冷干货型"></option>
                </datalist>
              </div>
            </div>

            <div class="form-field">
              <label>主色调</label>
              <div class="color-field">
                <input v-model="form.primary_color" type="color" class="color-picker" aria-label="选择主色调" />
                <input v-model="form.primary_color" class="input" type="text" placeholder="#FF2442" maxlength="20" />
              </div>
            </div>

            <div class="form-field">
              <label>常用口头禅 / 开场白 <span class="hint">（每行一条）</span></label>
              <textarea v-model="form.catchphrasesText" class="input" rows="3" placeholder="姐妹们！今天必须给你们说这个&#10;先说结论——"></textarea>
            </div>

            <div class="form-field">
              <label>签名 / 结尾话术</label>
              <textarea v-model="form.signature" class="input" rows="2" placeholder="如：关注我，做你最懂成分的护肤搭子"></textarea>
            </div>

            <div class="form-field">
              <label>禁用词 <span class="hint">（每行一个）</span></label>
              <textarea v-model="form.bannedWordsText" class="input" rows="3" placeholder="最&#10;第一&#10;绝对"></textarea>
            </div>

            <div class="form-field">
              <label>备注</label>
              <textarea v-model="form.notes" class="input" rows="2" placeholder="其他想记录的信息"></textarea>
            </div>

            <p v-if="formError" class="form-error" role="alert">{{ formError }}</p>
          </div>

          <div class="brand-modal-foot">
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
      title="删除这个品牌档案？"
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
  activateBrand,
  createBrand,
  deleteBrand,
  getBrandList,
  updateBrand,
  type BrandKit
} from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'

/**
 * 品牌记忆（品牌资料库）页面
 *
 * 功能：
 * - 品牌档案列表展示
 * - 新建 / 编辑档案（弹窗表单）
 * - 设置「当前启用」档案
 * - 删除档案（二次确认）
 */

// 列表状态
const brands = ref<BrandKit[]>([])
const activeId = ref<string | null>(null)
const loading = ref(false)
const error = ref<AppError | null>(null)
const successMessage = ref('')
const activatingId = ref<string | null>(null)

// 弹窗表单状态
const showModal = ref(false)
const editingBrand = ref<BrandKit | null>(null)
const saving = ref(false)
const formError = ref('')

const form = reactive({
  name: '',
  tagline: '',
  audience: '',
  tone: '',
  primary_color: '#FF2442',
  catchphrasesText: '',
  signature: '',
  bannedWordsText: '',
  notes: ''
})

/** 必填项（品牌名称）非空才允许保存 */
const canSave = computed(() => form.name.trim().length > 0)

// 删除确认状态
const deleteTarget = ref<BrandKit | null>(null)

const deleteMessage = computed(() => {
  if (!deleteTarget.value) return ''
  const base = `「${deleteTarget.value.name}」删除后无法恢复。`
  if (deleteTarget.value.id === activeId.value) {
    return `${base}\n该档案当前处于启用状态，删除后将没有启用中的档案。`
  }
  return base
})

/** 文本域（每行一条）转字符串数组 */
function textToList(text: string): string[] {
  return text
    .split('\n')
    .map(line => line.trim())
    .filter(Boolean)
}

/**
 * 加载档案列表
 */
async function loadBrands() {
  loading.value = true
  error.value = null
  const res = await getBrandList()
  if (res.success) {
    brands.value = res.brands
    activeId.value = res.active_id
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '获取品牌档案列表失败', '获取品牌档案列表失败')
  }
  loading.value = false
}

/**
 * 错误重试
 */
function handleRetry() {
  error.value = null
  loadBrands()
}

/**
 * 打开新建弹窗
 */
function openCreateModal() {
  editingBrand.value = null
  form.name = ''
  form.tagline = ''
  form.audience = ''
  form.tone = ''
  form.primary_color = '#FF2442'
  form.catchphrasesText = ''
  form.signature = ''
  form.bannedWordsText = ''
  form.notes = ''
  formError.value = ''
  showModal.value = true
}

/**
 * 打开编辑弹窗
 */
function openEditModal(brand: BrandKit) {
  editingBrand.value = brand
  form.name = brand.name
  form.tagline = brand.tagline
  form.audience = brand.audience
  form.tone = brand.tone
  form.primary_color = brand.primary_color || '#FF2442'
  form.catchphrasesText = brand.catchphrases.join('\n')
  form.signature = brand.signature
  form.bannedWordsText = brand.banned_words.join('\n')
  form.notes = brand.notes
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
  if (!form.name.trim()) {
    formError.value = '请填写品牌/IP 名称'
    return
  }

  saving.value = true
  formError.value = ''

  const payload = {
    name: form.name.trim(),
    tagline: form.tagline.trim(),
    audience: form.audience.trim(),
    tone: form.tone.trim(),
    primary_color: form.primary_color.trim(),
    catchphrases: textToList(form.catchphrasesText),
    signature: form.signature.trim(),
    banned_words: textToList(form.bannedWordsText),
    notes: form.notes.trim()
  }

  const res = editingBrand.value
    ? await updateBrand(editingBrand.value.id, payload)
    : await createBrand(payload)

  saving.value = false

  if (res.success) {
    successMessage.value = editingBrand.value ? '档案已更新' : '档案已创建'
    showModal.value = false
    await loadBrands()
  } else {
    formError.value = res.error_message || '保存失败，请重试'
  }
}

/**
 * 设为启用
 */
async function handleActivate(brand: BrandKit) {
  if (activatingId.value) return
  activatingId.value = brand.id
  const res = await activateBrand(brand.id)
  activatingId.value = null

  if (res.success) {
    activeId.value = brand.id
    successMessage.value = `已启用「${brand.name}」`
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '启用品牌档案失败', '启用品牌档案失败')
  }
}

/**
 * 执行删除
 */
async function doDelete() {
  if (!deleteTarget.value) return
  const target = deleteTarget.value
  deleteTarget.value = null

  const res = await deleteBrand(target.id)
  if (res.success) {
    successMessage.value = `已删除「${target.name}」`
    await loadBrands()
  } else {
    error.value = normalizeApiError(res.error || res.error_message || '删除品牌档案失败', '删除品牌档案失败')
  }
}

onMounted(() => {
  loadBrands()
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

/* 档案列表 */
.brand-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: 20px;
  margin-bottom: 40px;
}

.brand-card {
  display: flex;
  flex-direction: column;
  gap: 12px;
  padding: 20px;
}

.brand-card.active {
  border: 1px solid var(--primary);
  box-shadow: var(--shadow-focus);
}

.brand-card-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.color-dot {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
  border: 1px solid var(--border-color);
}

.brand-name {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0;
  flex: 1;
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.active-badge {
  flex-shrink: 0;
  font-size: 12px;
  font-weight: 600;
  padding: 2px 8px;
  border-radius: var(--radius-full);
  background: var(--primary-light);
  color: var(--primary);
}

.brand-tagline {
  margin: 0;
  font-size: 14px;
  color: var(--text-sub);
  line-height: 1.5;
}

.brand-meta {
  display: flex;
  flex-direction: column;
  gap: 6px;
  font-size: 13px;
}

.meta-row {
  display: flex;
  gap: 8px;
  line-height: 1.5;
}

.meta-label {
  flex-shrink: 0;
  color: var(--text-secondary);
}

.meta-value {
  color: var(--text-main);
  overflow: hidden;
  text-overflow: ellipsis;
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
}

.danger-text {
  color: var(--color-danger);
}

.brand-actions {
  display: flex;
  gap: 8px;
  margin-top: auto;
  padding-top: 12px;
  border-top: 1px solid var(--border-color);
}

.btn-mini {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  border-radius: var(--radius-sm);
}

.btn-mini:hover {
  border-color: var(--border-hover);
  background: var(--gray-0);
}

.btn-mini.btn-danger {
  color: var(--color-danger);
}

.btn-mini.btn-danger:hover {
  border-color: var(--color-danger);
  background: var(--color-danger-soft);
}

.btn-mini.is-active-hint {
  color: var(--primary);
  border-color: transparent;
  background: var(--primary-light);
  cursor: default;
}

/* 新建/编辑弹窗 */
.brand-modal-overlay {
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
}

.brand-modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 560px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

.brand-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 12px;
}

.brand-modal-head h3 {
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

.brand-modal-body {
  padding: 8px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.brand-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.brand-modal-foot .btn {
  border: 1px solid var(--border-color);
}

.brand-modal-foot .btn-primary {
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

.form-field .hint {
  font-weight: 400;
  color: var(--text-secondary);
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

.color-field {
  display: flex;
  gap: 10px;
  align-items: center;
}

.color-picker {
  width: 42px;
  height: 38px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  cursor: pointer;
  flex-shrink: 0;
  transition: border-color var(--transition-fast);
}

.color-picker:hover {
  border-color: var(--border-hover);
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .brand-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .form-grid {
    grid-template-columns: 1fr;
  }

  .brand-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .brand-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
}
</style>
