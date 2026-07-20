/**
 * 生成器状态管理 Store
 *
 * 功能说明：
 * - 管理图片生成的完整流程状态（输入主题 -> 生成大纲 -> 编辑大纲 -> 生成图片 -> 查看结果）
 * - 支持历史记录的保存和恢复
 * - 支持本地 localStorage 持久化，防止页面刷新后数据丢失
 * - 支持内容生成（标题、文案、标签）
 *
 * 状态流转：
 * 1. input: 用户输入主题
 * 2. outline: 生成并编辑大纲
 * 3. generating: 正在生成图片
 * 4. result: 查看生成结果
 */
import { defineStore } from 'pinia'
import type { Page } from '../api/types'
import { withCacheBuster } from '../utils/url'
import { removeAt } from '../utils/contentEdit'

/**
 * 生成的图片信息
 */
export interface GeneratedImage {
  index: number  // 图片对应的页面索引
  url: string    // 图片URL
  status: 'queued' | 'generating' | 'done' | 'error' | 'retrying'  // 生成状态
  error?: string      // 错误信息
  retryable?: boolean // 是否可以重试
  startedAt?: number  // 本张图开始生成的时间（epoch 毫秒），用于进度估算
  durationMs?: number // 本张图完成耗时（毫秒），用作后续图片的时长样本
}

/**
 * 生成的内容数据（标题、文案、标签）
 */
export interface GeneratedContent {
  titles: string[]     // 标题列表（多个备选）
  copywriting: string  // 文案内容
  tags: string[]       // 标签列表
  status: 'idle' | 'generating' | 'done' | 'error'  // 生成状态
  error?: string       // 错误信息
}

export interface GeneratorState {
  // 当前阶段：input-输入主题, outline-编辑大纲, generating-生成中, result-查看结果
  stage: 'input' | 'outline' | 'generating' | 'result'

  // 用户输入的主题
  topic: string

  // 大纲数据（包含原始文本和解析后的页面列表）
  outline: {
    raw: string      // 原始大纲文本
    pages: Page[]    // 解析后的页面数组
  }

  // 图片生成进度
  progress: {
    current: number  // 当前已完成的数量
    total: number    // 总共需要生成的数量
    status: 'idle' | 'generating' | 'done' | 'error'
    phase?: string   // 当前生成阶段：'cover' 封面 / 'content' 内容页
  }

  // 生成的图片结果列表
  images: GeneratedImage[]

  // 图片生成任务ID（用于轮询任务状态）
  taskId: string | null

  // 本次生成使用的风格提示词（来自风格模板库，空字符串表示未应用风格）
  // 记录在 store 中以便刷新恢复、重试时沿用同一风格
  stylePrompt: string

  // 本次创作使用的品牌档案 ID（空字符串表示不使用品牌人设）
  // 大纲生成与正文/标题/标签生成时都会作为 brand_id 传给后端
  brandId: string

  // 历史记录ID（用于保存和加载历史记录）
  recordId: string | null

  // 大纲在上次生成开始之后是否被编辑过。
  // 为 true 时进入生成页会跳过"从历史恢复旧图"，强制走全新生成，确保编辑生效；
  // 在 startGeneration()（新一轮生成已使用最新大纲）时清除
  outlineDirty: boolean

  // 用户上传的参考图片（File对象，不会被持久化）
  userImages: File[]

  // 生成的内容数据（标题、文案、标签）
  content: GeneratedContent

  // 大纲生成状态：idle-未开始, generating-生成中, done-已完成, error-出错
  outlineStatus: 'idle' | 'generating' | 'done' | 'error'

  // 最后一次保存到服务器的时间（ISO格式字符串）
  lastSavedAt: string | null
}

const STORAGE_KEY = 'generator-state'

// 持久化数据的版本号：结构不兼容时递增，旧数据会被直接丢弃
const STORAGE_VERSION = 1

const VALID_STAGES = ['input', 'outline', 'generating', 'result'] as const
const VALID_PROGRESS_STATUS = ['idle', 'generating', 'done', 'error'] as const

/**
 * 校验从 localStorage 恢复的数据是否为合法 shape
 * 只做关键字段的类型检查，不合法整体丢弃，避免脏数据污染 store
 */
function isValidPersistedState(data: unknown): data is Partial<GeneratorState> {
  if (!data || typeof data !== 'object') return false
  const d = data as Record<string, unknown>

  if (d.stage !== undefined && !VALID_STAGES.includes(d.stage as never)) return false
  if (d.topic !== undefined && typeof d.topic !== 'string') return false

  if (d.outline !== undefined) {
    const outline = d.outline as Record<string, unknown>
    if (!outline || typeof outline !== 'object') return false
    if (typeof outline.raw !== 'string' || !Array.isArray(outline.pages)) return false
  }

  if (d.progress !== undefined) {
    const progress = d.progress as Record<string, unknown>
    if (!progress || typeof progress !== 'object') return false
    if (typeof progress.current !== 'number' || typeof progress.total !== 'number') return false
    if (!VALID_PROGRESS_STATUS.includes(progress.status as never)) return false
  }

  if (d.images !== undefined && !Array.isArray(d.images)) return false
  if (d.taskId !== undefined && d.taskId !== null && typeof d.taskId !== 'string') return false
  if (d.recordId !== undefined && d.recordId !== null && typeof d.recordId !== 'string') return false
  if (d.stylePrompt !== undefined && typeof d.stylePrompt !== 'string') return false
  if (d.brandId !== undefined && typeof d.brandId !== 'string') return false
  if (d.outlineDirty !== undefined && typeof d.outlineDirty !== 'boolean') return false

  return true
}

// 从 localStorage 加载状态（带版本号 + shape 校验，不合法直接丢弃）
function loadState(): Partial<GeneratorState> {
  try {
    const saved = localStorage.getItem(STORAGE_KEY)
    if (!saved) return {}

    const parsed: unknown = JSON.parse(saved)
    if (!parsed || typeof parsed !== 'object') return {}

    const { version, ...data } = parsed as { version?: number } & Record<string, unknown>
    if (version !== STORAGE_VERSION) {
      // 版本不匹配（含旧版无 version 字段的数据），丢弃并清理
      localStorage.removeItem(STORAGE_KEY)
      return {}
    }
    if (!isValidPersistedState(data)) {
      localStorage.removeItem(STORAGE_KEY)
      return {}
    }
    return data
  } catch (e) {
    console.error('加载状态失败:', e)
  }
  return {}
}

// 保存状态到 localStorage
function saveState(state: GeneratorState) {
  try {
    // 只保存关键数据，不保存 userImages（文件对象无法序列化）
    const toSave = {
      version: STORAGE_VERSION,              // 持久化版本号
      stage: state.stage,                    // 当前阶段
      topic: state.topic,                    // 用户输入的主题
      outline: state.outline,                // 大纲数据
      progress: state.progress,              // 生成进度
      images: state.images,                  // 生成的图片结果
      taskId: state.taskId,                  // 任务ID
      stylePrompt: state.stylePrompt,        // 本次生成的风格提示词
      brandId: state.brandId,                // 本次创作使用的品牌档案ID
      recordId: state.recordId,              // 历史记录ID
      outlineDirty: state.outlineDirty,      // 大纲是否在上次生成后被编辑过
      content: state.content,                // 生成的内容（标题、文案、标签）
      outlineStatus: state.outlineStatus,    // 大纲生成状态
      lastSavedAt: state.lastSavedAt         // 最后保存时间
    }
    localStorage.setItem(STORAGE_KEY, JSON.stringify(toSave))
  } catch (e) {
    console.error('保存状态失败:', e)
  }
}

export const useGeneratorStore = defineStore('generator', {
  state: (): GeneratorState => {
    const saved = loadState()
    return {
      // 当前阶段
      stage: saved.stage || 'input',

      // 用户输入的主题
      topic: saved.topic || '',

      // 大纲数据
      outline: saved.outline || {
        raw: '',
        pages: []
      },

      // 图片生成进度
      progress: saved.progress || {
        current: 0,
        total: 0,
        status: 'idle'
      },

      // 生成的图片结果
      images: saved.images || [],

      // 任务ID
      taskId: saved.taskId || null,

      // 本次生成的风格提示词
      stylePrompt: saved.stylePrompt || '',

      // 本次创作使用的品牌档案ID
      brandId: saved.brandId || '',

      // 历史记录ID
      recordId: saved.recordId || null,

      // 大纲是否在上次生成后被编辑过
      outlineDirty: saved.outlineDirty === true,

      // 用户上传的参考图片（不从 localStorage 恢复）
      userImages: [],

      // 生成的内容数据
      content: saved.content || {
        titles: [],
        copywriting: '',
        tags: [],
        status: 'idle'
      },

      // 大纲生成状态
      outlineStatus: saved.outlineStatus || 'idle',

      // 最后保存时间
      lastSavedAt: saved.lastSavedAt || null
    }
  },

  actions: {
    /**
     * 设置用户输入的主题
     * @param topic 主题内容
     */
    setTopic(topic: string) {
      this.topic = topic
    },

    /**
     * 设置大纲数据
     * @param raw 原始大纲文本
     * @param pages 解析后的页面数组
     */
    setOutline(raw: string, pages: Page[]) {
      this.outline.raw = raw
      this.outline.pages = pages
      this.stage = 'outline'
      this.outlineStatus = 'done'  // 设置大纲为已完成状态
    },

    /**
     * 更新指定页面的内容
     * @param index 页面索引
     * @param content 新的页面内容
     */
    updatePage(index: number, content: string) {
      const page = this.outline.pages.find(p => p.index === index)
      if (page) {
        page.content = content
        // 同步更新 raw 文本
        this.syncRawFromPages()
        this.markOutlineDirty()
      }
    },

    /**
     * 标记大纲被用户编辑过（增删改页、排序）。
     * 生成页据此跳过"从历史恢复旧图"，强制重新生成，避免编辑静默失效。
     */
    markOutlineDirty() {
      this.outlineDirty = true
    },

    /**
     * 设置大纲编辑标记（从历史打开新记录等场景需要显式清除残留标记）
     * @param dirty 是否被编辑过
     */
    setOutlineDirty(dirty: boolean) {
      this.outlineDirty = dirty
    },

    /**
     * 根据 pages 数组重新生成 raw 文本
     * 用于保持 raw 和 pages 的数据同步
     */
    syncRawFromPages() {
      this.outline.raw = this.outline.pages
        .map(page => page.content)
        .join('\n\n<page>\n\n')
    },

    /**
     * 删除指定索引的页面
     * @param index 页面索引
     */
    deletePage(index: number) {
      this.outline.pages = this.outline.pages.filter(p => p.index !== index)
      // 重新索引所有页面
      this.outline.pages.forEach((page, idx) => {
        page.index = idx
      })
      // 同步更新 raw 文本
      this.syncRawFromPages()
      this.markOutlineDirty()
    },

    /**
     * 在列表末尾添加新页面
     * @param type 页面类型：cover-封面, content-内容, summary-总结
     * @param content 页面内容，默认为空
     */
    addPage(type: 'cover' | 'content' | 'summary', content: string = '') {
      const newPage: Page = {
        index: this.outline.pages.length,
        type,
        content
      }
      this.outline.pages.push(newPage)
      // 同步更新 raw 文本
      this.syncRawFromPages()
      this.markOutlineDirty()
    },

    /**
     * 在指定位置后插入新页面
     * @param afterIndex 在此索引后插入
     * @param type 页面类型
     * @param content 页面内容
     */
    insertPage(afterIndex: number, type: 'cover' | 'content' | 'summary', content: string = '') {
      const newPage: Page = {
        index: afterIndex + 1,
        type,
        content
      }
      this.outline.pages.splice(afterIndex + 1, 0, newPage)
      // 重新索引所有页面
      this.outline.pages.forEach((page, idx) => {
        page.index = idx
      })
      // 同步更新 raw 文本
      this.syncRawFromPages()
      this.markOutlineDirty()
    },

    /**
     * 移动页面位置（用于拖拽排序）
     * @param fromIndex 源位置索引
     * @param toIndex 目标位置索引
     */
    movePage(fromIndex: number, toIndex: number) {
      const pages = [...this.outline.pages]
      const [movedPage] = pages.splice(fromIndex, 1)
      pages.splice(toIndex, 0, movedPage)

      // 重新索引所有页面
      pages.forEach((page, idx) => {
        page.index = idx
      })

      this.outline.pages = pages
      // 同步更新 raw 文本
      this.syncRawFromPages()
      this.markOutlineDirty()
    },

    /**
     * 开始图片生成流程
     * 初始化进度状态和图片列表
     */
    startGeneration() {
      this.stage = 'generating'
      this.progress.current = 0
      this.progress.total = this.outline.pages.length
      this.progress.status = 'generating'
      // 新一轮生成基于最新大纲，编辑标记归零
      this.outlineDirty = false
      // 为每个页面创建对应的图片占位对象（串行生成，初始都在排队中）
      this.images = this.outline.pages.map(page => ({
        index: page.index,
        url: '',
        status: 'queued'
      }))
    },

    /**
     * 标记某张图片开始生成（SSE progress 事件触发）
     * @param index 页面索引
     * @param phase 当前阶段：'cover' 封面 / 'content' 内容页
     */
    markImageStarted(index: number, phase?: string) {
      const image = this.images.find(img => img.index === index)
      if (image && (image.status === 'queued' || image.status === 'generating')) {
        image.status = 'generating'
        // 已有 startedAt 时不覆盖，避免重复事件重置计时
        if (!image.startedAt) {
          image.startedAt = Date.now()
        }
      }
      if (phase) {
        this.progress.phase = phase
      }
    },

    /**
     * 更新图片生成进度
     * @param index 页面索引
     * @param status 生成状态
     * @param url 图片URL（可选）
     * @param error 错误信息（可选）
     */
    updateProgress(index: number, status: 'generating' | 'done' | 'error', url?: string, error?: string) {
      const image = this.images.find(img => img.index === index)
      if (!image) return

      // 幂等保护：重复的 complete 事件不会重复计数
      const wasDone = image.status === 'done'

      image.status = status
      if (url) image.url = url
      if (error) {
        image.error = error
      } else if (status !== 'error') {
        delete image.error
      }
      if (status === 'error') {
        image.retryable = true
      }

      // 完成时记录单张耗时，作为后续图片的预期时长样本
      if (status === 'done' && image.startedAt && image.durationMs === undefined) {
        image.durationMs = Date.now() - image.startedAt
      }

      // 成功完成时增加计数（只在从"未完成"变为"完成"时）
      if (status === 'done' && !wasDone && this.progress.current < this.progress.total) {
        this.progress.current++
      }
    },

    /**
     * 更新指定图片的URL
     * @param index 页面索引
     * @param newUrl 新的图片URL
     */
    updateImage(index: number, newUrl: string) {
      const image = this.images.find(img => img.index === index)
      if (image) {
        const wasDone = image.status === 'done'
        // 追加时间戳避免缓存（正确处理 URL 上已有的 query，如 ?thumbnail=true）
        image.url = withCacheBuster(newUrl)
        image.status = 'done'
        delete image.error
        if (!wasDone && this.progress.current < this.progress.total) {
          this.progress.current++
        }
      }
    },

    /**
     * 设置图片生成任务ID，并立即持久化到 localStorage
     * 用于流开始时尽早落库，防止刷新丢失 taskId 导致重复生成
     * @param taskId 任务ID，null 表示清空
     */
    setTaskId(taskId: string | null) {
      this.taskId = taskId
      // 立即写入 localStorage，不等防抖的自动保存
      this.saveToStorage()
    },

    /**
     * 设置本次生成使用的风格提示词（来自风格模板库）
     * 生成开始时写入，重试/刷新恢复时从这里读取同一风格
     * @param stylePrompt 风格提示词，空字符串表示未应用风格
     */
    setStylePrompt(stylePrompt: string) {
      this.stylePrompt = stylePrompt
    },

    /**
     * 设置本次创作使用的品牌档案 ID
     * 大纲生成与正文/标题/标签生成会用它作为 brand_id 传给后端
     * @param brandId 品牌档案 ID，空字符串表示不使用品牌人设
     */
    setBrandId(brandId: string) {
      this.brandId = brandId
    },

    /**
     * 把所有仍处于 queued/generating/retrying 状态的图片批量置为 error（可重试）
     * 用于 SSE 断流/网络中断时，让"补全失败图片"入口可用
     * @param error 错误信息，默认为断流提示
     */
    markGeneratingAsError(error: string = '生成中断，请重试') {
      let changed = false
      this.images.forEach(image => {
        // 排队中的图片也应可重试：中断时同样置为 error
        if (image.status === 'queued' || image.status === 'generating' || image.status === 'retrying') {
          image.status = 'error'
          image.error = image.error || error
          image.retryable = true
          changed = true
        }
      })
      if (changed || this.progress.status === 'generating') {
        this.progress.status = 'error'
      }
    },

    /**
     * 完成图片生成流程
     * @param taskId 生成任务的ID
     */
    finishGeneration(taskId: string) {
      this.taskId = taskId
      this.stage = 'result'
      this.progress.status = 'done'
    },

    /**
     * 设置指定图片为重试中状态
     * @param index 页面索引
     */
    setImageRetrying(index: number) {
      const image = this.images.find(img => img.index === index)
      if (image) {
        image.status = 'retrying'
        // 重试视为重新开始计时
        image.startedAt = Date.now()
        delete image.durationMs
      }
    },

    /**
     * 获取所有生成失败的图片列表
     * @returns 失败的图片数组
     */
    getFailedImages() {
      return this.images.filter(img => img.status === 'error')
    },

    /**
     * 获取生成失败的图片对应的页面
     * @returns 失败页面的数组
     */
    getFailedPages() {
      const failedIndices = this.images
        .filter(img => img.status === 'error')
        .map(img => img.index)
      return this.outline.pages.filter(page => failedIndices.includes(page.index))
    },

    /**
     * 检查是否存在生成失败的图片
     * @returns true-存在失败的图片, false-所有图片都成功
     */
    hasFailedImages() {
      return this.images.some(img => img.status === 'error')
    },

    /**
     * 重置所有状态到初始值
     * 用于开始新的生成任务时清空之前的数据
     */
    reset() {
      // 重置当前阶段为输入阶段
      this.stage = 'input'

      // 清空用户输入的主题
      this.topic = ''

      // 清空大纲数据
      this.outline = {
        raw: '',      // 原始大纲文本
        pages: []     // 解析后的页面数组
      }

      // 重置图片生成进度
      this.progress = {
        current: 0,   // 已完成数量归零
        total: 0,     // 总数归零
        status: 'idle' // 状态设为空闲
      }

      // 清空生成的图片结果
      this.images = []

      // 清空任务ID
      this.taskId = null

      // 清空本次生成的风格提示词
      this.stylePrompt = ''

      // 清空本次创作使用的品牌档案ID
      this.brandId = ''

      // 清空历史记录ID
      this.recordId = null

      // 清除大纲编辑标记
      this.outlineDirty = false

      // 清空用户上传的参考图片
      this.userImages = []

      // 重置生成的内容数据
      this.content = {
        titles: [],          // 清空标题列表
        copywriting: '',     // 清空文案
        tags: [],            // 清空标签列表
        status: 'idle'       // 状态设为空闲
      }

      // 重置大纲生成状态
      this.outlineStatus = 'idle'

      // 清空最后保存时间
      this.lastSavedAt = null

      // 清除 localStorage 中的持久化数据
      localStorage.removeItem(STORAGE_KEY)
    },

    /**
     * 开始生成内容（标题、文案、标签）
     * 设置状态为生成中并清除之前的错误
     */
    startContentGeneration() {
      this.content.status = 'generating'
      this.content.error = undefined
    },

    /**
     * 设置生成的内容数据
     * @param titles 标题列表
     * @param copywriting 文案内容
     * @param tags 标签列表
     */
    setContent(titles: string[], copywriting: string, tags: string[]) {
      this.content.titles = titles
      this.content.copywriting = copywriting
      this.content.tags = tags
      this.content.status = 'done'
      this.content.error = undefined
    },

    /**
     * 更新指定索引的标题文本（结果页 inline 编辑用）
     * 空白文本视为无效输入，直接忽略
     * @param index 标题索引
     * @param text 新标题文本
     */
    updateContentTitle(index: number, text: string) {
      const trimmed = text.trim()
      if (!trimmed) return
      if (index < 0 || index >= this.content.titles.length) return
      this.content.titles[index] = trimmed
    },

    /**
     * 删除指定索引的标题
     * @param index 标题索引
     */
    removeContentTitle(index: number) {
      this.content.titles = removeAt(this.content.titles, index)
    },

    /**
     * 更新文案内容（结果页编辑用）
     * @param text 新文案全文
     */
    updateCopywriting(text: string) {
      this.content.copywriting = text
    },

    /**
     * 整体替换标签列表（结果页增删标签用）
     * @param tags 新标签数组
     */
    updateTags(tags: string[]) {
      this.content.tags = tags
    },

    /**
     * 设置内容生成失败的错误信息
     * @param error 错误描述
     */
    setContentError(error: string) {
      this.content.status = 'error'
      this.content.error = error
    },

    /**
     * 清除生成的内容数据
     * 重置为初始状态
     */
    clearContent() {
      this.content = {
        titles: [],
        copywriting: '',
        tags: [],
        status: 'idle'
      }
    },

    /**
     * 设置大纲生成状态
     * @param status 大纲生成状态：idle-未开始, generating-生成中, done-已完成, error-出错
     */
    setOutlineStatus(status: 'idle' | 'generating' | 'done' | 'error') {
      this.outlineStatus = status
    },

    /**
     * 设置历史记录ID（带验证）
     * @param recordId 历史记录ID，null表示清空
     */
    setRecordId(recordId: string | null) {
      // 验证recordId格式（如果不为null）
      if (recordId !== null && typeof recordId !== 'string') {
        console.error('recordId 必须是字符串或 null')
        return
      }

      this.recordId = recordId

      // 如果设置了新的recordId，同时更新最后保存时间
      if (recordId !== null) {
        this.lastSavedAt = new Date().toISOString()
      }
    },

    /**
     * 标记已保存到服务器
     * 更新最后保存时间为当前时间
     */
    markSaved() {
      this.lastSavedAt = new Date().toISOString()
    },

    /**
     * 保存当前状态到 localStorage
     * 用于浏览器刷新后恢复状态
     */
    saveToStorage() {
      saveState(this)
    }
  }
})

// 监听状态变化并自动保存（使用 watch）
import { watch } from 'vue'

/**
 * 设置自动保存功能
 * 监听store中关键字段的变化，防抖后保存到localStorage
 * （生成过程中 SSE 事件非常频繁，全量序列化需要防抖，避免每个事件都 stringify）
 */
export function setupAutoSave(debounceMs: number = 500) {
  const store = useGeneratorStore()

  let saveTimer: ReturnType<typeof setTimeout> | null = null

  const flush = () => {
    if (saveTimer !== null) {
      clearTimeout(saveTimer)
      saveTimer = null
    }
    store.saveToStorage()
  }

  const scheduleSave = () => {
    if (saveTimer !== null) clearTimeout(saveTimer)
    saveTimer = setTimeout(flush, debounceMs)
  }

  // 监听关键字段变化并防抖保存到localStorage
  watch(
    () => ({
      stage: store.stage,                    // 当前阶段
      topic: store.topic,                    // 用户输入的主题
      outline: store.outline,                // 大纲数据
      progress: store.progress,              // 生成进度
      images: store.images,                  // 生成的图片结果
      taskId: store.taskId,                  // 任务ID
      stylePrompt: store.stylePrompt,        // 本次生成的风格提示词
      brandId: store.brandId,                // 本次创作使用的品牌档案ID
      recordId: store.recordId,              // 历史记录ID
      outlineDirty: store.outlineDirty,      // 大纲是否在上次生成后被编辑过
      content: store.content,                // 生成的内容
      outlineStatus: store.outlineStatus,    // 大纲生成状态
      lastSavedAt: store.lastSavedAt         // 最后保存时间
    }),
    scheduleSave,
    { deep: true }  // 深度监听，确保对象内部的变化也能被捕获
  )

  // 页面关闭/刷新前立即落盘，避免丢失防抖窗口内的最后一次变更
  if (typeof window !== 'undefined') {
    window.addEventListener('beforeunload', flush)
  }
}
