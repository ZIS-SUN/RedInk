<template>
  <div class="container" style="max-width: 1200px;">

    <!-- Header Area -->
    <div class="page-header">
      <div>
        <h1 class="page-title">风格模板</h1>
        <p class="page-desc">挑选一种视觉风格，一键应用到你的图文创作</p>
      </div>
      <div class="header-actions">
        <button class="import-btn" @click="openImportDialog">导入分享码</button>
        <button class="create-btn" @click="openCreateForm">+ 新建风格</button>
      </div>
    </div>

    <!-- 当前已应用风格 -->
    <div v-if="activeStyle" class="active-style-bar">
      <div class="active-style-swatches">
        <span
          v-for="color in activeStyle.colors"
          :key="color"
          class="swatch"
          :style="{ background: color }"
        ></span>
      </div>
      <div class="active-style-info">
        <span class="active-style-label">当前风格</span>
        <span class="active-style-name">{{ activeStyle.name }}</span>
      </div>
      <div class="active-style-actions">
        <button class="mini-btn" @click="copyPrompt(activeStyle.stylePrompt, 'active')">
          {{ copiedKey === 'active' ? '已复制' : '复制提示词' }}
        </button>
        <button class="mini-btn mini-btn-danger" @click="clearStyle">取消应用</button>
      </div>
    </div>
    <div v-else class="active-style-bar active-style-empty">
      尚未应用任何风格，点击下方模板卡片的「应用此风格」即可生效
    </div>

    <!-- 分类筛选 -->
    <div class="filter-bar" role="group" aria-label="按分类筛选风格模板">
      <button
        type="button"
        class="filter-chip"
        :class="{ active: currentCategory === 'all' }"
        :aria-pressed="currentCategory === 'all'"
        @click="currentCategory = 'all'"
      >
        全部
      </button>
      <button
        v-for="cat in styleCategories"
        :key="cat"
        type="button"
        class="filter-chip"
        :class="{ active: currentCategory === cat }"
        :aria-pressed="currentCategory === cat"
        @click="currentCategory = cat"
      >
        {{ cat }}
      </button>
    </div>

    <!-- 模板网格 -->
    <div class="style-grid">
      <div
        v-for="tpl in filteredTemplates"
        :key="tpl.id"
        class="style-card"
        :class="{ applied: isActive(tpl.id) }"
        @click="previewTemplate = tpl"
      >
        <div class="style-cover" :style="{ background: tpl.coverGradient }">
          <span v-if="isActive(tpl.id)" class="applied-badge">使用中</span>
          <span v-if="tpl.custom" class="custom-badge">自定义</span>
          <span class="category-badge">{{ tpl.category }}</span>
        </div>
        <div class="style-body">
          <div class="style-name">{{ tpl.name }}</div>
          <div class="style-desc">{{ tpl.description }}</div>
          <div class="style-colors">
            <span
              v-for="color in tpl.colors"
              :key="color"
              class="swatch"
              :style="{ background: color }"
              :title="color"
            ></span>
          </div>
          <div class="style-actions">
            <button
              class="card-btn card-btn-primary"
              @click.stop="handleApply(tpl)"
            >
              {{ isActive(tpl.id) ? '已应用' : '应用此风格' }}
            </button>
            <button class="card-btn" @click.stop="copyPrompt(tpl.stylePrompt, tpl.id)">
              {{ copiedKey === tpl.id ? '已复制' : '复制提示词' }}
            </button>
          </div>
          <div v-if="tpl.custom" class="style-actions custom-actions">
            <button class="card-btn" @click.stop="openEditForm(tpl)">编辑</button>
            <button class="card-btn" @click.stop="shareStyle(tpl)">分享</button>
            <button class="card-btn card-btn-danger" @click.stop="deleteTarget = tpl">删除</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 预览弹窗 -->
    <div v-if="previewTemplate" class="preview-mask" @click.self="previewTemplate = null">
      <div class="preview-modal" role="dialog" aria-modal="true">
        <button class="preview-close" aria-label="关闭预览" @click="previewTemplate = null">×</button>
        <div class="preview-cover" :style="{ background: previewTemplate.coverGradient }">
          <span class="preview-title">{{ previewTemplate.name }}</span>
        </div>
        <div class="preview-content">
          <div class="preview-section">
            <div class="preview-label">风格描述</div>
            <p class="preview-text">{{ previewTemplate.description }}</p>
          </div>
          <div class="preview-section">
            <div class="preview-label">推荐配色</div>
            <div class="preview-color-list">
              <div v-for="color in previewTemplate.colors" :key="color" class="preview-color-item">
                <span class="swatch swatch-lg" :style="{ background: color }"></span>
                <span class="color-hex">{{ color }}</span>
              </div>
            </div>
          </div>
          <div class="preview-section">
            <div class="preview-label">适用场景</div>
            <div class="scene-tags">
              <span v-for="scene in previewTemplate.scenes" :key="scene" class="scene-tag">{{ scene }}</span>
            </div>
          </div>
          <div class="preview-section">
            <div class="preview-label">风格提示词</div>
            <p class="preview-prompt">{{ previewTemplate.stylePrompt }}</p>
          </div>
          <div class="preview-actions">
            <button class="card-btn card-btn-primary" @click="handleApply(previewTemplate)">
              {{ isActive(previewTemplate.id) ? '已应用' : '应用此风格' }}
            </button>
            <button class="card-btn" @click="copyPrompt(previewTemplate.stylePrompt, 'preview')">
              {{ copiedKey === 'preview' ? '已复制' : '复制风格提示词' }}
            </button>
          </div>
        </div>
      </div>
    </div>

    <!-- 新建 / 编辑自定义风格弹窗 -->
    <div v-if="formVisible" class="preview-mask" @click.self="closeForm">
      <div class="preview-modal form-modal" role="dialog" aria-modal="true">
        <button class="preview-close" aria-label="关闭表单" @click="closeForm">×</button>
        <div class="form-content">
          <h2 class="form-title">{{ editingId ? '编辑自定义风格' : '新建自定义风格' }}</h2>

          <div class="form-field">
            <label class="form-label" for="style-name">名称 <span class="required-mark">*</span></label>
            <input
              id="style-name"
              v-model="form.name"
              class="form-input"
              type="text"
              maxlength="20"
              placeholder="给你的风格起个名字，如「奶油胶感」"
            />
            <p v-if="formErrors.name" class="form-error">{{ formErrors.name }}</p>
          </div>

          <div class="form-field">
            <label class="form-label" for="style-category">分类</label>
            <select id="style-category" v-model="form.category" class="form-input">
              <option v-for="cat in styleCategories" :key="cat" :value="cat">{{ cat }}</option>
            </select>
          </div>

          <div class="form-field">
            <label class="form-label" for="style-desc">风格描述</label>
            <textarea
              id="style-desc"
              v-model="form.description"
              class="form-input form-textarea"
              rows="2"
              maxlength="100"
              placeholder="一两句话描述这个风格的视觉特点"
            ></textarea>
          </div>

          <div class="form-field">
            <label class="form-label">配色（4 色）</label>
            <div class="color-inputs">
              <div v-for="(_, index) in form.colors" :key="index" class="color-input-item">
                <input
                  v-model="form.colors[index]"
                  type="color"
                  class="color-picker"
                  :aria-label="`配色 ${index + 1}`"
                />
                <span class="color-hex">{{ form.colors[index].toUpperCase() }}</span>
              </div>
            </div>
          </div>

          <div class="form-field">
            <label class="form-label" for="style-scenes">适用场景（用逗号分隔）</label>
            <input
              id="style-scenes"
              v-model="form.scenesText"
              class="form-input"
              type="text"
              placeholder="如：好物种草, 旅行游记, 美食探店"
            />
          </div>

          <div class="form-field">
            <label class="form-label" for="style-prompt">风格提示词 <span class="required-mark">*</span></label>
            <textarea
              id="style-prompt"
              v-model="form.stylePrompt"
              class="form-input form-textarea"
              rows="4"
              placeholder="描述画面风格的提示词，将直接用于图片生成"
            ></textarea>
            <p v-if="formErrors.stylePrompt" class="form-error">{{ formErrors.stylePrompt }}</p>
          </div>

          <div class="preview-actions">
            <button class="card-btn card-btn-primary" :disabled="!canSubmitForm" @click="submitForm">
              {{ editingId ? '保存修改' : '创建风格' }}
            </button>
            <button class="card-btn" @click="closeForm">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 删除确认弹窗 -->
    <div v-if="deleteTarget" class="preview-mask" @click.self="deleteTarget = null">
      <div class="preview-modal confirm-modal" role="alertdialog" aria-modal="true">
        <div class="form-content">
          <h2 class="form-title">删除自定义风格</h2>
          <p class="confirm-text">
            确定要删除「{{ deleteTarget.name }}」吗？删除后不可恢复。
          </p>
          <div class="preview-actions">
            <button class="card-btn card-btn-danger-solid" @click="confirmDelete">确认删除</button>
            <button class="card-btn" @click="deleteTarget = null">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 分享码手动复制弹窗（剪贴板不可用时的降级方案） -->
    <div v-if="shareFallback" class="preview-mask" @click.self="shareFallback = null">
      <div class="preview-modal confirm-modal" role="dialog" aria-modal="true">
        <button class="preview-close" aria-label="关闭分享码弹窗" @click="shareFallback = null">×</button>
        <div class="form-content">
          <h2 class="form-title">分享「{{ shareFallback.name }}」</h2>
          <p class="confirm-text">自动复制失败，请手动全选下方分享码并复制发给好友：</p>
          <textarea
            ref="shareCodeTextarea"
            class="form-input form-textarea share-code-box"
            rows="5"
            readonly
            :value="shareFallback.code"
            aria-label="风格分享码"
            @focus="selectShareCode"
          ></textarea>
          <div class="preview-actions">
            <button class="card-btn" @click="shareFallback = null">关闭</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 导入分享码弹窗 -->
    <div v-if="importVisible" class="preview-mask" @click.self="closeImportDialog">
      <div class="preview-modal form-modal" role="dialog" aria-modal="true">
        <button class="preview-close" aria-label="关闭导入弹窗" @click="closeImportDialog">×</button>
        <div class="form-content">
          <h2 class="form-title">导入风格分享码</h2>

          <div class="form-field">
            <label class="form-label" for="import-code">分享码</label>
            <textarea
              id="import-code"
              v-model="importText"
              class="form-input form-textarea share-code-box"
              rows="4"
              placeholder="粘贴好友发来的分享码（以 RINK 开头）"
            ></textarea>
            <p v-if="importError" class="form-error">{{ importError }}</p>
          </div>

          <!-- 校验通过后的预览 -->
          <div v-if="importPreview" class="import-preview">
            <div class="preview-label">导入预览</div>
            <div class="import-preview-head">
              <div class="active-style-swatches">
                <span
                  v-for="color in importPreview.style.colors"
                  :key="color"
                  class="swatch"
                  :style="{ background: color }"
                ></span>
              </div>
              <span class="import-preview-name">{{ importPreview.finalName }}</span>
              <span class="category-chip">{{ importPreview.style.category }}</span>
            </div>
            <p v-if="importPreview.renamed" class="import-rename-hint">
              已存在同名风格，导入后将命名为「{{ importPreview.finalName }}」
            </p>
            <p class="import-preview-prompt">{{ importPreview.promptExcerpt }}</p>
          </div>

          <div class="preview-actions">
            <button class="card-btn card-btn-primary" :disabled="!importPreview" @click="confirmImport">
              确认导入
            </button>
            <button class="card-btn" @click="closeImportDialog">取消</button>
          </div>
        </div>
      </div>
    </div>

    <!-- 从大纲页跳来时：应用风格后的「返回继续创作」悬浮条 -->
    <transition name="toast-fade">
      <div v-if="appliedFromOutline" class="back-to-outline-bar" role="status">
        <span class="back-bar-text">已应用「{{ appliedFromOutline }}」</span>
        <button type="button" class="back-bar-btn" @click="backToOutline">
          返回继续创作 →
        </button>
        <button type="button" class="back-bar-close" aria-label="关闭提示" @click="appliedFromOutline = ''">×</button>
      </div>
    </transition>

    <!-- 轻提示 -->
    <transition name="toast-fade">
      <div v-if="toast" class="toast" role="status" aria-live="polite">{{ toast }}</div>
    </transition>

  </div>
</template>

<script setup lang="ts">
import { ref, reactive, computed, onUnmounted, nextTick } from 'vue'
import { useRoute, useRouter } from 'vue-router'
import { styleCategories, type StyleCategory, type StyleTemplate } from '../data/styleTemplates'
import { useStyleLibrary } from '../composables/useStyleLibrary'
import {
  encodeStyleShareCode,
  decodeStyleShareCode,
  resolveDuplicateName
} from '../utils/styleShareCode'

const {
  activeStyle,
  applyStyle,
  clearStyle,
  isActive,
  allTemplates,
  addCustomStyle,
  updateCustomStyle,
  removeCustomStyle
} = useStyleLibrary()

// 分类筛选
const currentCategory = ref<string>('all')

const filteredTemplates = computed(() => {
  if (currentCategory.value === 'all') return allTemplates.value
  return allTemplates.value.filter(tpl => tpl.category === currentCategory.value)
})

// 预览
const previewTemplate = ref<StyleTemplate | null>(null)

// ===== 自定义风格：新建 / 编辑表单 =====
const DEFAULT_COLORS = ['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238']

const formVisible = ref(false)
/** 正在编辑的自定义模板 id（null 表示新建） */
const editingId = ref<string | null>(null)

const form = reactive({
  name: '',
  category: styleCategories[0] as StyleCategory,
  description: '',
  colors: [...DEFAULT_COLORS],
  scenesText: '',
  stylePrompt: ''
})

const formErrors = reactive({ name: '', stylePrompt: '' })

/** 必填项为空时禁用提交 */
const canSubmitForm = computed(() => !!form.name.trim() && !!form.stylePrompt.trim())

function resetForm() {
  form.name = ''
  form.category = styleCategories[0]
  form.description = ''
  form.colors = [...DEFAULT_COLORS]
  form.scenesText = ''
  form.stylePrompt = ''
  formErrors.name = ''
  formErrors.stylePrompt = ''
}

function openCreateForm() {
  resetForm()
  editingId.value = null
  formVisible.value = true
}

function openEditForm(template: StyleTemplate) {
  resetForm()
  editingId.value = template.id
  form.name = template.name
  form.category = template.category
  form.description = template.description
  form.colors = template.colors.length === 4 ? [...template.colors] : [...DEFAULT_COLORS]
  form.scenesText = template.scenes.join(', ')
  form.stylePrompt = template.stylePrompt
  formVisible.value = true
  previewTemplate.value = null
}

function closeForm() {
  formVisible.value = false
  editingId.value = null
}

function validateForm(): boolean {
  formErrors.name = form.name.trim() ? '' : '请填写风格名称'
  formErrors.stylePrompt = form.stylePrompt.trim() ? '' : '请填写风格提示词'
  return !formErrors.name && !formErrors.stylePrompt
}

function submitForm() {
  if (!validateForm()) return
  const colors = form.colors.map(c => c.toUpperCase())
  const payload = {
    name: form.name.trim(),
    category: form.category,
    description: form.description.trim() || '我的自定义风格',
    coverGradient: `linear-gradient(135deg, ${colors[0]} 0%, ${colors[1]} 40%, ${colors[2]} 100%)`,
    colors,
    scenes: form.scenesText
      .split(/[,，、]/)
      .map(s => s.trim())
      .filter(Boolean),
    stylePrompt: form.stylePrompt.trim()
  }
  if (editingId.value) {
    updateCustomStyle(editingId.value, payload)
    showToast(`已更新「${payload.name}」`)
  } else {
    addCustomStyle(payload)
    showToast(`已创建「${payload.name}」`)
  }
  closeForm()
}

// ===== 自定义风格：删除确认 =====
const deleteTarget = ref<StyleTemplate | null>(null)

function confirmDelete() {
  if (!deleteTarget.value) return
  const name = deleteTarget.value.name
  removeCustomStyle(deleteTarget.value.id)
  deleteTarget.value = null
  if (previewTemplate.value && !allTemplates.value.some(t => t.id === previewTemplate.value?.id)) {
    previewTemplate.value = null
  }
  showToast(`已删除「${name}」`)
}

// ===== 自定义风格：生成分享码 =====
/** 剪贴板不可用时降级展示的分享码（null 表示弹窗关闭） */
const shareFallback = ref<{ name: string; code: string } | null>(null)
const shareCodeTextarea = ref<HTMLTextAreaElement | null>(null)

/** 生成分享码并复制；剪贴板不可用时弹出可手动复制的文本框 */
async function shareStyle(template: StyleTemplate) {
  const code = encodeStyleShareCode(template)
  try {
    await navigator.clipboard.writeText(code)
    showToast(`「${template.name}」分享码已复制，发给好友即可导入`)
  } catch {
    // 降级方案：兼容不支持 Clipboard API（如非 https）的环境
    shareFallback.value = { name: template.name, code }
    nextTick(() => shareCodeTextarea.value?.select())
  }
}

function selectShareCode(event: FocusEvent) {
  ;(event.target as HTMLTextAreaElement).select()
}

// ===== 导入分享码 =====
const importVisible = ref(false)
const importText = ref('')

/** 实时解析粘贴的分享码：成功给出预览，失败给出具体原因 */
const importParsed = computed(() => {
  const text = importText.value.trim()
  if (!text) return null
  return decodeStyleShareCode(text)
})

const importError = computed(() => {
  const parsed = importParsed.value
  return parsed && !parsed.ok ? parsed.message : ''
})

const importPreview = computed(() => {
  const parsed = importParsed.value
  if (!parsed?.ok) return null
  const style = parsed.style
  const finalName = resolveDuplicateName(
    style.name,
    allTemplates.value.map(t => t.name)
  )
  return {
    style,
    finalName,
    renamed: finalName !== style.name,
    promptExcerpt:
      style.stylePrompt.length > 120 ? `${style.stylePrompt.slice(0, 120)}…` : style.stylePrompt
  }
})

function openImportDialog() {
  importText.value = ''
  importVisible.value = true
}

function closeImportDialog() {
  importVisible.value = false
  importText.value = ''
}

function confirmImport() {
  const preview = importPreview.value
  if (!preview) return
  addCustomStyle({ ...preview.style, name: preview.finalName })
  closeImportDialog()
  showToast(`已导入「${preview.finalName}」，可在自定义风格中查看`)
}

// 轻提示
const toast = ref('')
let toastTimer: ReturnType<typeof setTimeout> | null = null

function showToast(message: string) {
  toast.value = message
  if (toastTimer) clearTimeout(toastTimer)
  toastTimer = setTimeout(() => {
    toast.value = ''
  }, 2000)
}

// ==================== 从大纲页跳来的返回动线 ====================

const route = useRoute()
const router = useRouter()

/** 是否从大纲页跳来（大纲页跳风格库的链接带 ?from=outline） */
const fromOutline = computed(() => route.query.from === 'outline')

/** 应用成功后展示「返回继续创作」悬浮条（记录已应用的风格名，空串表示隐藏） */
const appliedFromOutline = ref('')

function backToOutline() {
  router.push('/outline')
}

/**
 * 应用风格模板；从大纲页跳来时改为展示「返回继续创作」悬浮条
 * （替代普通 toast，引导用户带着新风格回到创作流程）
 */
function handleApply(template: StyleTemplate) {
  applyStyle(template)
  if (fromOutline.value) {
    appliedFromOutline.value = template.name
  } else {
    showToast(`已应用「${template.name}」风格`)
  }
}

// 复制反馈：记录最近一次复制成功的按钮，短暂显示「已复制」后复原
const copiedKey = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | null = null

onUnmounted(() => {
  if (toastTimer) clearTimeout(toastTimer)
  if (copiedTimer) clearTimeout(copiedTimer)
})

function markCopied(key: string) {
  copiedKey.value = key
  showToast('风格提示词已复制')
  if (copiedTimer) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedKey.value = ''
  }, 2000)
}

/**
 * 复制风格提示词（非 https 环境降级到 execCommand）
 */
async function copyPrompt(prompt: string, key: string) {
  try {
    await navigator.clipboard.writeText(prompt)
    markCopied(key)
  } catch {
    // 降级方案：兼容不支持 Clipboard API（如非 https）的环境
    const textarea = document.createElement('textarea')
    textarea.value = prompt
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    try {
      document.execCommand('copy')
      markCopied(key)
    } catch {
      showToast('复制失败，请手动复制')
    } finally {
      document.body.removeChild(textarea)
    }
  }
}
</script>

<style scoped>
.page-desc {
  margin-top: var(--space-1);
  font-size: 14px;
  color: var(--text-sub);
}

/* ===== 新建风格入口 ===== */
.create-btn {
  padding: 9px 20px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: white;
  background: var(--primary);
  border: 1px solid var(--primary);
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
  box-shadow: var(--shadow-xs);
  transition: background var(--transition-fast), border-color var(--transition-fast),
    transform var(--transition-fast), box-shadow var(--transition-fast);
}

.create-btn:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

.header-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.import-btn {
  padding: 9px 20px;
  font-size: 14px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  white-space: nowrap;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), color var(--transition-fast),
    transform var(--transition-fast), box-shadow var(--transition-fast);
}

.import-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
  transform: translateY(-1px);
  box-shadow: var(--shadow-sm);
}

/* ===== 当前已应用风格 ===== */
.active-style-bar {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-5);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-xs);
}

.active-style-empty {
  color: var(--text-secondary);
  font-size: 14px;
  border-style: dashed;
  border-color: var(--border-hover);
  background: var(--gray-0);
  box-shadow: none;
  justify-content: center;
}

.active-style-swatches {
  display: flex;
  gap: var(--space-1);
  flex-shrink: 0;
}

.active-style-info {
  display: flex;
  align-items: baseline;
  gap: var(--space-2);
  flex: 1;
  min-width: 0;
}

.active-style-label {
  font-size: 12px;
  color: var(--text-secondary);
  flex-shrink: 0;
}

.active-style-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.active-style-actions {
  display: flex;
  gap: var(--space-2);
  flex-shrink: 0;
}

.mini-btn {
  padding: 6px 12px;
  font-size: 13px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast);
}

.mini-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.mini-btn-danger:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

/* ===== 分类筛选 ===== */
.filter-bar {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
  margin-bottom: var(--space-5);
}

.filter-chip {
  padding: 7px 18px;
  font-size: 14px;
  font-family: inherit;
  color: var(--text-sub);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-full);
  cursor: pointer;
  user-select: none;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.filter-chip:hover {
  border-color: var(--border-hover);
  color: var(--text-main);
}

.filter-chip.active {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  font-weight: 600;
}

/* ===== 模板网格 ===== */
.style-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(260px, 1fr));
  gap: var(--space-5);
  margin-bottom: 40px;
}

.style-card {
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-lg);
  overflow: hidden;
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: transform var(--transition-base), box-shadow var(--transition-base),
    border-color var(--transition-base);
}

.style-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
  border-color: var(--border-hover);
}

.style-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm);
}

.style-card.applied {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.style-card.applied:hover {
  border-color: var(--primary);
}

.style-cover {
  position: relative;
  height: 140px;
  overflow: hidden;
}

.style-cover::after {
  content: '';
  position: absolute;
  inset: 0;
  box-shadow: inset 0 -1px 0 rgba(33, 30, 27, 0.06);
  pointer-events: none;
}

.applied-badge {
  position: absolute;
  top: var(--space-3);
  left: var(--space-3);
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-sm);
  z-index: 1;
}

.category-badge {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  padding: 3px 10px;
  font-size: 12px;
  color: var(--text-main);
  background: rgba(255, 255, 255, 0.85);
  border-radius: var(--radius-full);
  backdrop-filter: blur(4px);
}

.custom-badge {
  position: absolute;
  bottom: var(--space-3);
  left: var(--space-3);
  padding: 3px 10px;
  font-size: 12px;
  font-weight: 600;
  color: white;
  background: rgba(33, 30, 27, 0.55);
  border-radius: var(--radius-full);
  backdrop-filter: blur(4px);
}

.style-body {
  padding: var(--space-4);
}

.style-name {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-2);
}

.style-desc {
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.6;
  margin-bottom: var(--space-3);
  display: -webkit-box;
  -webkit-line-clamp: 2;
  -webkit-box-orient: vertical;
  overflow: hidden;
}

.style-colors {
  display: flex;
  gap: var(--space-2);
  margin-bottom: var(--space-4);
}

.swatch {
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  flex-shrink: 0;
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.4);
}

.swatch-lg {
  width: 28px;
  height: 28px;
  border-radius: var(--radius-sm);
}

.style-actions {
  display: flex;
  gap: var(--space-2);
}

.card-btn {
  flex: 1;
  padding: 8px 0;
  font-size: 13px;
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-main);
  border-radius: var(--radius-sm);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), transform var(--transition-fast);
  white-space: nowrap;
}

.card-btn:active:not(:disabled) {
  transform: translateY(1px);
}

.card-btn:hover {
  border-color: var(--primary);
  color: var(--primary);
}

.card-btn-primary {
  background: var(--primary);
  border-color: var(--primary);
  color: white;
  font-weight: 600;
}

.card-btn-primary:hover {
  background: var(--primary-hover);
  border-color: var(--primary-hover);
  color: white;
}

.card-btn:disabled {
  opacity: 0.5;
  cursor: not-allowed;
}

.card-btn-primary:disabled:hover {
  background: var(--primary);
  border-color: var(--primary);
}

.custom-actions {
  margin-top: var(--space-2);
}

.card-btn-danger:hover {
  border-color: var(--color-danger);
  color: var(--color-danger);
}

.card-btn-danger-solid {
  background: var(--color-danger);
  border-color: var(--color-danger);
  color: white;
  font-weight: 600;
}

.card-btn-danger-solid:hover {
  opacity: 0.88;
  border-color: var(--color-danger);
  color: white;
}

/* ===== 预览弹窗 ===== */
.preview-mask {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  display: flex;
  align-items: center;
  justify-content: center;
  z-index: 1000;
  padding: var(--space-4);
  animation: maskIn 150ms var(--ease-out);
}

.preview-modal {
  position: relative;
  width: min(560px, 100%);
  max-height: calc(100vh - 48px);
  overflow-y: auto;
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  box-shadow: var(--shadow-lg);
  animation: modalIn 200ms var(--ease-out);
}

@keyframes maskIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes modalIn {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .preview-mask,
  .preview-modal {
    animation: none;
  }
}

.preview-close {
  position: absolute;
  top: var(--space-3);
  right: var(--space-3);
  width: 32px;
  height: 32px;
  border: none;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.85);
  color: var(--text-main);
  font-size: 20px;
  line-height: 1;
  cursor: pointer;
  z-index: 1;
  transition: background var(--transition-fast);
}

.preview-close:hover {
  background: white;
}

.preview-cover {
  height: 160px;
  display: flex;
  align-items: flex-end;
  padding: var(--space-4);
}

.preview-title {
  font-size: 22px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: white;
  text-shadow: 0 2px 8px rgba(0, 0, 0, 0.35);
}

.preview-content {
  padding: var(--space-5);
}

.preview-section {
  margin-bottom: var(--space-4);
}

.preview-label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.preview-text {
  font-size: 14px;
  color: var(--text-main);
  line-height: 1.7;
}

.preview-color-list {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.preview-color-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.color-hex {
  font-size: 12px;
  color: var(--text-sub);
  font-family: var(--font-mono);
}

.scene-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.scene-tag {
  padding: 4px 12px;
  font-size: 13px;
  color: var(--text-sub);
  background: var(--gray-2);
  border-radius: var(--radius-full);
}

.preview-prompt {
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.7;
  padding: var(--space-3);
  background: var(--gray-1);
  border-radius: var(--radius-sm);
  word-break: break-all;
}

.preview-actions {
  display: flex;
  gap: var(--space-3);
  margin-top: var(--space-5);
}

.preview-actions .card-btn {
  padding: 10px 0;
  font-size: 14px;
}

/* ===== 新建/编辑表单弹窗 ===== */
.form-modal {
  width: min(520px, 100%);
}

.confirm-modal {
  width: min(400px, 100%);
}

.form-content {
  padding: var(--space-5);
}

.form-title {
  font-size: 18px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0 0 var(--space-4);
}

.form-field {
  margin-bottom: var(--space-4);
}

.form-label {
  display: block;
  font-size: 13px;
  font-weight: 600;
  color: var(--text-secondary);
  margin-bottom: var(--space-2);
}

.required-mark {
  color: var(--color-danger);
}

.form-input {
  width: 100%;
  padding: 9px 12px;
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  outline: none;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  font-family: inherit;
  box-sizing: border-box;
}

.form-input::placeholder {
  color: var(--text-placeholder);
}

.form-input:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.form-textarea {
  resize: vertical;
  line-height: 1.6;
}

.form-error {
  margin-top: var(--space-1);
  font-size: 12px;
  color: var(--color-danger);
}

.color-inputs {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-3);
}

.color-input-item {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.color-picker {
  width: 40px;
  height: 32px;
  padding: 2px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.color-picker:hover {
  border-color: var(--border-hover);
}

.confirm-text {
  font-size: 14px;
  color: var(--text-main);
  line-height: 1.7;
  margin: 0 0 var(--space-4);
}

/* ===== 分享码 / 导入分享码 ===== */
.share-code-box {
  font-family: var(--font-mono);
  font-size: 12px;
  line-height: 1.6;
  word-break: break-all;
  resize: vertical;
}

.import-preview {
  padding: var(--space-3);
  margin-bottom: var(--space-4);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
}

.import-preview-head {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  margin-bottom: var(--space-2);
}

.import-preview-name {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  overflow: hidden;
  white-space: nowrap;
  text-overflow: ellipsis;
}

.category-chip {
  flex-shrink: 0;
  padding: 2px 10px;
  font-size: 12px;
  color: var(--text-sub);
  background: var(--gray-2);
  border-radius: var(--radius-full);
}

.import-rename-hint {
  margin: 0 0 var(--space-2);
  font-size: 12px;
  color: var(--text-secondary);
}

.import-preview-prompt {
  margin: 0;
  font-size: 13px;
  color: var(--text-sub);
  line-height: 1.7;
  word-break: break-all;
}

/* ===== 从大纲页跳来的「返回继续创作」悬浮条 ===== */
.back-to-outline-bar {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: 10px 14px 10px 20px;
  background: var(--bg-card);
  border: 1px solid var(--primary);
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-lg);
  z-index: 1500;
  white-space: nowrap;
}

.back-bar-text {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.back-bar-btn {
  padding: 7px 16px;
  font-size: 14px;
  font-weight: 600;
  color: white;
  background: var(--primary);
  border: none;
  border-radius: var(--radius-full);
  cursor: pointer;
  transition: background var(--transition-fast);
}

.back-bar-btn:hover {
  background: var(--primary-hover);
}

.back-bar-close {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  border-radius: var(--radius-full);
  transition: color var(--transition-fast);
}

.back-bar-close:hover {
  color: var(--text-main);
}

/* ===== 轻提示 ===== */
.toast {
  position: fixed;
  bottom: 40px;
  left: 50%;
  transform: translateX(-50%);
  padding: 10px 24px;
  background: rgba(33, 30, 27, 0.86);
  color: white;
  font-size: 14px;
  border-radius: var(--radius-full);
  box-shadow: var(--shadow-md);
  z-index: 2000;
  white-space: nowrap;
}

.toast-fade-enter-active,
.toast-fade-leave-active {
  transition: opacity var(--transition-slow), transform var(--transition-slow);
}

.toast-fade-enter-from,
.toast-fade-leave-to {
  opacity: 0;
  transform: translateX(-50%) translateY(10px);
}

/* ===== 移动端适配 ===== */
@media (max-width: 640px) {
  .style-grid {
    grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
    gap: var(--space-4);
  }

  .style-cover {
    height: 100px;
  }

  .style-body {
    padding: var(--space-3);
  }

  .style-desc {
    -webkit-line-clamp: 3;
  }

  .style-actions {
    flex-direction: column;
  }

  .active-style-bar {
    flex-wrap: wrap;
    gap: var(--space-2);
  }

  .active-style-actions {
    width: 100%;
    justify-content: flex-end;
  }

  .toast {
    bottom: calc(var(--mobile-tabbar-height) + 20px);
    max-width: calc(100vw - 32px);
    white-space: normal;
    text-align: center;
  }

  .back-to-outline-bar {
    bottom: calc(var(--mobile-tabbar-height) + 20px);
    max-width: calc(100vw - 24px);
    white-space: normal;
  }

  .create-btn,
  .import-btn {
    padding: 8px 16px;
    font-size: 13px;
  }

  .custom-actions {
    flex-direction: row;
  }

  .form-content {
    padding: var(--space-4);
  }
}
</style>
