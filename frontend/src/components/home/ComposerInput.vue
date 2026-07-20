<template>
  <!-- 主题输入组合框 -->
  <div class="composer-container">
    <!-- 输入区域 -->
    <div class="composer-input-wrapper">
      <div class="search-icon-static">
        <svg width="24" height="24" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
          <path d="M21 21L16.65 16.65M19 11C19 15.4183 15.4183 19 11 19C6.58172 19 3 15.4183 3 11C3 6.58172 6.58172 3 11 3C15.4183 3 19 6.58172 19 11Z" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
        </svg>
      </div>
      <textarea
        ref="textareaRef"
        :value="modelValue"
        @input="handleInput"
        class="composer-textarea"
        placeholder="输入主题，例如：秋季显白美甲..."
        @keydown.enter.prevent="handleEnter"
        :disabled="loading"
        rows="1"
      ></textarea>
    </div>

    <!-- 目标搜索词（选填）：可折叠的搜索埋词输入 -->
    <div class="seo-section">
      <button
        type="button"
        class="seo-toggle"
        :aria-expanded="seoExpanded"
        aria-controls="seo-keywords-area"
        @click="seoExpanded = !seoExpanded"
      >
        <svg
          class="seo-chevron"
          :class="{ expanded: seoExpanded }"
          width="14"
          height="14"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          stroke-width="2"
          stroke-linecap="round"
          stroke-linejoin="round"
          aria-hidden="true"
        >
          <polyline points="9 18 15 12 9 6"></polyline>
        </svg>
        <span>目标搜索词（选填）</span>
        <span v-if="store.seoKeywords.length > 0" class="seo-badge">{{ store.seoKeywords.length }}</span>
      </button>

      <div v-if="seoExpanded" id="seo-keywords-area" class="seo-body">
        <input
          v-model="seoRawInput"
          type="text"
          class="seo-input"
          placeholder="最多 3 个，用逗号或顿号分隔，例如：秋冬穿搭、显瘦穿搭"
          :disabled="loading"
          @input="handleSeoInput"
        />
        <p class="seo-guide">从小红书搜索框下拉联想或创作中心「笔记灵感」里抄 1-3 个词，能吃到搜索流量</p>
        <div v-if="store.seoKeywords.length > 0" class="seo-chips" aria-label="已识别的搜索词">
          <span v-for="word in store.seoKeywords" :key="word" class="seo-chip">{{ word }}</span>
        </div>
      </div>
    </div>

    <!-- 已上传图片预览 -->
    <div v-if="uploadedImages.length > 0" class="uploaded-images-preview">
      <div
        v-for="(img, idx) in uploadedImages"
        :key="idx"
        class="uploaded-image-item"
      >
        <img :src="img.preview" :alt="`图片 ${idx + 1}`" />
        <button class="remove-image-btn" @click="removeImage(idx)">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <line x1="18" y1="6" x2="6" y2="18"></line>
            <line x1="6" y1="6" x2="18" y2="18"></line>
          </svg>
        </button>
      </div>
      <div class="upload-hint">
        这些图片将用于生成封面和内容参考
      </div>
    </div>

    <!-- 工具栏 -->
    <div class="composer-toolbar">
      <div class="toolbar-left">
        <label class="tool-btn" :class="{ 'active': uploadedImages.length > 0 }" title="上传参考图">
          <input
            type="file"
            accept="image/*"
            multiple
            @change="handleImageUpload"
            :disabled="loading"
            style="display: none;"
          />
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect>
            <circle cx="8.5" cy="8.5" r="1.5"></circle>
            <polyline points="21 15 16 10 5 21"></polyline>
          </svg>
          <span v-if="uploadedImages.length > 0" class="badge-count">{{ uploadedImages.length }}</span>
        </label>
      </div>
      <div class="toolbar-right">
        <button
          class="btn btn-primary generate-btn"
          @click="$emit('generate')"
          :disabled="!modelValue.trim() || loading"
        >
          <span v-if="loading" class="spinner-sm"></span>
          <span>{{ loading ? '生成中' : '生成大纲' }}</span>
        </button>
      </div>
    </div>

    <!-- 上传校验提示：超限/超大小时内联提示，几秒后自动消失 -->
    <div v-if="uploadHint" class="upload-limit-hint" role="status" aria-live="polite">
      {{ uploadHint }}
    </div>

    <div v-if="loading" class="loading-hint" role="status" aria-live="polite">
      请稍后，这一步大概要 15-30 秒左右。
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, onUnmounted } from 'vue'
import { useGeneratorStore } from '../../stores/generator'

/**
 * 主题输入组合框组件
 *
 * 功能：
 * - 主题文本输入（自动调整高度）
 * - 目标搜索词输入（可折叠，选填，用于小红书搜索埋词）
 * - 参考图片上传（最多5张）
 * - 生成按钮
 */

// 定义上传的图片类型
interface UploadedImage {
  file: File
  preview: string
}

// 定义 Props（模板中直接使用，无需保留赋值）
defineProps<{
  modelValue: string
  loading: boolean
}>()

// 定义 Emits
const emit = defineEmits<{
  (e: 'update:modelValue', value: string): void
  (e: 'generate'): void
  (e: 'imagesChange', images: File[]): void
}>()

// 输入框引用
const textareaRef = ref<HTMLTextAreaElement | null>(null)

// 已上传的图片
const uploadedImages = ref<UploadedImage[]>([])

// ==================== 目标搜索词（搜索埋词） ====================

// 搜索词直接读写 generator store（随 store 的 localStorage 机制持久化）
const store = useGeneratorStore()

// 折叠状态：store 里已有搜索词（如从大纲页返回）时默认展开
const seoExpanded = ref(store.seoKeywords.length > 0)

// 搜索词原始输入文本（保留用户的分隔符书写习惯，解析结果才进 store）
const seoRawInput = ref(store.seoKeywords.join('、'))

/**
 * 把原始输入解析为搜索词数组：
 * 支持中英文逗号与顿号分隔；去空白、去重后最多保留 3 个
 */
function parseSeoKeywords(raw: string): string[] {
  const words: string[] = []
  for (const part of raw.split(/[,，、]/)) {
    const word = part.trim()
    if (word && !words.includes(word)) {
      words.push(word)
    }
  }
  return words.slice(0, 3)
}

/**
 * 输入即解析写入 store（setter 内还有一层同规则归一化兜底）
 */
function handleSeoInput() {
  store.setSeoKeywords(parseSeoKeywords(seoRawInput.value))
}

// 参考图数量上限与单张大小上限（后端按解码后 20MB 限制，前端按文件大小近似校验）
const MAX_IMAGES = 5
const MAX_IMAGE_SIZE = 20 * 1024 * 1024

// 上传校验提示文案（空字符串不显示），几秒后自动消失
const uploadHint = ref('')
let uploadHintTimer: number | null = null

/**
 * 显示上传校验提示，4 秒后自动消失
 */
function showUploadHint(message: string) {
  uploadHint.value = message
  if (uploadHintTimer !== null) {
    clearTimeout(uploadHintTimer)
  }
  uploadHintTimer = window.setTimeout(() => {
    uploadHint.value = ''
    uploadHintTimer = null
  }, 4000)
}

/**
 * 处理输入变化
 */
function handleInput(event: Event) {
  const target = event.target as HTMLTextAreaElement
  emit('update:modelValue', target.value)
  adjustHeight()
}

/**
 * 处理回车键
 */
function handleEnter(e: KeyboardEvent) {
  if (e.shiftKey) return // 允许 Shift+Enter 换行
  emit('generate')
}

/**
 * 自动调整输入框高度
 */
function adjustHeight() {
  const el = textareaRef.value
  if (!el) return

  el.style.height = 'auto'
  const newHeight = Math.max(64, Math.min(el.scrollHeight, 200))
  el.style.height = newHeight + 'px'
}

/**
 * 处理图片上传：
 * - 单张超过 20MB 的图片直接拒绝并提示
 * - 超出 5 张上限时保留前 5 张并提示，不再静默丢弃
 */
function handleImageUpload(event: Event) {
  const target = event.target as HTMLInputElement
  if (!target.files) return

  const files = Array.from(target.files)

  // 先过滤超大文件，避免占用数量名额
  const oversized = files.filter(file => file.size > MAX_IMAGE_SIZE)
  const validFiles = files.filter(file => file.size <= MAX_IMAGE_SIZE)

  let exceededLimit = false
  validFiles.forEach((file) => {
    // 限制最多 5 张图片
    if (uploadedImages.value.length >= MAX_IMAGES) {
      exceededLimit = true
      return
    }
    // 创建预览 URL
    const preview = URL.createObjectURL(file)
    uploadedImages.value.push({ file, preview })
  })

  // 组合提示：大小超限优先说明，数量超限说明只保留了前 5 张
  const hints: string[] = []
  if (oversized.length > 0) {
    hints.push('单张需小于 20MB，已忽略超出的图片')
  }
  if (exceededLimit) {
    hints.push('最多 5 张参考图，已保留前 5 张')
  }
  if (hints.length > 0) {
    showUploadHint(hints.join('；'))
  }

  // 通知父组件
  emitImagesChange()

  // 清空 input，允许重复选择同一文件
  target.value = ''
}

/**
 * 移除图片
 */
function removeImage(index: number) {
  const img = uploadedImages.value[index]
  // 释放预览 URL
  URL.revokeObjectURL(img.preview)
  uploadedImages.value.splice(index, 1)

  // 通知父组件
  emitImagesChange()
}

/**
 * 通知父组件图片变化
 */
function emitImagesChange() {
  const files = uploadedImages.value.map(img => img.file)
  emit('imagesChange', files)
}

/**
 * 清理所有预览 URL
 */
function clearPreviews() {
  uploadedImages.value.forEach(img => URL.revokeObjectURL(img.preview))
  uploadedImages.value = []
}

// 组件卸载时清理
onUnmounted(() => {
  clearPreviews()
  if (uploadHintTimer !== null) {
    clearTimeout(uploadHintTimer)
    uploadHintTimer = null
  }
})

// 暴露方法给父组件
defineExpose({
  clearPreviews
})
</script>

<style scoped>
/* 组合框容器：首页第一视觉焦点，干净的白卡 + 柔和多层阴影 + 大而柔的圆角 */
.composer-container {
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  padding: var(--space-4) var(--space-5);
  box-shadow: var(--shadow-md);
  border: 1px solid var(--border-color);
  transition: border-color var(--transition-base), box-shadow var(--transition-base);
}

.composer-container:focus-within {
  border-color: var(--border-hover);
  box-shadow: var(--shadow-hover);
}

/* 输入区域 */
.composer-input-wrapper {
  display: flex;
  align-items: flex-start;
  gap: var(--space-3);
}

.search-icon-static {
  flex-shrink: 0;
  padding-top: 8px;
  color: var(--text-placeholder);
}

.composer-textarea {
  flex: 1;
  border: none;
  outline: none;
  font-size: 16px;
  line-height: 1.6;
  resize: none;
  min-height: 44px;
  max-height: 200px;
  padding: 8px 0;
  font-family: inherit;
  background: transparent;
  color: var(--text-main);
}

.composer-textarea::placeholder {
  color: var(--text-placeholder);
}

.composer-textarea:disabled {
  background: transparent;
  color: var(--text-placeholder);
}

/* ==================== 目标搜索词（搜索埋词） ==================== */
.seo-section {
  margin-top: var(--space-2);
}

/* 折叠开关：安静的文字按钮，不与主输入框争夺注意力 */
.seo-toggle {
  display: inline-flex;
  align-items: center;
  gap: var(--space-1);
  padding: 4px 8px;
  margin-left: -8px;
  border: none;
  border-radius: var(--radius-sm);
  background: transparent;
  color: var(--text-sub);
  font-size: 13px;
  font-weight: 500;
  font-family: inherit;
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast);
}

.seo-toggle:hover {
  color: var(--text-main);
  background: var(--gray-1);
}

.seo-chevron {
  flex-shrink: 0;
  transition: transform var(--transition-fast);
}

.seo-chevron.expanded {
  transform: rotate(90deg);
}

.seo-badge {
  min-width: 18px;
  height: 18px;
  padding: 0 4px;
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: var(--primary-light);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
}

.seo-body {
  margin-top: var(--space-2);
  padding: var(--space-3);
  background: var(--gray-1);
  border-radius: var(--radius-md);
}

.seo-input {
  width: 100%;
  padding: 8px 12px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  color: var(--text-main);
  font-size: 14px;
  font-family: inherit;
  outline: none;
  transition: border-color var(--transition-fast);
}

.seo-input:focus {
  border-color: var(--primary);
}

.seo-input:disabled {
  color: var(--text-placeholder);
  cursor: not-allowed;
}

.seo-input::placeholder {
  color: var(--text-placeholder);
}

/* 引导文案：告诉用户去哪里抄词 */
.seo-guide {
  margin: var(--space-2) 0 0;
  font-size: 12px;
  line-height: 1.5;
  color: var(--text-secondary);
  text-align: left;
}

.seo-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-1);
  margin-top: var(--space-2);
}

.seo-chip {
  padding: 2px 10px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: 12px;
  font-weight: 500;
}

/* 已上传图片预览 */
.uploaded-images-preview {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
  margin-top: var(--space-4);
  padding: var(--space-4);
  background: var(--gray-1);
  border-radius: var(--radius-md);
  align-items: center;
}

.uploaded-image-item {
  position: relative;
  width: 60px;
  height: 60px;
  border-radius: var(--radius-sm);
  overflow: hidden;
  box-shadow: var(--shadow-xs);
  transition: box-shadow var(--transition-fast), transform var(--transition-fast);
}

.uploaded-image-item:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.uploaded-image-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
}

.remove-image-btn {
  position: absolute;
  top: 2px;
  right: 2px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: rgba(33, 30, 27, 0.6);
  border: none;
  cursor: pointer;
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  opacity: 0;
  transition: opacity var(--transition-fast), background var(--transition-fast);
}

.uploaded-image-item:hover .remove-image-btn,
.remove-image-btn:focus-visible {
  opacity: 1;
}

.remove-image-btn:hover {
  background: var(--primary);
}

.upload-hint {
  flex: 1;
  font-size: 12px;
  color: var(--text-secondary);
  text-align: right;
}

/* 工具栏 */
.composer-toolbar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-top: var(--space-3);
  padding-top: var(--space-3);
  border-top: 1px solid var(--border-color);
}

.toolbar-left {
  display: flex;
  gap: var(--space-2);
}

.tool-btn {
  display: flex;
  align-items: center;
  justify-content: center;
  position: relative;
  width: 40px;
  height: 40px;
  border-radius: var(--radius-md);
  background: var(--gray-2);
  border: none;
  cursor: pointer;
  color: var(--text-sub);
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
}

.tool-btn:hover {
  background: var(--gray-3);
  color: var(--text-main);
  transform: translateY(-1px);
  box-shadow: var(--shadow-xs);
}

.tool-btn:active {
  transform: translateY(0);
  box-shadow: none;
}

.tool-btn.active {
  background: var(--primary-light);
  color: var(--primary);
}

.badge-count {
  position: absolute;
  top: -4px;
  right: -4px;
  min-width: 18px;
  height: 18px;
  background: var(--primary);
  color: white;
  border-radius: var(--radius-full);
  font-size: 11px;
  font-weight: 600;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 0 4px;
}

/* 生成按钮 */
.generate-btn {
  min-width: 112px;
  padding: 10px 24px;
  font-size: 15px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.generate-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.loading-hint {
  margin-top: var(--space-3);
  padding: 10px 12px;
  border-radius: var(--radius-sm);
  background: var(--gray-1);
  color: var(--text-sub);
  font-size: 14px;
  line-height: 1.5;
  text-align: right;
}

/* 上传校验提示：warning 色内联小字，几秒后自动消失 */
.upload-limit-hint {
  margin-top: var(--space-2);
  font-size: 12px;
  line-height: 1.5;
  color: var(--color-warning);
  text-align: left;
}

/* 加载动画 */
.spinner-sm {
  width: 16px;
  height: 16px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: var(--radius-full);
  animation: spin 1s linear infinite;
}

@keyframes spin {
  to {
    transform: rotate(360deg);
  }
}
</style>
