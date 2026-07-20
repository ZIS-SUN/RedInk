<template>
  <div class="container" style="max-width: 100%;">
    <StepIndicator :current="2" />

    <div class="page-header" style="max-width: 1200px; margin: 0 auto 30px auto;">
      <div>
        <h1 class="page-title">编辑大纲</h1>
        <p class="page-subtitle">
          调整页面顺序，修改文案，打造完美内容
          <span v-if="saveState === 'saving'" class="save-indicator saving">保存中…</span>
          <button
            v-else-if="saveState === 'error'"
            type="button"
            class="save-indicator save-error"
            @click="autoSaveOutline"
          >保存失败，点击重试</button>
          <span v-else class="save-indicator saved">{{ lastSavedTime ? `已保存 ${lastSavedTime}` : '已保存' }}</span>
        </p>
        <!-- 换一版大纲失败的错误提示 -->
        <div v-if="regenerateError" class="regenerate-error" role="alert">
          {{ regenerateError }}
        </div>
      </div>
      <div style="display: flex; gap: 12px;">
        <button class="btn btn-secondary" @click="goBack">
          上一步
        </button>
        <button
          class="btn btn-secondary"
          :disabled="regenerating || !store.topic.trim()"
          :title="store.topic.trim() ? '不满意当前大纲？让 AI 重新生成一版' : '缺少主题，无法重新生成'"
          @click="requestRegenerate"
        >
          <span v-if="regenerating" class="btn-spinner" aria-hidden="true"></span>
          <svg v-else width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><polyline points="23 4 23 10 17 10"></polyline><path d="M20.49 15a9 9 0 1 1-2.12-9.36L23 10"></path></svg>
          {{ regenerating ? '生成中…' : '换一版' }}
        </button>
        <button class="btn btn-primary" :disabled="regenerating" @click="startGeneration">
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
          <!-- 带上来源参数，风格页据此提供「返回大纲」动线 -->
          <RouterLink to="/tools/style?from=outline" class="style-hint-link">去风格模板库选择</RouterLink>
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

      <!-- 添加按钮卡片：点击默认加内容页，小箭头可展开选择页面类型 -->
      <div class="card add-card-dashed" @click="addPage('content')">
        <div class="add-content">
          <div class="add-icon">+</div>
          <span class="add-label">
            添加页面
            <button
              type="button"
              class="add-type-btn"
              :class="{ active: addMenuOpen }"
              title="选择页面类型"
              aria-label="选择要添加的页面类型"
              aria-haspopup="menu"
              :aria-expanded="addMenuOpen"
              @click.stop="addMenuOpen = !addMenuOpen"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" aria-hidden="true"><polyline points="6 9 12 15 18 9"/></svg>
            </button>
          </span>
          <span class="add-hint">点击添加内容页 · 箭头选类型</span>
        </div>
        <div v-if="addMenuOpen" class="add-type-menu" role="menu" @click.stop>
          <button class="add-type-menu-item" role="menuitem" @click="addPage('cover')">封面页</button>
          <button class="add-type-menu-item" role="menuitem" @click="addPage('content')">内容页</button>
          <button class="add-type-menu-item" role="menuitem" @click="addPage('summary')">总结页</button>
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

    <!-- 换一版大纲确认弹窗：会丢弃当前编辑，需要用户明确确认 -->
    <ConfirmDialog
      :visible="showRegenerateConfirm"
      title="换一版大纲？"
      message="将丢弃当前大纲和你的修改，重新生成一版，确定？"
      confirm-text="重新生成"
      danger
      @confirm="doRegenerate"
      @cancel="showRegenerateConfirm = false"
    />

    <!-- 空白页确认弹窗：空文案页会白白消耗按张计费的生成额度，先提醒 -->
    <ConfirmDialog
      :visible="showBlankPagesConfirm"
      title="有页面还没有文案"
      :message="blankPagesConfirmMessage"
      confirm-text="仍然生成"
      cancel-text="去填写"
      @confirm="confirmGenerateAnyway"
      @cancel="cancelBlankPagesConfirm"
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
  generateOutline,
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
// 保存状态指示（三态：保存中 / 已保存 / 保存失败可重试）
const saveState = ref<'saved' | 'saving' | 'error'>('saved')
// 最近一次保存成功的时间（HH:mm），用于「已保存 HH:mm」展示
const lastSavedTime = ref('')
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

// 点击菜单外部时关闭下拉（润色菜单与加页类型菜单共用同一个全局监听）
const closeMenuOnOutsideClick = () => {
  openMenuKey.value = null
  addMenuOpen.value = false
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

// 「添加页面」的类型选择下拉是否展开
const addMenuOpen = ref(false)

const addPage = (type: 'cover' | 'content' | 'summary') => {
  store.addPage(type, '')
  addMenuOpen.value = false
  nextTick(() => {
    // 新页追加在列表末尾：按索引定位新卡片的输入框并聚焦，让用户落地即可打字
    const areas = document.querySelectorAll<HTMLTextAreaElement>('.outline-grid .textarea-paper')
    const target = areas[store.outline.pages.length - 1]
    target?.focus({ preventScroll: true })
    // 滚动到底部（聚焦用 preventScroll 避免瞬跳，交给平滑滚动）
    window.scrollTo({ top: document.body.scrollHeight, behavior: 'smooth' })
  })
}

const goBack = () => {
  // 显式回首页，避免 router.back() 在历史栈不确定时行为不可预测
  router.push('/')
}

// ==================== 换一版大纲 ====================

// 换一版确认弹窗可见性
const showRegenerateConfirm = ref(false)
// 重新生成进行中（按钮 loading 态）
const regenerating = ref(false)
// 重新生成失败的错误提示
const regenerateError = ref('')

/**
 * 点击「换一版」：先弹确认弹窗（会丢弃当前大纲与用户修改）
 */
const requestRegenerate = () => {
  if (regenerating.value) return
  regenerateError.value = ''
  showRegenerateConfirm.value = true
}

/**
 * 确认后重新生成一版大纲：
 * 复用与首页一致的生成入口（携带同样的参考图与品牌人设），
 * 成功后用 store.setOutline 原地替换，recordId 保持不变
 * （深度 watch 触发的自动保存会把新大纲更新到同一条历史记录，不新建）
 */
const doRegenerate = async () => {
  showRegenerateConfirm.value = false
  if (regenerating.value) return

  const topic = store.topic.trim()
  if (!topic) {
    regenerateError.value = '缺少主题，无法重新生成大纲'
    return
  }

  regenerating.value = true
  regenerateError.value = ''

  try {
    const result = await generateOutline(
      topic,
      store.userImages.length > 0 ? store.userImages : undefined,
      store.brandId || undefined
    )

    if (result.success && result.pages) {
      // 原地替换大纲；大纲整体换新后旧图不应再被复用，标记 dirty 强制全新生成
      store.setOutline(result.outline || '', result.pages)
      store.setOutlineDirty(true)
    } else {
      regenerateError.value =
        result.error_message
        || (typeof result.error === 'string' ? result.error : '')
        || '重新生成大纲失败，请稍后重试'
    }
  } catch (error) {
    regenerateError.value = getApiErrorPayload(error, '重新生成大纲失败，请稍后重试').error_message
  } finally {
    regenerating.value = false
  }
}

// ==================== 生成前空白页校验 + 成本预告 ====================

// 空白页确认弹窗可见性与文案
const showBlankPagesConfirm = ref(false)
const blankPagesConfirmMessage = ref('')

/**
 * 找出没有文案（空或纯空白字符）的页码（从 1 开始，与卡片上的「第 N 页」一致）
 */
const findBlankPageNumbers = (): number[] => {
  return store.outline.pages
    .map((page, idx) => (page.content.trim() ? -1 : idx + 1))
    .filter(no => no > 0)
}

const startGeneration = async () => {
  // 如果有待保存的内容，先强制保存
  if (saveTimer !== null) {
    clearTimeout(saveTimer)
    saveTimer = null
    await autoSaveOutline()
  }

  // 空白页会被发给按张计费的图像模型：存在时先确认并预告成本；无空白页则不打断
  const blankPages = findBlankPageNumbers()
  if (blankPages.length > 0) {
    const total = store.outline.pages.length
    blankPagesConfirmMessage.value =
      `第 ${blankPages.join('、')} 页还没有文案，生成会消耗额度且可能产出无意义图片。\n\n`
      + `本次共 ${total} 页 · 每张约 1 分钟。`
    showBlankPagesConfirm.value = true
    return
  }

  router.push('/generate')
}

/**
 * 空白页弹窗选「仍然生成」：按当前大纲继续
 */
const confirmGenerateAnyway = () => {
  showBlankPagesConfirm.value = false
  router.push('/generate')
}

/**
 * 空白页弹窗选「去填写」：留在大纲页补文案
 */
const cancelBlankPagesConfirm = () => {
  showBlankPagesConfirm.value = false
}

// ==================== 自动保存功能 ====================

// 防抖定时器
let saveTimer: number | null = null

/**
 * HH:mm 格式的时间文本（「已保存 HH:mm」展示用）
 */
const formatSaveTime = (date: Date): string => {
  const hh = String(date.getHours()).padStart(2, '0')
  const mm = String(date.getMinutes()).padStart(2, '0')
  return `${hh}:${mm}`
}

/**
 * 自动保存大纲到历史记录
 * 当大纲内容发生变化时，自动更新到后端；
 * 失败时把指示器置为「保存失败」，点击可重试（重试直接绑定本函数）
 */
const autoSaveOutline = async () => {
  // 如果没有大纲内容，不需要保存
  if (!store.outline.pages || store.outline.pages.length === 0) {
    return
  }

  saveState.value = 'saving'

  try {
    // 如果没有 recordId，先尝试创建历史记录
    if (!store.recordId) {
      const created = await createHistory(
        store.topic || '未命名主题',
        {
          raw: store.outline.raw,
          pages: store.outline.pages
        },
        store.taskId || undefined
      )
      if (created.success && created.record_id) {
        store.setRecordId(created.record_id)
      } else {
        console.warn('自动保存：创建历史记录失败')
        saveState.value = 'error'
        return
      }
    }

    const recordId = store.recordId
    if (!recordId) {
      saveState.value = 'error'
      return
    }

    // 调用更新历史记录 API
    const result = await updateHistory(recordId, {
      outline: {
        raw: store.outline.raw,
        pages: store.outline.pages
      }
    })

    if (result.success) {
      store.markSaved()
      lastSavedTime.value = formatSaveTime(new Date())
      saveState.value = 'saved'
    } else {
      console.error('自动保存失败:', result.error)
      saveState.value = 'error'
    }
  } catch (error) {
    console.error('自动保存出错:', error)
    saveState.value = 'error'
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

/* 保存失败态：warning 色 + 可点击重试 */
.save-indicator.save-error {
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border: 1px solid var(--color-warning-soft);
  font-family: inherit;
  cursor: pointer;
}

.save-indicator.save-error:hover {
  text-decoration: underline;
}

/* 换一版按钮的加载转圈（复用润色的旋转动画） */
.btn-spinner {
  display: inline-block;
  width: 14px;
  height: 14px;
  margin-right: 6px;
  border: 2px solid currentColor;
  border-top-color: transparent;
  border-radius: var(--radius-full);
  animation: polish-spin 0.7s linear infinite;
}

/* 换一版失败的错误提示 */
.regenerate-error {
  display: inline-block;
  margin-top: var(--space-2);
  padding: 6px 10px;
  font-size: 12px;
  color: var(--color-danger);
  background: var(--color-danger-soft);
  border-radius: var(--radius-xs);
  word-break: break-word;
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
  background: var(--bg-card);
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
  background: var(--bg-card);
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
  position: relative;
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

.add-label {
  display: inline-flex;
  align-items: center;
  gap: 4px;
}

/* 页面类型选择的小箭头（阻止冒泡，避免触发默认加内容页） */
.add-type-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  padding: 4px;
  border: none;
  background: transparent;
  color: inherit;
  cursor: pointer;
  border-radius: var(--radius-xs);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.add-type-btn:hover,
.add-type-btn.active {
  color: var(--primary);
  background: var(--primary-fade);
}

.add-hint {
  display: block;
  margin-top: var(--space-2);
  font-size: 12px;
  color: var(--text-secondary);
}

/* 三种页面类型的下拉菜单（视觉复用润色菜单） */
.add-type-menu {
  position: absolute;
  top: calc(50% + 56px);
  left: 50%;
  transform: translateX(-50%);
  z-index: 30;
  min-width: 120px;
  padding: 4px;
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm, 8px);
  box-shadow: var(--shadow-hover);
}

.add-type-menu-item {
  display: block;
  width: 100%;
  padding: 8px 12px;
  border: none;
  background: none;
  text-align: left;
  font-size: 13px;
  color: var(--text-main);
  cursor: pointer;
  border-radius: var(--radius-xs);
  transition: background var(--transition-fast), color var(--transition-fast);
}

.add-type-menu-item:hover {
  color: var(--primary);
  background: var(--primary-fade);
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
