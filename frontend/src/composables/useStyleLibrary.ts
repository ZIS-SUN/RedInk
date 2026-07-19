/**
 * useStyleLibrary - 风格模板库的 localStorage 读写封装
 *
 * 1. 当前应用的风格存入 localStorage（key: redink_active_style），
 *    存储内容为 JSON: { id, name, stylePrompt, colors }。
 * 2. 用户自定义模板存入 localStorage（key: redink_custom_styles），
 *    存储内容为 JSON: StyleTemplate[]（每项 custom: true）。
 * 独立于现有 stores/composables，供未来生成管线集成时读取。
 */
import { ref, computed, readonly } from 'vue'
import { styleTemplates, type StyleTemplate } from '../data/styleTemplates'

export const ACTIVE_STYLE_STORAGE_KEY = 'redink_active_style'
export const CUSTOM_STYLES_STORAGE_KEY = 'redink_custom_styles'

/** localStorage 中保存的已应用风格 */
export interface ActiveStyle {
  id: string
  name: string
  stylePrompt: string
  colors: string[]
}

function loadFromStorage(): ActiveStyle | null {
  try {
    const raw = localStorage.getItem(ACTIVE_STYLE_STORAGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      parsed &&
      typeof parsed.id === 'string' &&
      typeof parsed.name === 'string' &&
      typeof parsed.stylePrompt === 'string' &&
      Array.isArray(parsed.colors)
    ) {
      return parsed as ActiveStyle
    }
    return null
  } catch {
    return null
  }
}

/** 校验单个自定义模板结构，容忍旧数据/脏数据 */
function isValidTemplate(value: unknown): value is StyleTemplate {
  if (!value || typeof value !== 'object') return false
  const t = value as Record<string, unknown>
  return (
    typeof t.id === 'string' &&
    typeof t.name === 'string' &&
    typeof t.category === 'string' &&
    typeof t.description === 'string' &&
    typeof t.coverGradient === 'string' &&
    Array.isArray(t.colors) &&
    Array.isArray(t.scenes) &&
    typeof t.stylePrompt === 'string'
  )
}

function loadCustomFromStorage(): StyleTemplate[] {
  try {
    const raw = localStorage.getItem(CUSTOM_STYLES_STORAGE_KEY)
    if (!raw) return []
    const parsed = JSON.parse(raw)
    if (!Array.isArray(parsed)) return []
    return parsed.filter(isValidTemplate).map(t => ({ ...t, custom: true as const }))
  } catch {
    return []
  }
}

function saveCustomToStorage(list: StyleTemplate[]) {
  try {
    localStorage.setItem(CUSTOM_STYLES_STORAGE_KEY, JSON.stringify(list))
  } catch (e) {
    console.error('保存自定义风格到 localStorage 失败:', e)
  }
}

// 模块级单例状态：同一会话内多处使用时保持同步
const activeStyle = ref<ActiveStyle | null>(loadFromStorage())
const customStyles = ref<StyleTemplate[]>(loadCustomFromStorage())

// 合并后的模板列表：预设在前，自定义在后
const allTemplates = computed<StyleTemplate[]>(() => [...styleTemplates, ...customStyles.value])

export function useStyleLibrary() {
  /** 应用某个风格模板（写入 localStorage） */
  function applyStyle(template: StyleTemplate) {
    const value: ActiveStyle = {
      id: template.id,
      name: template.name,
      stylePrompt: template.stylePrompt,
      colors: template.colors
    }
    activeStyle.value = value
    try {
      localStorage.setItem(ACTIVE_STYLE_STORAGE_KEY, JSON.stringify(value))
    } catch (e) {
      console.error('保存风格到 localStorage 失败:', e)
    }
  }

  /** 清除当前已应用的风格 */
  function clearStyle() {
    activeStyle.value = null
    try {
      localStorage.removeItem(ACTIVE_STYLE_STORAGE_KEY)
    } catch (e) {
      console.error('清除 localStorage 风格失败:', e)
    }
  }

  /** 判断某个模板是否为当前已应用风格 */
  function isActive(templateId: string): boolean {
    return activeStyle.value?.id === templateId
  }

  /** 从 localStorage 重新读取（跨标签页/外部修改后可手动刷新） */
  function refresh() {
    activeStyle.value = loadFromStorage()
    customStyles.value = loadCustomFromStorage()
  }

  /** 新增自定义模板（自动生成 id 与 custom 标记），返回创建后的模板 */
  function addCustomStyle(input: Omit<StyleTemplate, 'id' | 'custom'>): StyleTemplate {
    const template: StyleTemplate = {
      ...input,
      id: `custom-${Date.now()}-${Math.random().toString(36).slice(2, 8)}`,
      custom: true
    }
    customStyles.value = [...customStyles.value, template]
    saveCustomToStorage(customStyles.value)
    return template
  }

  /** 更新自定义模板（按 id 匹配），成功返回 true；预设模板不可更新 */
  function updateCustomStyle(
    id: string,
    patch: Partial<Omit<StyleTemplate, 'id' | 'custom'>>
  ): boolean {
    const index = customStyles.value.findIndex(t => t.id === id)
    if (index === -1) return false
    const updated: StyleTemplate = { ...customStyles.value[index], ...patch, id, custom: true }
    customStyles.value = customStyles.value.map((t, i) => (i === index ? updated : t))
    saveCustomToStorage(customStyles.value)
    // 若被更新的模板正处于应用状态，同步刷新已应用风格
    if (activeStyle.value?.id === id) {
      applyStyle(updated)
    }
    return true
  }

  /** 删除自定义模板（按 id 匹配），成功返回 true；预设模板不可删除 */
  function removeCustomStyle(id: string): boolean {
    const index = customStyles.value.findIndex(t => t.id === id)
    if (index === -1) return false
    customStyles.value = customStyles.value.filter(t => t.id !== id)
    saveCustomToStorage(customStyles.value)
    // 若被删除的模板正处于应用状态，一并取消应用
    if (activeStyle.value?.id === id) {
      clearStyle()
    }
    return true
  }

  /** 判断某个 id 是否为自定义模板 */
  function isCustom(templateId: string): boolean {
    return customStyles.value.some(t => t.id === templateId)
  }

  return {
    /** 当前已应用的风格（只读响应式） */
    activeStyle: readonly(activeStyle),
    applyStyle,
    clearStyle,
    isActive,
    refresh,
    /** 自定义模板列表（只读响应式） */
    customStyles: readonly(customStyles),
    /** 合并后的模板列表：预设 + 自定义（只读响应式） */
    allTemplates,
    addCustomStyle,
    updateCustomStyle,
    removeCustomStyle,
    isCustom
  }
}
