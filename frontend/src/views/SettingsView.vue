<template>
  <div class="container">
    <div class="page-header">
      <!-- 标题与副标题需包在同一子项内，避免被 page-header 的 space-between 推散 -->
      <div>
        <h1 class="page-title">系统设置</h1>
        <p class="page-subtitle">配置文本生成和图片生成的 API 服务</p>
      </div>
    </div>

    <div v-if="loading" class="loading-container">
      <div class="spinner"></div>
      <p>加载配置中...</p>
    </div>

    <div v-else class="settings-container">
      <!-- 已在设置页内，无需再显示"去设置"跳转 -->
      <ErrorCard
        v-if="feedback?.type === 'error'"
        :error="feedback.error"
        dismissible
        :settings-action="false"
        @dismiss="clearFeedback"
        @retry="handleRetry"
        style="margin-bottom: 16px;"
      />

      <div
        v-else-if="feedback?.type === 'success'"
        class="success-card"
        role="status"
        aria-live="polite"
      >
        <span>{{ feedback.message }}</span>
        <button type="button" @click="clearFeedback" aria-label="关闭提示">×</button>
      </div>

      <!-- 首配引导：没有任何已配置服务商时的"三步开始" -->
      <div v-if="showFirstRunGuide" class="first-run-guide" role="note">
        <div class="first-run-title">三步开始创作</div>
        <ol class="first-run-steps">
          <li><span class="step-num">1</span>在下方选择服务商，填好 API Key 并保存</li>
          <li><span class="step-num">2</span>点击「测试」确认连接可用</li>
          <li>
            <span class="step-num">3</span>
            <RouterLink to="/" class="step-link">回首页</RouterLink>输入主题开始创作
          </li>
        </ol>
      </div>

      <!-- 文本生成配置 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">文本生成配置</h2>
            <p class="section-desc">用于生成小红书图文大纲</p>
          </div>
          <button class="btn btn-secondary btn-small" @click="openAddTextModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 服务商列表表格 -->
        <ProviderTable
          :providers="textConfig.providers"
          :activeProvider="textConfig.active_provider"
          @activate="activateTextProvider"
          @edit="openEditTextModal"
          @delete="deleteTextProvider"
          @test="testTextProviderInList"
        />
      </div>

      <!-- 图片生成配置 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">图片生成配置</h2>
            <p class="section-desc">用于生成小红书配图</p>
          </div>
          <button class="btn btn-secondary btn-small" @click="openAddImageModal">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <line x1="12" y1="5" x2="12" y2="19"></line>
              <line x1="5" y1="12" x2="19" y2="12"></line>
            </svg>
            添加
          </button>
        </div>

        <!-- 服务商列表表格 -->
        <ProviderTable
          :providers="imageConfig.providers"
          :activeProvider="imageConfig.active_provider"
          @activate="activateImageProvider"
          @edit="openEditImageModal"
          @delete="deleteImageProvider"
          @test="testImageProviderInList"
        />
      </div>

      <!-- 图片生成 Prompt 模板 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">
              图片生成 Prompt 模板
              <span v-if="promptIsCustom" class="custom-badge">当前使用自定义模板</span>
            </h2>
            <p class="section-desc">
              模板控制 AI 画图的指令。可用占位符：<code v-pre>{page_content}</code>=页面文案、<code v-pre>{page_type}</code>=页面类型、<code v-pre>{user_topic}</code>=用户主题、<code v-pre>{full_outline}</code>=完整大纲。风格模板的 style_prompt 会自动追加在末尾。
            </p>
            <p class="section-desc prompt-short-warning">
              注意：若图片服务商开启了“短 Prompt 模式”，将使用内置短模板，此处的自定义模板不生效。
            </p>
          </div>
        </div>

        <div v-if="promptLoading" class="loading-container">
          <div class="spinner"></div>
          <p>加载模板中...</p>
        </div>

        <template v-else>
          <textarea
            v-model="promptTemplate"
            class="prompt-textarea"
            spellcheck="false"
            placeholder="输入图片生成 Prompt 模板..."
          ></textarea>

          <div class="prompt-actions">
            <button
              class="btn btn-secondary"
              @click="handleResetPrompt"
              :disabled="promptSaving"
            >
              恢复默认
            </button>
            <button
              class="btn btn-primary"
              @click="handleSavePrompt"
              :disabled="promptSaving"
            >
              {{ promptSaving ? '保存中...' : '保存模板' }}
            </button>
          </div>
        </template>
      </div>

      <!-- 数据管理：一键备份 / 导入恢复 / 诊断包 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">数据管理</h2>
            <p class="section-desc">
              所有数据（历史记录、品牌库、内容日历、表现数据、发布账号与浏览器内的风格模板等）均存储在本机，可在此一键备份、迁移与导出诊断包。
            </p>
          </div>
        </div>

        <div class="data-admin-rows">
          <!-- 导出备份 -->
          <div class="data-admin-row">
            <div class="data-admin-info">
              <div class="data-admin-label">导出备份</div>
              <p class="data-admin-desc">
                打包全部本地数据为 zip 文件，可用于换机迁移或定期备份。默认不包含 API 密钥。
              </p>
              <p class="data-admin-danger">
                「含密钥」会把服务商 API Key 明文写入备份文件，请妥善保管，切勿分享给他人。
              </p>
            </div>
            <div class="data-admin-actions">
              <button
                class="btn btn-primary btn-small"
                :disabled="exporting"
                @click="handleExportBackup(false)"
              >
                {{ exporting ? '导出中...' : '导出备份' }}
              </button>
              <button
                class="btn btn-secondary btn-small"
                :disabled="exporting"
                @click="handleExportBackup(true)"
              >
                导出备份（含密钥）
              </button>
            </div>
          </div>

          <!-- 导入恢复 -->
          <div class="data-admin-row">
            <div class="data-admin-info">
              <div class="data-admin-label">导入恢复</div>
              <p class="data-admin-desc">
                选择此前导出的备份 zip 恢复数据。导入前会自动把现有数据备份到数据目录的
                .pre_import_backup_ 文件夹，再进行覆盖。
              </p>
            </div>
            <div class="data-admin-actions">
              <input
                ref="importFileInput"
                type="file"
                accept=".zip,application/zip"
                class="data-admin-file-input"
                @change="handleImportFileSelected"
              />
              <button
                class="btn btn-secondary btn-small"
                :disabled="importing"
                @click="importFileInput?.click()"
              >
                {{ importing ? '导入中...' : '选择备份文件导入' }}
              </button>
            </div>
          </div>

          <!-- 导出诊断包 -->
          <div class="data-admin-row">
            <div class="data-admin-info">
              <div class="data-admin-label">导出诊断包</div>
              <p class="data-admin-desc">
                打包运行日志与版本、平台信息，用于反馈问题。配置信息已脱敏，不包含任何 API 密钥。
              </p>
            </div>
            <div class="data-admin-actions">
              <button
                class="btn btn-secondary btn-small"
                :disabled="diagnosing"
                @click="handleExportDiagnostics"
              >
                {{ diagnosing ? '导出中...' : '导出诊断包' }}
              </button>
            </div>
          </div>
        </div>
      </div>

      <!-- 创作偏好画像：从作品评分与编辑留痕聚合的用户偏好 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">创作偏好画像</h2>
            <p class="section-desc">
              根据你的作品评分与文案编辑习惯自动聚合，生成大纲时会参考这些偏好。
            </p>
          </div>
        </div>

        <div v-if="profileLoading" class="loading-container">
          <div class="spinner"></div>
          <p>加载画像中...</p>
        </div>

        <p v-else-if="profileError" class="preference-hint">
          画像加载失败，请稍后重试。
        </p>

        <p v-else-if="!profile || profile.insufficient" class="preference-hint">
          多给作品打分，AI 会越来越懂你（当前样本
          {{ profile?.sample_count ?? 0 }}/{{ profile?.min_samples ?? 3 }}）
        </p>

        <div v-else class="preference-rows">
          <div class="preference-row">
            <span class="preference-label">已评分作品</span>
            <span class="preference-value">
              {{ profile.sample_count }} 个（其中高分 {{ profile.liked_count }} 个）
            </span>
          </div>
          <div v-if="profile.preferred_page_count" class="preference-row">
            <span class="preference-label">偏好篇幅</span>
            <span class="preference-value">{{ profile.preferred_page_count }} 页左右</span>
          </div>
          <div v-if="profile.liked_topics.length" class="preference-row">
            <span class="preference-label">满意的主题</span>
            <span class="preference-value">{{ profile.liked_topics.join('、') }}</span>
          </div>
          <div v-if="editingSignalText" class="preference-row">
            <span class="preference-label">编辑习惯</span>
            <span class="preference-value">{{ editingSignalText }}</span>
          </div>
        </div>
      </div>

      <!-- 访问安全：公网部署时的访问令牌 -->
      <div class="card">
        <div class="section-header">
          <div>
            <h2 class="section-title">访问安全</h2>
            <p class="section-desc">
              本地使用无需设置。若你把 RedInk 部署到公网并在服务端启用了
              REDINK_ACCESS_TOKEN，请在此填写相同令牌。
            </p>
          </div>
        </div>

        <p v-if="hasSavedAccessToken" class="token-status">
          已保存令牌：<code class="token-preview">{{ maskedAccessToken }}</code>（保存新值将覆盖）
        </p>
        <p v-else class="token-status">当前未保存访问令牌，请求不会携带鉴权头。</p>

        <div class="token-editor">
          <div class="token-input-wrap">
            <input
              v-model="accessTokenInput"
              :type="showAccessToken ? 'text' : 'password'"
              class="token-input"
              placeholder="粘贴与服务端 REDINK_ACCESS_TOKEN 相同的令牌"
              autocomplete="off"
              spellcheck="false"
              @keyup.enter="handleSaveAccessToken"
            />
            <button
              type="button"
              class="token-toggle"
              :aria-label="showAccessToken ? '隐藏令牌' : '明文显示令牌'"
              @click="showAccessToken = !showAccessToken"
            >
              {{ showAccessToken ? '隐藏' : '显示' }}
            </button>
          </div>
          <div class="token-actions">
            <button
              class="btn btn-primary btn-small"
              :disabled="!accessTokenInput.trim()"
              @click="handleSaveAccessToken"
            >
              保存
            </button>
            <button
              class="btn btn-secondary btn-small"
              :disabled="!hasSavedAccessToken && !accessTokenInput"
              @click="handleClearAccessToken"
            >
              清除
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 文本服务商弹窗 -->
    <ProviderModal
      :visible="showTextModal"
      :isEditing="!!editingTextProvider"
      :formData="textForm"
      :testing="testingText"
      :typeOptions="textTypeOptions"
      providerCategory="text"
      @close="closeTextModal"
      @save="saveTextProvider"
      @test="testTextConnection"
      @update:formData="updateTextForm"
    />

    <!-- 图片服务商弹窗 -->
    <ImageProviderModal
      :visible="showImageModal"
      :isEditing="!!editingImageProvider"
      :formData="imageForm"
      :testing="testingImage"
      :typeOptions="imageTypeOptions"
      @close="closeImageModal"
      @save="saveImageProvider"
      @test="testImageConnection"
      @update:formData="updateImageForm"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import ProviderTable from '../components/settings/ProviderTable.vue'
import ProviderModal from '../components/settings/ProviderModal.vue'
import ImageProviderModal from '../components/settings/ImageProviderModal.vue'
import ErrorCard from '../components/common/ErrorCard.vue'
import {
  getImagePrompt,
  saveImagePrompt,
  resetImagePrompt,
  exportBackup,
  importBackup,
  exportDiagnostics,
  downloadBlob,
  getPreferenceProfile,
  type PreferenceProfile
} from '../api'
import { clearAccessToken, getAccessToken, setAccessToken } from '../api/client'
import { normalizeApiError } from '../utils/errors'
import { hasConfiguredProvider } from '../utils/providerConfig'
import { collectLocalBackup, restoreLocalBackup } from '../utils/localBackup'
import {
  useProviderForm,
  textTypeOptions,
  imageTypeOptions
} from '../composables/useProviderForm'

/**
 * 系统设置页面
 *
 * 功能：
 * - 管理文本生成服务商配置
 * - 管理图片生成服务商配置
 * - 测试 API 连接
 * - 自定义图片生成 Prompt 模板
 */

// 使用 composable 管理表单状态和逻辑
const {
  // 状态
  loading,
  testingText,
  testingImage,
  feedback,

  // 配置数据
  textConfig,
  imageConfig,

  // 文本服务商弹窗
  showTextModal,
  editingTextProvider,
  textForm,

  // 图片服务商弹窗
  showImageModal,
  editingImageProvider,
  imageForm,

  // 方法
  loadConfig,
  clearFeedback,

  // 文本服务商方法
  activateTextProvider,
  openAddTextModal,
  openEditTextModal,
  closeTextModal,
  saveTextProvider,
  deleteTextProvider,
  testTextConnection,
  testTextProviderInList,
  updateTextForm,

  // 图片服务商方法
  activateImageProvider,
  openAddImageModal,
  openEditImageModal,
  closeImageModal,
  saveImageProvider,
  deleteImageProvider,
  testImageConnection,
  testImageProviderInList,
  updateImageForm
} = useProviderForm()

/**
 * 首配引导：文本和图片两个分区都没有任何已保存 API Key 的服务商时显示；
 * 用户配好任意一个服务商（保存后配置回读）即自然消失
 */
const showFirstRunGuide = computed(
  () =>
    !hasConfiguredProvider(textConfig.value.providers) &&
    !hasConfiguredProvider(imageConfig.value.providers)
)

/**
 * 错误重试：清除错误提示并重新加载配置
 */
function handleRetry() {
  clearFeedback()
  loadConfig()
  loadImagePrompt()
}

// ==================== 图片生成 Prompt 模板 ====================

const REQUIRED_PLACEHOLDERS = ['{page_content}', '{page_type}']

const promptLoading = ref(true)
const promptSaving = ref(false)
const promptTemplate = ref('')
const promptIsCustom = ref(false)

/** 加载当前生效的图片 Prompt 模板 */
async function loadImagePrompt() {
  promptLoading.value = true
  try {
    const result = await getImagePrompt()
    if (result.success) {
      promptTemplate.value = result.template || ''
      promptIsCustom.value = !!result.is_custom
    } else {
      setPromptError(result.error || result.error_message || '加载模板失败', '加载模板失败')
    }
  } catch (e) {
    setPromptError(e, '加载模板失败')
  } finally {
    promptLoading.value = false
  }
}

/** 保存自定义模板（前端先校验必需占位符） */
async function handleSavePrompt() {
  const missing = REQUIRED_PLACEHOLDERS.filter(p => !promptTemplate.value.includes(p))
  if (missing.length > 0) {
    setPromptError(
      `模板缺少必需占位符: ${missing.join('、')}，请补充后再保存`,
      '模板校验失败'
    )
    return
  }

  promptSaving.value = true
  try {
    const result = await saveImagePrompt(promptTemplate.value)
    if (result.success) {
      promptIsCustom.value = true
      feedback.value = { type: 'success', message: result.message || '图片 Prompt 模板已保存' }
    } else {
      setPromptError(result.error || result.error_message || '保存模板失败', '保存模板失败')
    }
  } catch (e) {
    setPromptError(e, '保存模板失败')
  } finally {
    promptSaving.value = false
  }
}

/** 恢复默认模板 */
async function handleResetPrompt() {
  if (!confirm('确定要恢复默认模板吗？当前自定义内容将被删除。')) return

  promptSaving.value = true
  try {
    const result = await resetImagePrompt()
    if (result.success) {
      feedback.value = { type: 'success', message: result.message || '已恢复默认模板' }
      await loadImagePrompt()
    } else {
      setPromptError(result.error || result.error_message || '恢复默认失败', '恢复默认失败')
    }
  } catch (e) {
    setPromptError(e, '恢复默认失败')
  } finally {
    promptSaving.value = false
  }
}

function setPromptError(error: unknown, fallbackTitle: string) {
  feedback.value = { type: 'error', error: normalizeApiError(error, fallbackTitle) }
}

// ==================== 数据管理（备份 / 恢复 / 诊断包） ====================

const exporting = ref(false)
const importing = ref(false)
const diagnosing = ref(false)
const importFileInput = ref<HTMLInputElement | null>(null)

function backupTimestamp(): string {
  const now = new Date()
  const pad = (n: number) => String(n).padStart(2, '0')
  return (
    `${now.getFullYear()}${pad(now.getMonth() + 1)}${pad(now.getDate())}` +
    `_${pad(now.getHours())}${pad(now.getMinutes())}${pad(now.getSeconds())}`
  )
}

/** 导出备份：前端收集 localStorage 数据 POST 给后端合入 zip */
async function handleExportBackup(includeKeys: boolean) {
  if (includeKeys && !confirm(
    '含密钥备份会把服务商 API Key 明文写入 zip 文件。\n\n'
    + '请确认该文件仅用于自己迁移或备份，切勿分享给他人。是否继续？'
  )) {
    return
  }

  exporting.value = true
  try {
    const blob = await exportBackup(includeKeys, collectLocalBackup())
    downloadBlob(blob, `redink_backup_${backupTimestamp()}.zip`)
    feedback.value = {
      type: 'success',
      message: includeKeys
        ? '备份已导出（含 API 密钥，请妥善保管该文件）'
        : '备份已导出（不含 API 密钥）'
    }
  } catch (e) {
    setPromptError(e, '导出备份失败')
  } finally {
    exporting.value = false
  }
}

/** 导入恢复：确认后上传 zip，成功后写回 localStorage 并提示刷新 */
async function handleImportFileSelected(event: Event) {
  const input = event.target as HTMLInputElement
  const file = input.files?.[0]
  // 允许下次选择同一文件仍触发 change
  input.value = ''
  if (!file) return

  if (!confirm(
    `确定要导入备份「${file.name}」吗？\n\n`
    + '导入会用备份内容覆盖现有数据。覆盖前会先把现有数据自动备份到数据目录的 '
    + '.pre_import_backup_ 文件夹，如需回退可从中手动恢复。'
  )) {
    return
  }

  importing.value = true
  try {
    const result = await importBackup(file)
    if (!result.success) {
      setPromptError(result.error || result.error_message || '导入备份失败', '导入备份失败')
      return
    }

    // 备份包内的前端 localStorage 数据（风格模板/水印设置等）写回浏览器
    if (result.local_storage) {
      restoreLocalBackup(result.local_storage)
    }

    const restored = result.restored?.length
      ? `已恢复：${result.restored.join('、')}。`
      : ''
    feedback.value = {
      type: 'success',
      message: `导入完成。${restored}原数据已备份到 ${result.pre_import_backup || '数据目录'}。请刷新页面使数据生效。`
    }
    if (confirm('导入完成，需要刷新页面才能看到恢复后的数据。现在刷新吗？')) {
      location.reload()
    }
  } catch (e) {
    setPromptError(e, '导入备份失败')
  } finally {
    importing.value = false
  }
}

/** 导出诊断包（日志 + 版本/平台信息 + 脱敏配置） */
async function handleExportDiagnostics() {
  diagnosing.value = true
  try {
    const blob = await exportDiagnostics()
    downloadBlob(blob, `redink_diagnostics_${backupTimestamp()}.zip`)
    feedback.value = { type: 'success', message: '诊断包已导出，不含任何 API 密钥，可放心用于问题反馈' }
  } catch (e) {
    setPromptError(e, '导出诊断包失败')
  } finally {
    diagnosing.value = false
  }
}

// ==================== 创作偏好画像 ====================

const profileLoading = ref(true)
const profileError = ref(false)
const profile = ref<PreferenceProfile | null>(null)

/** 编辑习惯信号 -> 展示文案 */
const editingSignalText = computed(() => {
  switch (profile.value?.editing_signal?.tendency) {
    case 'shorten':
      return '常把文案改短，偏好精炼的口语化短句'
    case 'expand':
      return '常把文案改长，偏好充实具体的内容'
    case 'neutral':
      return '有少量编辑，改动幅度不大'
    default:
      return ''
  }
})

/** 加载创作偏好画像（失败只在卡片内提示，不打断页面其他功能） */
async function loadPreferenceProfile() {
  profileLoading.value = true
  profileError.value = false
  try {
    const result = await getPreferenceProfile()
    if (result.success && result.profile) {
      profile.value = result.profile
    } else {
      profileError.value = true
    }
  } catch {
    profileError.value = true
  } finally {
    profileLoading.value = false
  }
}

// ==================== 访问安全（部署级访问令牌） ====================

const accessTokenInput = ref('')
const showAccessToken = ref(false)
/** 已保存的令牌值（仅用于脱敏预览，不回填输入框） */
const savedAccessToken = ref(getAccessToken())

const hasSavedAccessToken = computed(() => savedAccessToken.value !== '')

/** 脱敏预览：前 4 后 4，中间打星（与后端 mask_api_key 约定一致） */
const maskedAccessToken = computed(() => {
  const token = savedAccessToken.value
  if (!token) return ''
  if (token.length <= 8) return '*'.repeat(token.length)
  return token.slice(0, 4) + '*'.repeat(token.length - 8) + token.slice(-4)
})

/** 保存令牌：axios 拦截器与 SSE fetch 每次请求都会重新读取，保存后立即生效 */
function handleSaveAccessToken() {
  const token = accessTokenInput.value.trim()
  if (!token) return
  setAccessToken(token)
  savedAccessToken.value = getAccessToken()
  accessTokenInput.value = ''
  showAccessToken.value = false
  feedback.value = { type: 'success', message: '访问令牌已保存，立即生效（无需刷新页面）' }
}

/** 清除令牌：后续请求不再携带鉴权头 */
function handleClearAccessToken() {
  clearAccessToken()
  savedAccessToken.value = ''
  accessTokenInput.value = ''
  showAccessToken.value = false
  feedback.value = { type: 'success', message: '已清除访问令牌，后续请求不再携带鉴权头' }
}

onMounted(() => {
  loadConfig()
  loadImagePrompt()
  loadPreferenceProfile()
})
</script>

<style scoped>
.settings-container {
  max-width: 900px;
  margin: 0 auto;
}

/* 首配引导：三步开始，克制的浅底卡片 */
.first-run-guide {
  padding: var(--space-4) var(--space-5);
  margin-bottom: var(--space-4);
  background: var(--primary-fade);
  border: 1px solid var(--primary-fade);
  border-radius: var(--radius-md);
}

.first-run-title {
  font-size: var(--font-size-body);
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--primary);
  margin-bottom: var(--space-2);
}

.first-run-steps {
  margin: 0;
  padding: 0;
  list-style: none;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.first-run-steps li {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  line-height: 1.6;
}

.first-run-steps .step-num {
  flex-shrink: 0;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: var(--bg-card);
  color: var(--primary);
  font-size: 12px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.first-run-steps .step-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.first-run-steps .step-link:hover {
  text-decoration: underline;
}

.section-header {
  display: flex;
  justify-content: space-between;
  align-items: flex-start;
  gap: var(--space-4);
  margin-bottom: var(--space-5);
}

.section-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  margin-bottom: var(--space-1);
  color: var(--text-main);
}

.section-desc {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin: 0;
}

/* 图片 Prompt 模板卡片 */
.prompt-short-warning {
  margin-top: var(--space-1);
  color: var(--color-warning);
}

.custom-badge {
  display: inline-block;
  margin-left: var(--space-2);
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-fade);
  border-radius: var(--radius-full);
  vertical-align: middle;
  letter-spacing: normal;
}

.section-desc code {
  padding: 1px 5px;
  font-size: 12px;
  background: var(--gray-2);
  border-radius: var(--radius-sm);
  color: var(--text-main);
}

.prompt-textarea {
  width: 100%;
  min-height: 320px;
  padding: var(--space-3) var(--space-4);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-main);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  resize: vertical;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.prompt-textarea::placeholder {
  color: var(--text-placeholder);
}

.prompt-textarea:hover {
  border-color: var(--border-hover);
}

.prompt-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.prompt-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
  margin-top: var(--space-4);
}

.success-card {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
  padding: var(--space-3) var(--space-4);
  border: 1px solid rgba(31, 169, 92, 0.25);
  background: var(--color-success-soft);
  color: var(--color-success);
  border-radius: var(--radius-md);
  font-size: 14px;
}

.success-card button {
  border: none;
  background: transparent;
  color: var(--color-success);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.success-card button:hover {
  opacity: 0.7;
}

/* 数据管理卡片 */
.data-admin-rows {
  display: flex;
  flex-direction: column;
}

.data-admin-row {
  display: flex;
  justify-content: space-between;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-4) 0;
}

.data-admin-row + .data-admin-row {
  border-top: 1px solid var(--border-color);
}

.data-admin-info {
  min-width: 0;
}

.data-admin-label {
  font-size: var(--font-size-body);
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: var(--space-1);
}

.data-admin-desc {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
}

.data-admin-danger {
  font-size: var(--font-size-caption);
  color: var(--color-danger);
  margin: var(--space-1) 0 0;
  line-height: 1.6;
}

.data-admin-actions {
  display: flex;
  flex-direction: column;
  align-items: stretch;
  gap: var(--space-2);
  flex-shrink: 0;
}

.data-admin-file-input {
  display: none;
}

/* 创作偏好画像卡片 */
.preference-hint {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin: 0;
  line-height: 1.6;
}

.preference-rows {
  display: flex;
  flex-direction: column;
}

.preference-row {
  display: flex;
  align-items: baseline;
  gap: var(--space-4);
  padding: var(--space-3) 0;
}

.preference-row + .preference-row {
  border-top: 1px solid var(--border-color);
}

.preference-label {
  flex-shrink: 0;
  width: 90px;
  font-size: var(--font-size-caption);
  font-weight: 600;
  color: var(--text-main);
}

.preference-value {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  line-height: 1.6;
  min-width: 0;
}

/* 访问安全卡片 */
.token-status {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin: 0 0 var(--space-3);
  line-height: 1.6;
}

.token-preview {
  padding: 1px 5px;
  font-family: var(--font-mono);
  font-size: 12px;
  background: var(--gray-2);
  border-radius: var(--radius-sm);
  color: var(--text-main);
  word-break: break-all;
}

.token-editor {
  display: flex;
  align-items: center;
  gap: var(--space-3);
}

.token-input-wrap {
  position: relative;
  flex: 1;
  min-width: 0;
}

/* 输入框对齐 ProviderModal 的 .form-input 样式 */
.token-input {
  width: 100%;
  padding: 10px 58px 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.token-input::placeholder {
  color: var(--text-placeholder);
}

.token-input:hover {
  border-color: var(--border-hover);
}

.token-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.token-toggle {
  position: absolute;
  right: 8px;
  top: 50%;
  transform: translateY(-50%);
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 12px;
  font-family: inherit;
  padding: 4px 6px;
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.token-toggle:hover {
  color: var(--text-main);
  background: var(--gray-2);
}

.token-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

/* 按钮样式 */
.btn-small {
  padding: 6px 14px;
  font-size: 13px;
  display: inline-flex;
  align-items: center;
  gap: 6px;
  flex-shrink: 0;
}

/* 加载状态：spinner 在浅色画布上用灰槽 + 主色高亮，保证可见 */
.loading-container {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: var(--space-3);
  padding: var(--space-8) var(--space-5);
  color: var(--text-secondary);
  font-size: var(--font-size-caption);
}

.loading-container .spinner {
  border-color: var(--gray-3);
  border-top-color: var(--primary);
}

.loading-container p {
  margin: 0;
}

/* 移动端适配 */
@media (max-width: 640px) {
  .section-header {
    flex-direction: column;
    gap: 10px;
  }

  .data-admin-row {
    flex-direction: column;
    align-items: stretch;
  }

  .token-editor {
    flex-direction: column;
    align-items: stretch;
  }

  .token-actions .btn {
    flex: 1;
  }
}
</style>
