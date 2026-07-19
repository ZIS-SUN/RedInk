<template>
  <!-- 图片服务商编辑/添加弹窗 -->
  <div v-if="visible" class="modal-overlay" @click="$emit('close')">
    <div class="modal-content" @click.stop>
      <div class="modal-header">
        <h3>{{ isEditing ? '编辑服务商' : '添加服务商' }}</h3>
        <button class="close-btn" @click="$emit('close')">×</button>
      </div>

      <div class="modal-body">
        <!-- 服务商名称（仅添加时显示） -->
        <div class="form-group" v-if="!isEditing">
          <label>服务商名称</label>
          <input
            type="text"
            class="form-input"
            :value="formData.name"
            @input="updateField('name', ($event.target as HTMLInputElement).value)"
            placeholder="例如: google_genai"
          />
          <span class="form-hint">唯一标识，用于区分不同服务商</span>
        </div>

        <!-- 类型选择 -->
        <div class="form-group">
          <label>类型</label>
          <select
            class="form-select"
            :value="formData.type"
            @change="updateField('type', ($event.target as HTMLSelectElement).value)"
          >
            <option v-for="opt in typeOptions" :key="opt.value" :value="opt.value">
              {{ opt.label }}
            </option>
          </select>
        </div>

        <!-- API Key -->
        <div class="form-group">
          <label>API Key</label>
          <input
            type="text"
            class="form-input"
            :value="formData.api_key"
            @input="updateField('api_key', ($event.target as HTMLInputElement).value)"
            :placeholder="isEditing && formData._has_api_key ? formData.api_key_masked : '输入 API Key'"
          />
          <span class="form-hint" v-if="isEditing && formData._has_api_key">
            已配置 API Key，留空表示不修改
          </span>
        </div>

        <!-- Base URL -->
        <div class="form-group" v-if="showBaseUrl">
          <label>Base URL</label>
          <input
            type="text"
            class="form-input"
            :value="formData.base_url"
            @input="updateField('base_url', ($event.target as HTMLInputElement).value)"
            placeholder="例如: https://generativelanguage.googleapis.com"
          />
          <span class="form-hint" v-if="previewUrl">
            预览: {{ previewUrl }}
          </span>
        </div>

        <!-- 模型 -->
        <div class="form-group">
          <label>模型</label>
          <input
            type="text"
            class="form-input"
            :value="formData.model"
            @input="updateField('model', ($event.target as HTMLInputElement).value)"
            :placeholder="modelPlaceholder"
          />
        </div>

        <!-- 端点路径（仅 OpenAI 兼容接口） -->
        <div class="form-group" v-if="showEndpointType">
          <label>API 端点路径</label>
          <input
            type="text"
            class="form-input"
            :value="formData.endpoint_type"
            @input="updateField('endpoint_type', ($event.target as HTMLInputElement).value)"
            placeholder="例如: /v1/images/generations 或 /v1/chat/completions"
          />
          <span class="form-hint">
            常用端点：/v1/images/generations（标准图片生成）、/v1/chat/completions（即梦等返回链接的 API）
          </span>
        </div>

        <!-- 高并发模式 -->
        <div class="form-group">
          <label class="toggle-label">
            <span>高并发模式</span>
            <div
              class="toggle-switch"
              :class="{ active: formData.high_concurrency }"
              @click="updateField('high_concurrency', !formData.high_concurrency)"
            >
              <div class="toggle-slider"></div>
            </div>
          </label>
          <span class="form-hint">
            启用后将并行生成图片，速度更快但对 API 质量要求较高。GCP 300$ 试用账号不建议启用。
          </span>
        </div>

        <!-- 短 Prompt 模式 -->
        <div class="form-group">
          <label class="toggle-label">
            <span>短 Prompt 模式</span>
            <div
              class="toggle-switch"
              :class="{ active: formData.short_prompt }"
              @click="updateField('short_prompt', !formData.short_prompt)"
            >
              <div class="toggle-slider"></div>
            </div>
          </label>
          <span class="form-hint">
            启用后使用精简版提示词，适合有字符限制的 API（如即梦 1600 字符限制）。
          </span>
        </div>
      </div>

      <div class="modal-footer">
        <button class="btn" @click="$emit('close')">取消</button>
        <button
          class="btn btn-secondary"
          @click="$emit('test')"
          :disabled="testing || (!formData.api_key && !isEditing)"
        >
          <span v-if="testing" class="spinner-small"></span>
          {{ testing ? '测试中...' : '测试连接' }}
        </button>
        <button class="btn btn-primary" @click="$emit('save')">
          {{ isEditing ? '保存' : '添加' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed } from 'vue'
import type { ImageProviderForm } from '../../composables/useProviderForm'

/**
 * 图片服务商编辑/添加弹窗组件
 *
 * 功能：
 * - 添加新服务商
 * - 编辑现有服务商
 * - 测试连接
 * - 支持高并发模式和短 Prompt 模式开关
 */

// 定义类型选项
interface TypeOption {
  value: string
  label: string
}

// 定义 Props
const props = defineProps<{
  visible: boolean
  isEditing: boolean
  formData: ImageProviderForm
  testing: boolean
  typeOptions: TypeOption[]
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'close'): void
  (e: 'save'): void
  (e: 'test'): void
  (e: 'update:formData', data: ImageProviderForm): void
}>()

// 更新表单字段
function updateField(field: keyof ImageProviderForm, value: string | boolean) {
  emit('update:formData', {
    ...props.formData,
    [field]: value
  })
}

// 是否显示 Base URL
const showBaseUrl = computed(() => {
  return ['image_api', 'google_genai'].includes(props.formData.type)
})

// 是否显示端点类型
const showEndpointType = computed(() => {
  return props.formData.type === 'image_api'
})

// 模型占位符
const modelPlaceholder = computed(() => {
  switch (props.formData.type) {
    case 'google_genai':
      return '例如: imagen-3.0-generate-002'
    case 'image_api':
      return '例如: flux-pro'
    default:
      return '例如: gpt-4o'
  }
})

// 预览 URL
const previewUrl = computed(() => {
  if (!props.formData.base_url) return ''

  const baseUrl = props.formData.base_url.replace(/\/$/, '').replace(/\/v1$/, '')

  switch (props.formData.type) {
    case 'image_api': {
      // 使用用户自定义的端点路径
      let endpoint = props.formData.endpoint_type || '/v1/images/generations'
      if (!endpoint.startsWith('/')) {
        endpoint = '/' + endpoint
      }
      return `${baseUrl}${endpoint}`
    }
    case 'google_genai':
      return `${baseUrl}/v1beta/models/${props.formData.model || '{model}'}:generateImages`
    default:
      return ''
  }
})
</script>

<style scoped>
/* 模态框遮罩 */
.modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-5);
}

/* 模态框内容 */
.modal-content {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 500px;
  max-height: 90vh;
  overflow: hidden;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
}

/* 头部 */
.modal-header {
  padding: var(--space-5);
  border-bottom: 1px solid var(--border-color);
  display: flex;
  justify-content: space-between;
  align-items: center;
}

.modal-header h3 {
  margin: 0;
  font-size: 18px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.close-btn {
  background: none;
  border: none;
  font-size: 24px;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 2px 6px;
  line-height: 1;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-btn:hover {
  color: var(--text-main);
  background: var(--gray-2);
}

/* 主体 */
.modal-body {
  padding: var(--space-5);
  overflow-y: auto;
  flex: 1;
}

/* 表单组 */
.form-group {
  margin-bottom: var(--space-5);
}

.form-group:last-child {
  margin-bottom: 0;
}

.form-group label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: var(--space-2);
}

/* 输入框对齐全局 .input 的新样式 */
.form-input {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.form-input::placeholder {
  color: var(--text-placeholder);
}

.form-input:hover {
  border-color: var(--border-hover);
}

.form-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.form-select {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.form-select:hover {
  border-color: var(--border-hover);
}

.form-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.form-hint {
  display: block;
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
}

/* Toggle 开关样式 */
.toggle-label {
  display: flex;
  align-items: center;
  justify-content: space-between;
  cursor: pointer;
}

.toggle-switch {
  width: 44px;
  height: 24px;
  background: var(--gray-4);
  border-radius: var(--radius-full);
  position: relative;
  transition: background var(--transition-fast);
  flex-shrink: 0;
}

.toggle-switch.active {
  background: var(--primary);
}

.toggle-slider {
  width: 20px;
  height: 20px;
  background: white;
  border-radius: var(--radius-full);
  position: absolute;
  top: 2px;
  left: 2px;
  transition: transform var(--transition-fast);
  box-shadow: 0 1px 3px rgba(33, 30, 27, 0.2);
}

.toggle-switch.active .toggle-slider {
  transform: translateX(20px);
}

/* 底部 */
.modal-footer {
  padding: var(--space-4) var(--space-5);
  border-top: 1px solid var(--border-color);
  display: flex;
  justify-content: flex-end;
  gap: var(--space-3);
}

/* 按钮样式（对齐全局 .btn 语义） */
.btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 9px 18px;
  border-radius: var(--radius-md);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  letter-spacing: var(--tracking-tight);
  cursor: pointer;
  border: 1px solid var(--border-hover);
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.btn:hover:not(:disabled) {
  background: var(--gray-0);
  border-color: var(--gray-5);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.btn-primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  box-shadow: var(--shadow-xs), 0 4px 12px var(--primary-fade);
}

.btn-primary:hover:not(:disabled) {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
}

.btn-secondary {
  background: var(--gray-2);
  border-color: transparent;
  color: var(--text-sub);
  box-shadow: none;
}

.btn-secondary:hover:not(:disabled) {
  background: var(--gray-3);
  border-color: transparent;
  color: var(--text-main);
}

.btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
  transform: none;
  box-shadow: none;
}

/* 加载动画 */
.spinner-small {
  display: inline-block;
  width: 14px;
  height: 14px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: 50%;
  animation: spin 1s linear infinite;
  margin-right: 6px;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
