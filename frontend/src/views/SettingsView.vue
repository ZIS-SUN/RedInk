<template>
  <div class="container">
    <div class="page-header">
      <h1 class="page-title">系统设置</h1>
      <p class="page-subtitle">配置文本生成和图片生成的 API 服务</p>
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
import { getImagePrompt, saveImagePrompt, resetImagePrompt } from '../api'
import { normalizeApiError } from '../utils/errors'
import { hasConfiguredProvider } from '../utils/providerConfig'
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

onMounted(() => {
  loadConfig()
  loadImagePrompt()
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
}
</style>
