<template>
  <div class="container" style="max-width: 1000px;">
    <!-- 页头 -->
    <div class="page-header">
      <div>
        <h1 class="page-title">品牌记忆</h1>
        <p class="page-subtitle">管理你的个人 IP / 品牌档案，让文案始终保持统一人设</p>
      </div>
      <div class="header-actions">
        <button type="button" class="btn btn-secondary" @click="openWizard">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"></path></svg>
          新手？让 AI 帮你定位
        </button>
        <button type="button" class="btn btn-primary" @click="openCreateModal">
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="12" y1="5" x2="12" y2="19"></line><line x1="5" y1="12" x2="19" y2="12"></line></svg>
          新建档案
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
    <div v-if="loading" class="brand-grid" aria-hidden="true">
      <div v-for="i in 3" :key="i" class="card brand-card skeleton-card">
        <div class="skeleton-head">
          <span class="skeleton skeleton-dot"></span>
          <span class="skeleton skeleton-line" style="width: 42%;"></span>
        </div>
        <span class="skeleton skeleton-line" style="width: 86%;"></span>
        <span class="skeleton skeleton-line" style="width: 64%;"></span>
        <span class="skeleton skeleton-line" style="width: 52%;"></span>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="brands.length === 0" class="empty-state-large">
      <div class="empty-icon-wrap">
        <svg width="32" height="32" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><path d="M20 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2"></path><circle cx="12" cy="7" r="4"></circle></svg>
      </div>
      <h3 class="empty-title">还没有品牌档案</h3>
      <p class="empty-tips">创建一个档案，记录你的人设定位、语气风格和常用话术</p>
      <div class="empty-cta-group">
        <button type="button" class="btn btn-primary empty-cta" @click="openWizard">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"></path></svg>
          新手？让 AI 帮你定位
        </button>
        <button type="button" class="btn btn-secondary empty-cta" @click="openCreateModal">自己填写创建</button>
      </div>
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

    <!-- 新手账号定位向导弹窗 -->
    <Teleport to="body">
      <div v-if="wizardVisible" class="brand-modal-overlay" @click.self="closeWizard">
        <div class="brand-modal wizard-modal" role="dialog" aria-modal="true" aria-label="新手账号定位向导">
          <div class="brand-modal-head">
            <h3>{{ wizardTitle }}</h3>
            <button type="button" class="close-btn" aria-label="关闭" @click="closeWizard">×</button>
          </div>

          <!-- 阶段一：三步问答 -->
          <template v-if="wizardPhase === 'questions'">
            <div class="brand-modal-body">
              <div class="wizard-steps" aria-hidden="true">
                <template v-for="(q, i) in WIZARD_QUESTIONS" :key="q.key">
                  <span class="wizard-step-dot" :class="{ active: i === wizardStep, done: i < wizardStep }">{{ i + 1 }}</span>
                  <span v-if="i < WIZARD_QUESTIONS.length - 1" class="wizard-step-line" :class="{ done: i < wizardStep }"></span>
                </template>
              </div>

              <div class="form-field">
                <label class="wizard-q-title">{{ currentQuestion.title }}</label>
                <p class="wizard-q-tips">{{ currentQuestion.tips }}</p>
                <textarea
                  v-model="wizardAnswers[currentQuestion.key]"
                  class="input"
                  rows="3"
                  :placeholder="currentQuestion.placeholder"
                ></textarea>
              </div>

              <div class="wizard-chips" aria-label="示例，点击填入">
                <button
                  v-for="chip in currentQuestion.examples"
                  :key="chip"
                  type="button"
                  class="wizard-chip"
                  @click="applyExample(chip)"
                >{{ chip }}</button>
              </div>

              <p v-if="wizardError" class="form-error" role="alert">{{ wizardError }}</p>
            </div>

            <div class="brand-modal-foot">
              <button v-if="wizardStep > 0" type="button" class="btn" :disabled="drafting" @click="prevStep">上一步</button>
              <button
                v-if="wizardStep < WIZARD_QUESTIONS.length - 1"
                type="button"
                class="btn btn-primary"
                @click="nextStep"
              >下一步</button>
              <button
                v-else
                type="button"
                class="btn btn-primary"
                :disabled="drafting"
                @click="handleGenerateDraft"
              >
                <span v-if="drafting" class="btn-spinner" aria-hidden="true"></span>
                {{ drafting ? '生成中...' : (wizardError ? '重试生成' : '生成我的定位') }}
              </button>
            </div>
          </template>

          <!-- 阶段二：可编辑预览 -->
          <template v-else-if="wizardPhase === 'preview'">
            <div class="brand-modal-body">
              <p class="wizard-preview-tip">AI 已生成你的定位草稿，每个字段都可以修改，确认后将创建档案并设为启用</p>

              <div class="form-field">
                <label>账号名 <span class="required">*</span></label>
                <div v-if="draftNameOptions.length > 1" class="wizard-chips">
                  <button
                    v-for="option in draftNameOptions"
                    :key="option"
                    type="button"
                    class="wizard-chip"
                    :class="{ selected: draftForm.name === option }"
                    @click="draftForm.name = option"
                  >{{ option }}</button>
                </div>
                <input v-model="draftForm.name" class="input" type="text" maxlength="50" placeholder="从上方建议里选一个，或自己改" />
              </div>

              <div class="form-field">
                <label>一句话定位</label>
                <input v-model="draftForm.positioning" class="input" type="text" maxlength="100" />
              </div>

              <div class="form-grid">
                <div class="form-field">
                  <label>目标人群</label>
                  <input v-model="draftForm.audience" class="input" type="text" maxlength="100" />
                </div>
                <div class="form-field">
                  <label>语气风格</label>
                  <input v-model="draftForm.tone" class="input" type="text" maxlength="50" />
                </div>
              </div>

              <div class="form-field">
                <label>常用口头禅 / 开场白 <span class="hint">（每行一条）</span></label>
                <textarea v-model="draftForm.catchphrasesText" class="input" rows="3"></textarea>
              </div>

              <div class="form-field">
                <label>签名 / 结尾话术</label>
                <textarea v-model="draftForm.signature" class="input" rows="2"></textarea>
              </div>

              <div class="form-field">
                <label>建议避免的词 <span class="hint">（每行一个，将存为禁用词）</span></label>
                <textarea v-model="draftForm.bannedWordsText" class="input" rows="3"></textarea>
              </div>

              <div class="form-field">
                <label>赛道标签 <span class="hint">（空格分隔，将写入备注）</span></label>
                <input v-model="draftForm.nicheTagsText" class="input" type="text" />
              </div>

              <p v-if="wizardError" class="form-error" role="alert">{{ wizardError }}</p>
            </div>

            <div class="brand-modal-foot">
              <button type="button" class="btn" :disabled="savingDraft" @click="backToQuestions">返回修改回答</button>
              <button
                type="button"
                class="btn btn-primary"
                :disabled="savingDraft || !draftForm.name.trim()"
                @click="handleSaveDraft"
              >
                {{ savingDraft ? '创建中...' : '创建档案并启用' }}
              </button>
            </div>
          </template>

          <!-- 阶段三：起号选题清单 -->
          <template v-else>
            <div class="brand-modal-body">
              <div class="wizard-done-banner" role="status">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"><polyline points="20 6 9 17 4 12"></polyline></svg>
                档案「{{ createdBrandName }}」已创建并启用
              </div>

              <template v-if="draftTopics.length > 0">
                <div class="starter-topics-head">
                  <h4>你的前 {{ draftTopics.length }} 篇起号选题</h4>
                  <button type="button" class="btn btn-mini" @click="copyAllTopics">
                    {{ copiedKey === 'all' ? '✓ 已复制' : '全部复制' }}
                  </button>
                </div>

                <ol class="starter-topics">
                  <li v-for="(topic, i) in draftTopics" :key="i" class="starter-topic-item">
                    <span class="topic-index">{{ i + 1 }}</span>
                    <div class="topic-text">
                      <span class="topic-title">{{ topic.title }}</span>
                      <span v-if="topic.angle" class="topic-angle">{{ topic.angle }}</span>
                    </div>
                    <button
                      type="button"
                      class="btn btn-mini topic-copy-btn"
                      :aria-label="`复制「${topic.title}」`"
                      @click="copyTopic(topic, i)"
                    >
                      {{ copiedKey === String(i) ? '✓' : '复制' }}
                    </button>
                  </li>
                </ol>
              </template>
              <p v-else class="wizard-q-tips">本次没有生成起号选题，可以去选题灵感工具按新定位生成。</p>

              <p class="wizard-done-tip">
                想要更多方向？可去
                <RouterLink to="/tools/topic">选题灵感工具</RouterLink>
                继续深化这些选题
              </p>
            </div>

            <div class="brand-modal-foot">
              <button type="button" class="btn btn-primary" @click="closeWizard">完成</button>
            </div>
          </template>
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
import { computed, onMounted, onUnmounted, reactive, ref } from 'vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'
import {
  activateBrand,
  createBrand,
  deleteBrand,
  generateBrandDraft,
  getBrandList,
  updateBrand,
  type BrandDraft,
  type BrandKit,
  type BrandStarterTopic
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
 * - 新手账号定位向导（三步问答 → AI 草稿 → 可编辑预览 → 落库启用 + 起号选题）
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

// ==================== 新手账号定位向导 ====================

/** 向导问答步骤定义 */
interface WizardQuestion {
  key: 'who' | 'audience' | 'advantage'
  title: string
  tips: string
  placeholder: string
  examples: string[]
}

const WIZARD_QUESTIONS: WizardQuestion[] = [
  {
    key: 'who',
    title: '第 1 步：你是谁？',
    tips: '你的身份、职业或经历，是账号可信度的地基',
    placeholder: '如：三甲医院营养科医生，做了 8 年临床营养',
    examples: ['三甲医院营养科医生', '带娃的前大厂运营', '健身 5 年的上班族']
  },
  {
    key: 'audience',
    title: '第 2 步：做给谁看？',
    tips: '人群越具体，内容越容易戳中人，别贪「所有人」',
    placeholder: '如：25-35 岁想减脂但没时间运动的女生',
    examples: ['25-35 岁想减脂的女生', '新手宝妈', '想搞副业的大学生']
  },
  {
    key: 'advantage',
    title: '第 3 步：凭什么是你？',
    tips: '你的独特优势：专业资质、踩过的坑、能坚持的事都算',
    placeholder: '如：有营养师资质，自己减过 30 斤',
    examples: ['有专业资质', '亲身踩过坑', '能坚持日更实测']
  }
]

const wizardVisible = ref(false)
const wizardPhase = ref<'questions' | 'preview' | 'done'>('questions')
const wizardStep = ref(0)
const wizardAnswers = reactive<Record<WizardQuestion['key'], string>>({
  who: '',
  audience: '',
  advantage: ''
})
const wizardError = ref('')
const drafting = ref(false)
const savingDraft = ref(false)

// 草稿预览（可编辑）状态
const draftNameOptions = ref<string[]>([])
const draftTopics = ref<BrandStarterTopic[]>([])
const draftForm = reactive({
  name: '',
  positioning: '',
  audience: '',
  tone: '',
  catchphrasesText: '',
  signature: '',
  bannedWordsText: '',
  nicheTagsText: ''
})
const createdBrandName = ref('')

// 起号选题复制反馈（'all' 或条目下标字符串）
const copiedKey = ref('')
let copyTimer: ReturnType<typeof setTimeout> | undefined

const currentQuestion = computed(() => WIZARD_QUESTIONS[wizardStep.value])

const wizardTitle = computed(() => {
  if (wizardPhase.value === 'preview') return '确认你的定位'
  if (wizardPhase.value === 'done') return '定位完成，开始起号'
  return '新手账号定位向导'
})

function openWizard() {
  wizardVisible.value = true
  wizardPhase.value = 'questions'
  wizardStep.value = 0
  wizardAnswers.who = ''
  wizardAnswers.audience = ''
  wizardAnswers.advantage = ''
  wizardError.value = ''
  createdBrandName.value = ''
  draftTopics.value = []
}

function closeWizard() {
  // 生成/保存进行中不允许误触关闭
  if (drafting.value || savingDraft.value) return
  wizardVisible.value = false
}

/** 点击示例 chip：填入当前问题的输入框（可继续编辑） */
function applyExample(chip: string) {
  wizardAnswers[currentQuestion.value.key] = chip
}

function nextStep() {
  if (!wizardAnswers[currentQuestion.value.key].trim()) {
    wizardError.value = '先写一句再继续，点下面的示例填入也可以'
    return
  }
  wizardError.value = ''
  wizardStep.value++
}

function prevStep() {
  wizardError.value = ''
  if (wizardStep.value > 0) wizardStep.value--
}

/** 从预览返回问答（保留已填回答，便于调整后重新生成） */
function backToQuestions() {
  wizardError.value = ''
  wizardPhase.value = 'questions'
  wizardStep.value = WIZARD_QUESTIONS.length - 1
}

/**
 * 第三步确认：调后端生成定位草稿，成功进入可编辑预览，失败展示错误可重试
 */
async function handleGenerateDraft() {
  if (drafting.value) return
  if (!wizardAnswers.advantage.trim()) {
    wizardError.value = '先写一句再继续，点下面的示例填入也可以'
    return
  }

  drafting.value = true
  wizardError.value = ''

  const res = await generateBrandDraft({
    who: wizardAnswers.who.trim(),
    audience: wizardAnswers.audience.trim(),
    advantage: wizardAnswers.advantage.trim()
  })

  drafting.value = false

  if (res.success && res.draft) {
    fillDraftForm(res.draft)
    wizardPhase.value = 'preview'
  } else {
    wizardError.value = res.error_message || '生成账号定位失败，请稍后重试'
  }
}

/** 把 AI 草稿填入可编辑表单（目标人群草稿里没有，用第 2 步回答预填） */
function fillDraftForm(draft: BrandDraft) {
  draftNameOptions.value = draft.name
  draftForm.name = draft.name[0] || ''
  draftForm.positioning = draft.positioning
  draftForm.audience = wizardAnswers.audience.trim()
  draftForm.tone = draft.tone
  draftForm.catchphrasesText = draft.catchphrases.join('\n')
  draftForm.signature = draft.signature
  draftForm.bannedWordsText = draft.banned_words.join('\n')
  draftForm.nicheTagsText = draft.niche_tags.join(' ')
  draftTopics.value = draft.starter_topics
}

/**
 * 确认草稿：走现有创建档案 API 落库并设为启用，成功进入起号选题页
 */
async function handleSaveDraft() {
  if (savingDraft.value) return
  if (!draftForm.name.trim()) {
    wizardError.value = '请填写账号名'
    return
  }

  savingDraft.value = true
  wizardError.value = ''

  // 赛道标签没有独立字段，规整后写入备注便于后续查看
  const tags = draftForm.nicheTagsText
    .split(/[\s,，、#]+/)
    .map(tag => tag.trim())
    .filter(Boolean)
  const notesParts = ['来自新手账号定位向导']
  if (tags.length > 0) {
    notesParts.push(`赛道标签：${tags.join(' / ')}`)
  }

  const res = await createBrand({
    name: draftForm.name.trim(),
    tagline: draftForm.positioning.trim(),
    audience: draftForm.audience.trim(),
    tone: draftForm.tone.trim(),
    catchphrases: textToList(draftForm.catchphrasesText),
    signature: draftForm.signature.trim(),
    banned_words: textToList(draftForm.bannedWordsText),
    notes: notesParts.join('\n')
  })

  if (!res.success || !res.brand) {
    savingDraft.value = false
    wizardError.value = res.error_message || '创建档案失败，请重试'
    return
  }

  // 设为启用（首个档案后端已自动启用，这里再调用一次幂等无副作用）
  const activated = await activateBrand(res.brand.id)
  savingDraft.value = false

  createdBrandName.value = res.brand.name
  wizardPhase.value = 'done'
  successMessage.value = activated.success
    ? `已创建并启用「${res.brand.name}」`
    : `已创建「${res.brand.name}」，启用失败，可在列表中手动启用`
  await loadBrands()
}

/** 复制文本（剪贴板 API 不可用时降级为手动选区复制），并给出短暂反馈 */
async function copyText(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedKey.value = key
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedKey.value = '' }, 1500)
}

function copyTopic(topic: BrandStarterTopic, index: number) {
  const text = topic.angle ? `${topic.title}\n切入角度：${topic.angle}` : topic.title
  copyText(text, String(index))
}

function copyAllTopics() {
  const text = draftTopics.value
    .map((topic, i) => `${i + 1}. ${topic.title}${topic.angle ? `（${topic.angle}）` : ''}`)
    .join('\n')
  copyText(text, 'all')
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

onUnmounted(() => {
  if (copyTimer !== undefined) clearTimeout(copyTimer)
})
</script>

<style scoped>
/* 页头操作组 */
.header-actions {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.header-actions .btn-secondary {
  border: 1px solid var(--border-color);
}

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
.skeleton-card {
  pointer-events: none;
}

.skeleton {
  display: block;
  background: var(--gray-2);
  border-radius: var(--radius-xs);
  animation: skeleton-pulse 1.4s var(--ease-out) infinite;
}

.skeleton-head {
  display: flex;
  align-items: center;
  gap: 10px;
}

.skeleton-dot {
  width: 14px;
  height: 14px;
  border-radius: var(--radius-full);
  flex-shrink: 0;
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

/* 空态双入口：向导为主 CTA，手动创建降级为次级 */
.empty-cta-group {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 12px;
  flex-wrap: wrap;
}

.empty-cta-group .btn-secondary {
  border: 1px solid var(--border-color);
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
  margin-bottom: 0;
}

.brand-card:hover {
  box-shadow: var(--shadow-hover);
  border-color: var(--border-hover);
  transform: translateY(-2px);
}

.brand-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.brand-card.active {
  border: 1px solid var(--primary);
  box-shadow: var(--shadow-focus);
}

.brand-card.active:hover {
  border-color: var(--primary);
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
  box-shadow: inset 0 0 0 2px var(--bg-card);
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
  animation: overlay-in 150ms var(--ease-out);
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
  .brand-modal-overlay,
  .brand-modal {
    animation: none;
  }
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

/* ==================== 新手账号定位向导 ==================== */
.wizard-modal {
  max-width: 520px;
}

/* 步骤指示：编号圆点 + 连接线 */
.wizard-steps {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 4px 0 2px;
}

.wizard-step-dot {
  width: 26px;
  height: 26px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  background: var(--gray-2);
  color: var(--text-secondary);
  flex-shrink: 0;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.wizard-step-dot.active {
  background: var(--primary);
  color: white;
}

.wizard-step-dot.done {
  background: var(--primary-light);
  color: var(--primary);
}

.wizard-step-line {
  width: 36px;
  height: 2px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  transition: background var(--transition-fast);
}

.wizard-step-line.done {
  background: var(--primary-light);
}

/* 提问标题比普通表单 label 更醒目（用更高特异性覆盖，避免 !important） */
.form-field label.wizard-q-title {
  font-size: 15px;
}

.wizard-q-tips {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.5;
}

/* 示例 chips */
.wizard-chips {
  display: flex;
  flex-wrap: wrap;
  gap: 8px;
}

.wizard-chip {
  padding: 6px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13px;
  font-family: inherit;
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.wizard-chip:hover {
  border-color: var(--border-hover);
  color: var(--primary);
  background: var(--primary-light);
}

.wizard-chip.selected {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-light);
  font-weight: 600;
}

/* 生成按钮里的加载圈 */
.btn-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.45);
  border-top-color: white;
  border-radius: 50%;
  display: inline-block;
  margin-right: 6px;
  vertical-align: -2px;
  animation: wizard-spin 0.8s linear infinite;
}

@keyframes wizard-spin {
  to { transform: rotate(360deg); }
}

.wizard-preview-tip {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
  padding: 10px 12px;
  background: var(--gray-0);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
}

/* 完成态 */
.wizard-done-banner {
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--color-success-soft);
  color: var(--color-success);
  font-size: 14px;
  font-weight: 600;
}

.starter-topics-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
}

.starter-topics-head h4 {
  margin: 0;
  font-size: 14px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.starter-topics {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: 8px;
}

.starter-topic-item {
  display: flex;
  align-items: flex-start;
  gap: 10px;
  padding: 10px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
}

.topic-index {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--gray-2);
  color: var(--text-secondary);
  font-size: 11px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
  margin-top: 1px;
}

.topic-text {
  flex: 1;
  min-width: 0;
  display: flex;
  flex-direction: column;
  gap: 2px;
}

.topic-title {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
  line-height: 1.5;
}

.topic-angle {
  font-size: 12px;
  color: var(--text-secondary);
  line-height: 1.5;
}

.topic-copy-btn {
  flex-shrink: 0;
}

.wizard-done-tip {
  margin: 0;
  font-size: 13px;
  color: var(--text-secondary);
}

.wizard-done-tip a {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.wizard-done-tip a:hover {
  text-decoration: underline;
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
