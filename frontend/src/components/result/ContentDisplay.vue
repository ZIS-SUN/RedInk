<template>
  <div class="content-display">
    <!-- 生成按钮 -->
    <div v-if="content.status === 'idle'" class="generate-section">
      <button class="btn btn-primary generate-btn" @click="handleGenerate" :disabled="loading">
        <svg v-if="!loading" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
          <path d="M12 5v14M5 12h14"/>
        </svg>
        <span v-if="loading" class="spinner"></span>
        {{ loading ? '生成中...' : '生成标题、文案和标签' }}
      </button>
    </div>

    <!-- 加载状态 -->
    <div v-else-if="content.status === 'generating'" class="loading-section">
      <div class="loading-spinner"></div>
      <p>正在生成标题、文案和标签...</p>
    </div>

    <!-- 错误状态 -->
    <div v-else-if="content.status === 'error'" class="error-section">
      <div class="error-icon">!</div>
      <p class="error-message">{{ content.error || '生成失败，请重试' }}</p>
      <button class="btn btn-secondary" @click="handleGenerate">重新生成</button>
    </div>

    <!-- 生成结果 -->
    <div v-else-if="content.status === 'done'" class="result-section">
      <!-- 标题区域 -->
      <div class="content-card">
        <div class="card-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M4 6h16M4 12h16M4 18h10"/>
            </svg>
            标题
          </h3>
          <button class="copy-btn" @click="copyTitles" :class="{ copied: copiedTitles }">
            <svg v-if="!copiedTitles" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            {{ copiedTitles ? '已复制' : '复制' }}
          </button>
        </div>
        <div class="titles-list">
          <div v-for="(title, index) in content.titles" :key="index" class="title-item" @click="copyTitle(title, index)">
            <span class="title-badge">{{ index === 0 ? '推荐' : `备选${index}` }}</span>
            <template v-if="editingTitleIndex === index">
              <input
                :ref="setTitleInputRef"
                v-model="editingTitleText"
                class="title-edit-input"
                @click.stop
                @keydown.enter.prevent="confirmTitleEdit"
                @keydown.esc="cancelTitleEdit"
                @blur="confirmTitleEdit"
              />
            </template>
            <template v-else>
              <span class="title-text">{{ title }}</span>
              <span class="copy-hint" :class="{ show: copiedTitleIndex === index }">
                {{ copiedTitleIndex === index ? '已复制' : '点击复制' }}
              </span>
              <button class="item-icon-btn" title="编辑标题" aria-label="编辑标题" @click.stop="startEditTitle(index)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/></svg>
              </button>
              <button class="item-icon-btn danger" title="删除标题" aria-label="删除标题" @click.stop="handleRemoveTitle(index)">
                <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
              </button>
            </template>
          </div>
        </div>
      </div>

      <!-- 文案区域 -->
      <div class="content-card">
        <div class="card-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/>
              <polyline points="14 2 14 8 20 8"/>
              <line x1="16" y1="13" x2="8" y2="13"/>
              <line x1="16" y1="17" x2="8" y2="17"/>
            </svg>
            文案
          </h3>
          <div class="header-actions">
            <button v-if="!editingCopywriting" class="copy-btn" @click="startEditCopywriting">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                <path d="M17 3a2.828 2.828 0 1 1 4 4L7.5 20.5 2 22l1.5-5.5L17 3z"/>
              </svg>
              编辑
            </button>
            <button class="copy-btn" @click="copyCopywriting" :class="{ copied: copiedCopywriting }">
              <svg v-if="!copiedCopywriting" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
                <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
              </svg>
              <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                <polyline points="20 6 9 17 4 12"/>
              </svg>
              {{ copiedCopywriting ? '已复制' : '复制' }}
            </button>
          </div>
        </div>
        <div v-if="editingCopywriting" class="copywriting-edit">
          <textarea
            ref="copywritingTextareaRef"
            v-model="editingCopywritingText"
            class="copywriting-textarea"
            placeholder="在此输入文案..."
          />
          <div class="copywriting-edit-actions">
            <button class="copy-btn" @click="cancelCopywritingEdit">取消</button>
            <button class="copy-btn primary" @click="saveCopywriting">保存</button>
          </div>
        </div>
        <div v-else class="copywriting-content">
          <p v-for="(paragraph, index) in formattedCopywriting" :key="index">{{ paragraph }}</p>
        </div>
      </div>

      <!-- 标签区域 -->
      <div class="content-card">
        <div class="card-header">
          <h3>
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <path d="M20.59 13.41l-7.17 7.17a2 2 0 0 1-2.83 0L2 12V2h10l8.59 8.59a2 2 0 0 1 0 2.82z"/>
              <line x1="7" y1="7" x2="7.01" y2="7"/>
            </svg>
            标签
          </h3>
          <button class="copy-btn" @click="copyTags" :class="{ copied: copiedTags }">
            <svg v-if="!copiedTags" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <rect x="9" y="9" width="13" height="13" rx="2" ry="2"/>
              <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            <svg v-else viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            {{ copiedTags ? '已复制' : '复制全部' }}
          </button>
        </div>
        <div class="tags-list">
          <span
            v-for="(tag, index) in content.tags"
            :key="index"
            class="tag-item"
            @click="copyTag(tag, index)"
            :class="{ copied: copiedTagIndex === index }"
          >
            #{{ tag }}
            <button class="tag-remove" title="删除标签" aria-label="删除标签" @click.stop="handleRemoveTag(index)">
              <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5" stroke-linecap="round"><line x1="18" y1="6" x2="6" y2="18"/><line x1="6" y1="6" x2="18" y2="18"/></svg>
            </button>
          </span>
          <input
            v-model="newTagInput"
            class="tag-input"
            placeholder="+ 添加标签，回车确认"
            @keydown.enter.prevent="handleAddTag"
          />
        </div>
      </div>

      <!-- 重新生成按钮 -->
      <div class="regenerate-section">
        <button class="btn btn-secondary" @click="handleGenerate" :disabled="loading">
          <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
            <path d="M23 4v6h-6M1 20v-6h6"/>
            <path d="M3.51 9a9 9 0 0 1 14.85-3.36L23 10M1 14l4.64 4.36A9 9 0 0 0 20.49 15"/>
          </svg>
          {{ loading ? '重新生成中…' : '重新生成' }}
        </button>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed, nextTick, onUnmounted } from 'vue'
import { useGeneratorStore } from '../../stores/generator'
import { generateContent, updateHistory } from '../../api'
import { formatErrorMessage } from '../../utils/errors'
import { addTag, removeAt } from '../../utils/contentEdit'

const store = useGeneratorStore()

const loading = ref(false)
const copiedTitles = ref(false)
const copiedCopywriting = ref(false)
const copiedTags = ref(false)
const copiedTitleIndex = ref<number | null>(null)
const copiedTagIndex = ref<number | null>(null)
const copyTimers: number[] = []

function setCopyTimeout(fn: () => void, ms: number) {
  const id = window.setTimeout(() => {
    fn()
    const idx = copyTimers.indexOf(id)
    if (idx !== -1) copyTimers.splice(idx, 1)
  }, ms)
  copyTimers.push(id)
}

onUnmounted(() => {
  copyTimers.forEach(id => clearTimeout(id))
  copyTimers.length = 0
  if (contentSyncTimer !== null) {
    clearTimeout(contentSyncTimer)
    contentSyncTimer = null
  }
})

const content = computed(() => store.content)

// ==================== content 同步落库 ====================
// 生成成功与每次编辑保存后，防抖 800ms 把标题/文案/标签同步进历史记录。
// 失败静默（本地 store 已持久化到 localStorage，不打扰用户）。
let contentSyncTimer: number | null = null

function scheduleContentSync() {
  if (!store.recordId) return
  if (contentSyncTimer !== null) clearTimeout(contentSyncTimer)
  contentSyncTimer = window.setTimeout(async () => {
    contentSyncTimer = null
    const recordId = store.recordId
    if (!recordId) return
    const result = await updateHistory(recordId, {
      content: {
        titles: [...store.content.titles],
        copywriting: store.content.copywriting,
        tags: [...store.content.tags]
      }
    })
    if (!result.success) {
      console.warn('同步发布内容到历史记录失败:', result.error_message || result.error)
    }
  }, 800)
}

// 格式化文案（按换行分段）
const formattedCopywriting = computed(() => {
  if (!content.value.copywriting) return []
  return content.value.copywriting.split('\n').filter(p => p.trim())
})

// 生成内容
async function handleGenerate() {
  if (loading.value) return

  loading.value = true
  store.startContentGeneration()

  try {
    const result = await generateContent(
      store.topic,
      store.outline.raw,
      store.brandId || undefined
    )

    if (result.success && result.titles && result.copywriting && result.tags) {
      store.setContent(result.titles, result.copywriting, result.tags)
      scheduleContentSync()
    } else {
      store.setContentError(formatErrorMessage(result.error || result.error_message || '生成失败', '内容生成失败'))
    }
  } catch (error: unknown) {
    store.setContentError(formatErrorMessage(error, '内容生成失败'))
  } finally {
    loading.value = false
  }
}

// 复制到剪贴板
async function copyToClipboard(text: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(text)
    return true
  } catch {
    // 降级方案
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

// 复制所有标题
async function copyTitles() {
  const text = content.value.titles.join('\n')
  if (await copyToClipboard(text)) {
    copiedTitles.value = true
    setCopyTimeout(() => copiedTitles.value = false, 2000)
  }
}

// 复制单个标题
async function copyTitle(title: string, index: number) {
  // 编辑中的标题行不响应点击复制
  if (editingTitleIndex.value === index) return
  if (await copyToClipboard(title)) {
    copiedTitleIndex.value = index
    setCopyTimeout(() => copiedTitleIndex.value = null, 2000)
  }
}

// ==================== 标题编辑 ====================
const editingTitleIndex = ref<number | null>(null)
const editingTitleText = ref('')
// v-for 内同一时刻只渲染一个编辑输入框，用函数 ref 拿到元素
let titleInputEl: HTMLInputElement | null = null
function setTitleInputRef(el: unknown) {
  titleInputEl = (el as HTMLInputElement) || null
}

async function startEditTitle(index: number) {
  editingTitleIndex.value = index
  editingTitleText.value = content.value.titles[index]
  await nextTick()
  titleInputEl?.focus()
}

// Enter/blur 确认：空内容视为无效，store 内部会忽略
function confirmTitleEdit() {
  if (editingTitleIndex.value === null) return
  store.updateContentTitle(editingTitleIndex.value, editingTitleText.value)
  editingTitleIndex.value = null
  scheduleContentSync()
}

// Esc 取消：先置空索引，随后的 blur 会因索引为 null 而不再保存
function cancelTitleEdit() {
  editingTitleIndex.value = null
}

function handleRemoveTitle(index: number) {
  store.removeContentTitle(index)
  scheduleContentSync()
}

// ==================== 文案编辑 ====================
const editingCopywriting = ref(false)
const editingCopywritingText = ref('')
const copywritingTextareaRef = ref<HTMLTextAreaElement | null>(null)

async function startEditCopywriting() {
  editingCopywritingText.value = content.value.copywriting
  editingCopywriting.value = true
  await nextTick()
  copywritingTextareaRef.value?.focus()
}

function saveCopywriting() {
  store.updateCopywriting(editingCopywritingText.value)
  editingCopywriting.value = false
  scheduleContentSync()
}

function cancelCopywritingEdit() {
  editingCopywriting.value = false
}

// ==================== 标签编辑 ====================
const newTagInput = ref('')

// Enter 添加：自动去掉开头 # 和空白、去重（纯逻辑在 utils/contentEdit）
function handleAddTag() {
  const next = addTag(content.value.tags, newTagInput.value)
  if (next !== content.value.tags) {
    store.updateTags(next)
    scheduleContentSync()
  }
  newTagInput.value = ''
}

function handleRemoveTag(index: number) {
  store.updateTags(removeAt(content.value.tags, index))
  scheduleContentSync()
}

// 复制文案
async function copyCopywriting() {
  if (await copyToClipboard(content.value.copywriting)) {
    copiedCopywriting.value = true
    setCopyTimeout(() => copiedCopywriting.value = false, 2000)
  }
}

// 复制所有标签
async function copyTags() {
  const text = content.value.tags.map(t => `#${t}`).join(' ')
  if (await copyToClipboard(text)) {
    copiedTags.value = true
    setCopyTimeout(() => copiedTags.value = false, 2000)
  }
}

// 复制单个标签
async function copyTag(tag: string, index: number) {
  if (await copyToClipboard(`#${tag}`)) {
    copiedTagIndex.value = index
    setCopyTimeout(() => copiedTagIndex.value = null, 2000)
  }
}
</script>

<style scoped>
.content-display {
  margin-top: var(--space-6);
}

.generate-section {
  text-align: center;
  padding: var(--space-7) var(--space-5);
  background: var(--bg-card);
  border-radius: var(--radius-xl);
  border: 2px dashed var(--gray-4);
}

.generate-btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 16px 32px;
  font-size: 16px;
}

.generate-btn svg {
  width: 20px;
  height: 20px;
}

.loading-section {
  text-align: center;
  padding: 60px 20px;
  background: var(--bg-card);
  border-radius: var(--radius-xl);
}

.loading-spinner {
  width: 48px;
  height: 48px;
  border: 3px solid var(--border-color);
  border-top-color: var(--primary);
  border-radius: var(--radius-full);
  animation: spin 1s linear infinite;
  margin: 0 auto 16px;
}

.loading-section p {
  color: var(--text-sub);
  font-size: 16px;
}

.error-section {
  text-align: center;
  padding: 40px 20px;
  background: var(--color-danger-soft);
  border-radius: var(--radius-xl);
  border: 1px solid rgba(222, 59, 59, 0.25);
}

.error-icon {
  width: 48px;
  height: 48px;
  background: var(--color-danger);
  color: white;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 24px;
  font-weight: bold;
  margin: 0 auto 16px;
}

.error-message {
  color: var(--color-danger);
  margin-bottom: 20px;
  white-space: pre-line;
}

.result-section {
  display: flex;
  flex-direction: column;
  gap: var(--space-5);
}

.content-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: var(--space-6);
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-xs);
}

.card-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: var(--space-4);
  padding-bottom: var(--space-3);
  border-bottom: 1px solid var(--border-color);
}

.card-header h3 {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  font-size: 16px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0;
}

.card-header h3 svg {
  width: 20px;
  height: 20px;
  color: var(--primary);
}

.copy-btn {
  display: flex;
  align-items: center;
  gap: 4px;
  padding: 6px 12px;
  font-size: var(--font-size-caption);
  color: var(--text-sub);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.copy-btn:hover {
  background: var(--bg-card);
  color: var(--text-main);
  border-color: var(--border-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-xs);
}

.copy-btn:active {
  transform: translateY(0);
  box-shadow: none;
}

.copy-btn.copied {
  background: var(--color-success-soft);
  color: var(--color-success);
  border-color: var(--color-success);
}

.copy-btn svg {
  width: 14px;
  height: 14px;
}

.header-actions {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

/* 「保存」主按钮：沿用 copy-btn 尺寸，品牌色填充 */
.copy-btn.primary {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.copy-btn.primary:hover {
  background: var(--primary-hover);
  color: white;
  border-color: var(--primary-hover);
}

/* 标题列表 */
.titles-list {
  display: flex;
  flex-direction: column;
  gap: var(--space-3);
}

.title-item {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  background: var(--gray-1);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: background var(--transition-fast), box-shadow var(--transition-fast);
  position: relative;
}

.title-item:hover {
  background: var(--gray-2);
  box-shadow: var(--shadow-xs);
}

.title-badge {
  flex-shrink: 0;
  padding: 4px 8px;
  font-size: 12px;
  font-weight: 500;
  border-radius: var(--radius-xs);
  background: var(--primary);
  color: white;
}

.title-item:not(:first-child) .title-badge {
  background: var(--gray-6);
}

.title-text {
  flex: 1;
  font-size: var(--font-size-body);
  color: var(--text-main);
  line-height: 1.5;
}

.copy-hint {
  font-size: 12px;
  color: var(--text-sub);
  opacity: 0;
  transition: opacity var(--transition-fast);
}

.title-item:hover .copy-hint {
  opacity: 1;
}

.copy-hint.show {
  opacity: 1;
  color: var(--color-success);
}

/* 标题行的编辑/删除小按钮 */
.item-icon-btn {
  flex-shrink: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  width: 26px;
  height: 26px;
  border: none;
  background: none;
  border-radius: var(--radius-sm);
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast);
}

.item-icon-btn:hover {
  background: var(--gray-3);
  color: var(--text-main);
}

.item-icon-btn.danger:hover {
  background: var(--color-danger-soft);
  color: var(--color-danger);
}

.item-icon-btn svg {
  width: 14px;
  height: 14px;
}

/* 标题 inline 编辑输入框 */
.title-edit-input {
  flex: 1;
  min-width: 0;
  padding: 6px 10px;
  font-size: var(--font-size-body);
  font-family: inherit;
  color: var(--text-main);
  line-height: 1.5;
  background: var(--bg-card);
  border: 1px solid var(--primary);
  border-radius: var(--radius-sm);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.title-edit-input:focus {
  outline: none;
}

/* 文案内容 */
.copywriting-content {
  font-size: var(--font-size-body);
  line-height: 1.8;
  color: var(--text-main);
}

.copywriting-content p {
  margin: 0 0 12px;
}

.copywriting-content p:last-child {
  margin-bottom: 0;
}

/* 文案编辑态 */
.copywriting-textarea {
  width: 100%;
  min-height: 200px;
  padding: var(--space-3);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  background: var(--gray-1);
  font-size: var(--font-size-body);
  line-height: 1.8;
  color: var(--text-main);
  font-family: inherit;
  resize: vertical;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.copywriting-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: 0 0 0 3px var(--primary-fade);
}

.copywriting-edit-actions {
  display: flex;
  justify-content: flex-end;
  gap: var(--space-2);
  margin-top: var(--space-3);
}

/* 标签列表 */
.tags-list {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
}

.tag-item {
  padding: 8px 16px;
  font-size: 14px;
  color: var(--primary);
  background: var(--primary-light);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast), transform var(--transition-fast);
}

.tag-item:hover {
  background: var(--primary);
  color: white;
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.tag-item:active {
  transform: translateY(0);
  box-shadow: none;
}

.tag-item.copied {
  background: var(--color-success);
  color: white;
}

/* tag chip 内的删除按钮：继承 chip 当前文字色，hover 反色时同步变化 */
.tag-item {
  display: inline-flex;
  align-items: center;
  gap: 6px;
}

.tag-remove {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  width: 16px;
  height: 16px;
  padding: 0;
  border: none;
  background: none;
  border-radius: var(--radius-full);
  color: inherit;
  opacity: 0.65;
  cursor: pointer;
  transition: opacity var(--transition-fast);
}

.tag-remove:hover {
  opacity: 1;
}

.tag-remove svg {
  width: 10px;
  height: 10px;
}

/* 新增标签输入框：与 chip 同高、圆角一致 */
.tag-input {
  padding: 8px 16px;
  font-size: 14px;
  font-family: inherit;
  color: var(--text-main);
  background: var(--gray-1);
  border: 1px dashed var(--border-hover);
  border-radius: var(--radius-full);
  min-width: 0;
  width: 170px;
  max-width: 100%;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.tag-input::placeholder {
  color: var(--text-placeholder);
}

.tag-input:focus {
  outline: none;
  border-color: var(--primary);
  border-style: solid;
  background: var(--bg-card);
}

/* 移动端：编辑控件不溢出 */
@media (max-width: 640px) {
  .title-item {
    flex-wrap: wrap;
  }

  .title-edit-input {
    flex-basis: 100%;
  }

  .tag-input {
    width: 100%;
  }
}

/* 重新生成 */
.regenerate-section {
  text-align: center;
  padding-top: 8px;
}

.regenerate-section .btn {
  display: inline-flex;
  align-items: center;
  gap: 8px;
}

.regenerate-section .btn svg {
  width: 16px;
  height: 16px;
}

/* 动画 */
@keyframes spin {
  to { transform: rotate(360deg); }
}

.spinner {
  display: inline-block;
  width: 16px;
  height: 16px;
  border: 2px solid rgba(255,255,255,0.3);
  border-top-color: white;
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}
</style>
