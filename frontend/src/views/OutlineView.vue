<template>
  <div class="container" style="max-width: 100%;">
    <StepIndicator :current="2" />

    <div class="page-header" style="max-width: 1200px; margin: 0 auto 30px auto;">
      <div>
        <h1 class="page-title">编辑大纲</h1>
        <p class="page-subtitle">
          调整页面顺序，修改文案，打造完美内容
          <span v-if="isSaving" class="save-indicator saving">保存中...</span>
          <span v-else class="save-indicator saved">已保存</span>
        </p>
      </div>
      <div style="display: flex; gap: 12px;">
        <button class="btn btn-secondary" @click="goBack">
          上一步
        </button>
        <button class="btn btn-primary" @click="startGeneration">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="M20.24 12.24a6 6 0 0 0-8.49-8.49L5 10.5V19h8.5z"></path><line x1="16" y1="8" x2="2" y2="22"></line><line x1="17.5" y1="15" x2="9" y2="15"></line></svg>
          开始生成图片
        </button>
      </div>
    </div>

    <!-- 当前风格提示条：让用户在生成前明确知道会使用什么风格 -->
    <div class="style-hint-wrap">
      <div class="style-hint" :class="{ inactive: !activeStyle }" role="status">
        <template v-if="activeStyle">
          <span class="style-hint-colors" aria-hidden="true">
            <span
              v-for="color in activeStyle.colors.slice(0, 3)"
              :key="color"
              class="style-hint-color"
              :style="{ background: color }"
            />
          </span>
          <span>本次生成将使用风格：<strong>{{ activeStyle.name }}</strong></span>
        </template>
        <template v-else>
          <span>未应用风格，</span>
          <RouterLink to="/tools/style" class="style-hint-link">去风格模板库选择</RouterLink>
        </template>
      </div>
    </div>

    <div class="outline-grid">
      <div 
        v-for="(page, idx) in store.outline.pages" 
        :key="pageKey(page)"
        class="card outline-card"
        :draggable="true"
        @dragstart="onDragStart($event, idx)"
        @dragover.prevent="onDragOver($event, idx)"
        @drop="onDrop($event, idx)"
        :class="{ 'dragging-over': dragOverIndex === idx }"
      >
        <!-- 拖拽手柄 (改为右上角或更加隐蔽) -->
        <div class="card-top-bar">
          <div class="page-info">
             <span class="page-number">第 {{ idx + 1 }} 页</span>
             <span class="page-type" :class="page.type">{{ getPageTypeName(page.type) }}</span>
          </div>
          
          <div class="card-controls">
            <div class="polish-wrap">
              <button
                class="icon-btn polish-btn"
                :class="{ active: openMenuKey === pageKey(page) }"
                :disabled="polishingKey !== null"
                title="AI 润色"
                aria-label="AI 润色"
                aria-haspopup="menu"
                @click.stop="toggleMenu(page)"
              >
                <span v-if="polishingKey === pageKey(page)" class="polish-spinner" aria-hidden="true" />
                <svg v-else width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"></path></svg>
              </button>
              <div
                v-if="openMenuKey === pageKey(page)"
                class="polish-menu"
                role="menu"
                @click.stop
              >
                <button class="polish-menu-item" role="menuitem" @click="runPolish(page, 'polish')">润色</button>
                <button class="polish-menu-item" role="menuitem" @click="runPolish(page, 'shorten')">精简</button>
                <button class="polish-menu-item" role="menuitem" @click="runPolish(page, 'punchier')">更抓眼球</button>
              </div>
            </div>
            <button
              class="icon-btn"
              :disabled="idx === 0"
              @click="movePageBy(idx, -1)"
              title="上移此页"
              aria-label="上移此页"
            >
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="19" x2="12" y2="5"></line><polyline points="5 12 12 5 19 12"></polyline></svg>
            </button>
            <button
              class="icon-btn"
              :disabled="idx === store.outline.pages.length - 1"
              @click="movePageBy(idx, 1)"
              title="下移此页"
              aria-label="下移此页"
            >
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="12" y1="5" x2="12" y2="19"></line><polyline points="19 12 12 19 5 12"></polyline></svg>
            </button>
            <div class="drag-handle" title="拖拽排序">
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="9" cy="12" r="1"></circle><circle cx="9" cy="5" r="1"></circle><circle cx="9" cy="19" r="1"></circle><circle cx="15" cy="12" r="1"></circle><circle cx="15" cy="5" r="1"></circle><circle cx="15" cy="19" r="1"></circle></svg>
            </div>
            <button class="icon-btn danger" @click="requestDeletePage(idx)" title="删除此页" aria-label="删除此页">
               <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
        </div>

        <textarea
          v-model="page.content"
          class="textarea-paper"
          placeholder="在此输入文案..."
          :disabled="polishingKey === pageKey(page)"
          @input="store.updatePage(page.index, page.content)"
        />
        
        <div class="word-count">{{ page.content.length }} 字</div>

        <!-- AI 润色结果对比预览：应用后才写回，放弃则丢弃 -->
        <div v-if="polishPreviews[pageKey(page)] !== undefined" class="polish-preview">
          <div class="polish-preview-label">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 3l1.9 5.8a2 2 0 0 0 1.3 1.3L21 12l-5.8 1.9a2 2 0 0 0-1.3 1.3L12 21l-1.9-5.8a2 2 0 0 0-1.3-1.3L3 12l5.8-1.9a2 2 0 0 0 1.3-1.3L12 3z"></path></svg>
            AI 润色结果
          </div>
          <div class="polish-preview-text">{{ polishPreviews[pageKey(page)] }}</div>
          <div class="polish-preview-actions">
            <button class="polish-mini-btn primary" @click="applyPolish(page)">应用</button>
            <button class="polish-mini-btn" @click="discardPolish(page)">放弃</button>
          </div>
        </div>

        <div v-if="polishErrors[pageKey(page)]" class="polish-error" role="alert">
          {{ polishErrors[pageKey(page)] }}
        </div>
      </div>

      <!-- 添加按钮卡片 -->
      <div class="card add-card-dashed" @click="addPage('content')">
        <div class="add-content">
          <div class="add-icon">+</div>
          <span>添加页面</span>
        </div>
      </div>
    </div>
    
    <div style="height: 100px;"></div>

    <!-- 删除页面确认弹窗 -->
    <ConfirmDialog
      :visible="pendingDeleteIndex !== null"
      title="删除这一页？"
      message="删除后该页文案将无法恢复。"
      confirm-text="删除"
      danger
      @confirm="doDeletePage"
      @cancel="pendingDeleteIndex = null"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, nextTick, watch, onMounted, onUnmounted } from 'vue'
import { useRouter, RouterLink } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { useStyleLibrary } from '../composables/useStyleLibrary'
import {
  updateHistory,
  createHistory,
  polishPage,
  type Page,
  type PolishInstruction
} from '../api'
import { getApiErrorPayload } from '../api/client'
import StepIndicator from './shared/StepIndicator.vue'
import ConfirmDialog from './shared/ConfirmDialog.vue'

const router = useRouter()
const store = useGeneratorStore()
// 当前应用的风格（来自风格模板库），用于生成前的风格提示条
const { activeStyle } = useStyleLibrary()

const dragOverIndex = ref<number | null>(null)
const draggedIndex = ref<number | null>(null)
// 保存状态指示
const isSaving = ref(false)
// 待删除的页面索引（确认弹窗用）
const pendingDeleteIndex = ref<number | null>(null)

// ==================== 稳定 key ====================
// page.index 在拖拽/删除后会被重新编号，直接用作 :key 会导致卡片
// （含 textarea）销毁重建、焦点丢失。这里基于页面对象本身维护稳定 key。
let pageKeySeed = 0
const pageKeyMap = new WeakMap<Page, number>()

function pageKey(page: Page): number {
  let key = pageKeyMap.get(page)
  if (key === undefined) {
    key = ++pageKeySeed
    pageKeyMap.set(page, key)
  }
  return key
}

const getPageTypeName = (type: string) => {
  const names = {
    cover: '封面',
    content: '内容',
    summary: '总结'
  }
  return names[type as keyof typeof names] || '内容'
}

// 拖拽逻辑
const onDragStart = (e: DragEvent, index: number) => {
  draggedIndex.value = index
  if (e.dataTransfer) {
    e.dataTransfer.effectAllowed = 'move'
    e.dataTransfer.dropEffect = 'move'
  }
}

const onDragOver = (_e: DragEvent, index: number) => {
  if (draggedIndex.value === index) return
  dragOverIndex.value = index
}

const onDrop = (_e: DragEvent, index: number) => {
  dragOverIndex.value = null
  if (draggedIndex.value !== null && draggedIndex.value !== index) {
    store.movePage(draggedIndex.value, index)
  }
  draggedIndex.value = null
}

const requestDeletePage = (index: number) => {
  pendingDeleteIndex.value = index
}

const doDeletePage = () => {
  if (pendingDeleteIndex.value !== null) {
    store.deletePage(pendingDeleteIndex.value)
  }
  pendingDeleteIndex.value = null
}

/**
 * 上移/下移页面（触屏和键盘可达的拖拽替代方案）
 */
const movePageBy = (index: number, offset: number) => {
  const target = index + offset
  if (target < 0 || target >= store.outline.pages.length) return
  store.movePage(index, target)
}

// ==================== 单页 AI 润色 ====================

// 正在润色的页面 key（同一时间只允许一页润色）
const polishingKey = ref<number | null>(null)
// 当前展开润色菜单的页面 key
const openMenuKey = ref<number | null>(null)
// 润色结果预览（key -> 新文案），应用后才写回 page.content
const polishPreviews = ref<Record<number, string>>({})
// 润色失败的错误信息（key -> 错误文本）
const polishErrors = ref<Record<number, string>>({})

const toggleMenu = (page: Page) => {
  const key = pageKey(page)
  openMenuKey.value = openMenuKey.value === key ? null : key
}

// 点击菜单外部时关闭下拉
const closeMenuOnOutsideClick = () => {
  openMenuKey.value = null
}

const runPolish = async (page: Page, instruction: PolishInstruction) => {
  openMenuKey.value = null
  // 同一时间只允许一页在润色
  if (polishingKey.value !== null) return

  const key = pageKey(page)
  delete polishErrors.value[key]
  delete polishPreviews.value[key]
  polishingKey.value = key

  try {
    // 本次创作选了品牌人设时，润色也带上，避免润色洗掉人设语气或引入禁用词
    const result = await polishPage(
      page.content,
      page.type,
      store.topic,
      instruction,
      store.brandId || undefined
    )
    if (result.success && result.content) {
      polishPreviews.value[key] = result.content
    } else {
      polishErrors.value[key] =
        result.error_message
        || (typeof result.error === 'string' ? result.error : '')
        || 'AI 润色失败，请稍后重试'
    }
  } catch (error) {
    polishErrors.value[key] = getApiErrorPayload(error, 'AI 润色失败，请稍后重试').error_message
  } finally {
    polishingKey.value = null
  }
}

const applyPolish = (page: Page) => {
  const key = pageKey(page)
  const next = polishPreviews.value[key]
  if (next === undefined) return
  // 写回 page.content，触发 store 深度 watch 的自动保存
  page.content = next
  store.updatePage(page.index, next)
  delete polishPreviews.value[key]
}

const discardPolish = (page: Page) => {
  delete polishPreviews.value[pageKey(page)]
}

const addPage = (type: 'cover' | 'content' | 'summary') => {
  store.addPage(type, '')
  // 滚动到底部
  nextTick(() => {
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })
}

const goBack = () => {
  // 显式回首页，避免 router.back() 在历史栈不确定时行为不可预测
  router.push('/')
}

const startGeneration = async () => {
  // 如果有待保存的内容，先强制保存
  if (saveTimer !== null) {
    clearTimeout(saveTimer)
    saveTimer = null
    await autoSaveOutline()
  }
  router.push('/generate')
}

// ==================== 自动保存功能 ====================

// 防抖定时器
let saveTimer: number | null = null

/**
 * 自动保存大纲到历史记录
 * 当大纲内容发生变化时，自动更新到后端
 */
const autoSaveOutline = async () => {
  // 如果没有 recordId，尝试创建历史记录
  if (!store.recordId) {
    if (store.outline.pages && store.outline.pages.length > 0) {
      try {
        const result = await createHistory(
          store.topic || '未命名主题',
          {
            raw: store.outline.raw,
            pages: store.outline.pages
          },
          store.taskId || undefined
        )
        if (result.success && result.record_id) {
          store.setRecordId(result.record_id)
        } else {
          console.warn('自动保存：创建历史记录失败')
          return
        }
      } catch (error) {
        console.error('自动保存：创建历史记录出错:', error)
        return
      }
    } else {
      return
    }
  }

  // 如果没有大纲内容，不需要保存
  if (!store.outline.pages || store.outline.pages.length === 0) {
    return
  }

  try {
    isSaving.value = true

    // 调用更新历史记录 API
    const recordId = store.recordId
    if (!recordId) return

    const result = await updateHistory(recordId, {
      outline: {
        raw: store.outline.raw,
        pages: store.outline.pages
      }
    })

    if (!result.success) {
      console.error('自动保存失败:', result.error)
    } else {
      console.log('大纲已自动保存')
    }
  } catch (error) {
    console.error('自动保存出错:', error)
  } finally {
    isSaving.value = false
  }
}

/**
 * 防抖函数：延迟执行保存操作
 * 避免用户频繁编辑时产生大量请求
 */
const debouncedSave = () => {
  // 清除之前的定时器
  if (saveTimer !== null) {
    clearTimeout(saveTimer)
  }

  // 设置新的定时器，300ms 后执行保存
  saveTimer = window.setTimeout(() => {
    autoSaveOutline()
    saveTimer = null
  }, 300)
}

/**
 * 页面加载时检查历史记录
 * 如果没有 recordId 但有大纲数据，尝试创建历史记录
 */
const checkAndCreateHistory = async () => {
  // 如果已经有 recordId，无需创建
  if (store.recordId) {
    console.log('已存在历史记录ID:', store.recordId)
    return
  }

  // 如果有大纲数据但没有 recordId，说明是异常情况，尝试创建
  if (store.outline.pages && store.outline.pages.length > 0) {
    console.log('检测到大纲数据但无历史记录ID，尝试创建历史记录')

    try {
      const result = await createHistory(
        store.topic || '未命名主题',
        {
          raw: store.outline.raw,
          pages: store.outline.pages
        },
        store.taskId || undefined
      )

      if (result.success && result.record_id) {
        store.setRecordId(result.record_id)
        console.log('历史记录创建成功，ID:', result.record_id)
      } else {
        console.error('创建历史记录失败:', result.error)
      }
    } catch (error) {
      console.error('创建历史记录出错:', error)
    }
  }
}

// 组件挂载时检查历史记录，并注册润色菜单的点击外部关闭
onMounted(async () => {
  document.addEventListener('click', closeMenuOnOutsideClick)
  await checkAndCreateHistory()
})

// 组件卸载时清理定时器和事件监听
onUnmounted(() => {
  document.removeEventListener('click', closeMenuOnOutsideClick)
  if (saveTimer !== null) {
    clearTimeout(saveTimer)
    saveTimer = null
  }
})

// 监听大纲变化，触发自动保存
watch(
  () => store.outline.pages,
  () => {
    // 使用防抖函数，避免频繁请求
    debouncedSave()
  },
  { deep: true } // 深度监听，确保能检测到数组内部对象的变化
)
</script>

<style scoped>
/* 当前风格提示条 */
.style-hint-wrap {
  max-width: 1200px;
  margin: -14px auto 24px auto;
  padding: 0 20px;
}

.style-hint {
  display: inline-flex;
  align-items: center;
  flex-wrap: wrap;
  gap: var(--space-2);
  max-width: 100%;
  padding: 8px 16px;
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  color: var(--color-info);
  background: var(--color-info-soft);
}

.style-hint.inactive {
  color: var(--text-sub);
  background: var(--gray-1);
  border: 1px solid var(--border-color);
}

.style-hint-colors {
  display: inline-flex;
  gap: 4px;
}

.style-hint-color {
  width: 12px;
  height: 12px;
  border-radius: var(--radius-full);
  border: 1px solid rgba(33, 30, 27, 0.1);
}

.style-hint-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.style-hint-link:hover {
  text-decoration: underline;
}

/* 保存状态指示器 */
.save-indicator {
  margin-left: var(--space-3);
  font-size: 12px;
  font-weight: 500;
  padding: 2px 8px;
  border-radius: var(--radius-xs);
  transition: color var(--transition-base), background var(--transition-base),
    opacity var(--transition-base);
}

.save-indicator.saving {
  color: var(--color-info);
  background: var(--color-info-soft);
  border: 1px solid var(--color-info-soft);
}

.save-indicator.saved {
  color: var(--color-success);
  background: var(--color-success-soft);
  border: 1px solid var(--color-success-soft);
  opacity: 0.7;
}

/* 网格布局 */
.outline-grid {
  display: grid;
  /* 响应式列：最小宽度 280px，自动填充 */
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: var(--space-5);
  max-width: 1400px;
  margin: 0 auto;
  padding: 0 20px;
}

.outline-card {
  display: flex;
  flex-direction: column;
  padding: var(--space-4);
  margin-bottom: 0; /* 间距交给 grid gap */
  /* 边框/圆角/阴影复用全局 .card（--radius-lg + --shadow-xs + --border-color） */
  min-height: 360px;
  position: relative;
}

.outline-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-hover);
  border-color: var(--border-hover);
  z-index: 10;
}

.outline-card.dragging-over {
  border: 2px dashed var(--primary);
  opacity: 0.8;
}

/* 顶部栏 */
.card-top-bar {
  display: flex;
  justify-content: space-between;
  align-items: center;
  margin-bottom: var(--space-3);
  padding-bottom: var(--space-2);
  border-bottom: 1px solid var(--border-color);
}

.page-info {
  display: flex;
  align-items: center;
  gap: var(--space-2);
}

.page-number {
  font-size: 14px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-secondary);
}

.outline-card:focus-within .page-number {
  color: var(--text-sub);
}

.page-type {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-weight: 600;
  text-transform: uppercase;
  letter-spacing: 0.5px;
}
.page-type.cover { color: var(--color-danger); background: var(--color-danger-soft); }
.page-type.content { color: var(--text-secondary); background: var(--gray-2); }
.page-type.summary { color: var(--color-success); background: var(--color-success-soft); }

.card-controls {
  display: flex;
  align-items: center;
  gap: var(--space-1);
  opacity: 0.85;
  transition: opacity var(--transition-fast);
}
.outline-card:hover .card-controls,
.outline-card:focus-within .card-controls { opacity: 1; }

/* 触屏设备无 hover，操作按钮保持完全可见 */
@media (hover: none) {
  .card-controls { opacity: 1; }
  .drag-handle { display: none; }
}

.drag-handle {
  cursor: grab;
  padding: 4px;
  color: var(--text-secondary);
  border-radius: var(--radius-xs);
  transition: color var(--transition-fast), background var(--transition-fast);
}
.drag-handle:hover { color: var(--text-main); background: var(--gray-2); }
.drag-handle:active { cursor: grabbing; }

.icon-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 4px;
  border-radius: var(--radius-xs);
  transition: color var(--transition-fast), background var(--transition-fast);
}
.icon-btn:hover:not(:disabled) { color: var(--text-main); background: var(--gray-2); }
.icon-btn.danger:hover:not(:disabled) { color: var(--color-danger); background: var(--color-danger-soft); }
.icon-btn:disabled {
  opacity: 0.3;
  cursor: not-allowed;
}

/* ==================== 单页 AI 润色 ==================== */
.polish-wrap {
  position: relative;
  display: inline-flex;
}

.polish-btn.active {
  color: var(--primary);
  background: var(--primary-fade);
}

.polish-btn:hover:not(:disabled) {
  color: var(--primary);
  background: var(--primary-fade);
}

/* 润色进行中的转圈指示 */
.polish-spinner {
  display: inline-block;
  width: 12px;
  height: 12px;
  border: 2px solid var(--primary-fade);
  border-top-color: var(--primary);
  border-radius: var(--radius-full);
  animation: polish-spin 0.7s linear infinite;
}

@keyframes polish-spin {
  to { transform: rotate(360deg); }
}

/* 三选项下拉菜单：右对齐避免小屏溢出 */
.polish-menu {
  position: absolute;
  top: calc(100% + 4px);
  right: 0;
  z-index: 30;
  min-width: 108px;
  padding: 4px;
  background: var(--card-bg, #fff);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm, 8px);
  box-shadow: var(--shadow-hover);
}

.polish-menu-item {
  display: block;
  width: 100%;
  padding: 6px 10px;
  border: none;
  background: none;
  text-align: left;
  font-size: 13px;
  color: var(--text-main);
  cursor: pointer;
  border-radius: var(--radius-xs);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.polish-menu-item:hover {
  color: var(--primary);
  background: var(--primary-fade);
}

/* 润色结果对比预览块 */
.polish-preview {
  margin-top: var(--space-3);
  padding: var(--space-3);
  border: 1px dashed var(--primary);
  border-radius: var(--radius-sm, 8px);
  background: var(--primary-fade);
}

.polish-preview-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
  font-size: 11px;
  font-weight: 700;
  color: var(--primary);
  margin-bottom: var(--space-2);
}

.polish-preview-text {
  font-size: 14px;
  line-height: 1.7;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  max-height: 240px;
  overflow-y: auto;
}

.polish-preview-actions {
  display: flex;
  gap: var(--space-2);
  margin-top: var(--space-2);
}

.polish-mini-btn {
  padding: 4px 14px;
  font-size: 12px;
  font-weight: 600;
  border-radius: var(--radius-xs);
  border: 1px solid var(--border-color);
  background: var(--card-bg, #fff);
  color: var(--text-secondary);
  cursor: pointer;
  transition: color var(--transition-fast), background var(--transition-fast),
    border-color var(--transition-fast);
}

.polish-mini-btn:hover {
  color: var(--text-main);
  border-color: var(--border-hover);
}

.polish-mini-btn.primary {
  background: var(--primary);
  border-color: var(--primary);
  color: #fff;
}

.polish-mini-btn.primary:hover {
  opacity: 0.9;
  color: #fff;
}

/* 润色失败错误提示（复用全局 danger 配色变量） */
.polish-error {
  margin-top: var(--space-2);
  padding: 6px 10px;
  font-size: 12px;
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border-radius: var(--radius-xs);
  word-break: break-word;
}

/* 润色中禁用的文本域 */
.textarea-paper:disabled {
  opacity: 0.5;
  cursor: wait;
}

/* 文本区域 - 核心 */
.textarea-paper {
  flex: 1; /* 占据剩余空间 */
  width: 100%;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 16px; /* 更大的字号 */
  line-height: 1.7; /* 舒适行高 */
  color: var(--text-main);
  resize: none; /* 禁止手动拉伸，保持卡片整体感 */
  font-family: inherit;
  margin-bottom: 10px;
}

.textarea-paper::placeholder {
  color: var(--text-placeholder);
}

.textarea-paper:focus {
  outline: none;
}

.word-count {
  text-align: right;
  font-size: 11px;
  color: var(--text-secondary);
  margin-top: auto;
}

.outline-card:focus-within .word-count {
  color: var(--text-sub);
}

/* 添加卡片 */
.add-card-dashed {
  border: 2px dashed var(--gray-4);
  background: transparent;
  box-shadow: none;
  display: flex;
  align-items: center;
  justify-content: center;
  cursor: pointer;
  min-height: 360px;
  margin-bottom: 0;
  color: var(--gray-5);
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.add-card-dashed:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-fade);
}

.add-content {
  text-align: center;
}

.add-icon {
  font-size: 32px;
  font-weight: 300;
  margin-bottom: var(--space-2);
}

/* 移动端适配 */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 14px;
  }

  .style-hint-wrap {
    margin-top: -8px;
    padding: 0 8px;
  }

  .outline-grid {
    grid-template-columns: 1fr;
    gap: 16px;
    padding: 0 8px;
  }

  .outline-card,
  .add-card-dashed {
    min-height: 240px;
  }
}
</style>
