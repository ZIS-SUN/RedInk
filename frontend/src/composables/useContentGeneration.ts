/**
 * 标题/文案/标签内容生成 composable（生成页与结果页共享）
 *
 * 背景：内容生成只依赖 topic + outline.raw + brandId，与出图零依赖。
 * 生成页出图启动后即可并行触发（autoGenerateOnce），用户到结果页时
 * 内容通常已就绪，无需再手动点击并额外等待一次。
 *
 * 生成状态统一放在 generator store（content.status），模块级变量只负责：
 * - inFlight：同一时刻只允许一个内容生成请求
 * - autoTriggeredKeys：同一条记录只自动触发一次（手动重新生成不受限）
 * - contentSyncTimer：内容同步落库的防抖定时器（跨页面存活，离开页面也能落库）
 */
import { useGeneratorStore } from '../stores/generator'
import { generateContent, updateHistory } from '../api'
import { formatErrorMessage } from '../utils/errors'

/** 是否有内容生成请求正在进行（模块级：跨生成页/结果页共享，防重复请求） */
let inFlight = false

/** 已自动触发过内容生成的记录 ID 集合（无记录 ID 时以空串兜底） */
const autoTriggeredKeys = new Set<string>()

/** content 同步落库的防抖定时器 */
let contentSyncTimer: number | null = null

/** 内容同步落库的防抖时长（毫秒） */
const CONTENT_SYNC_DEBOUNCE_MS = 800

export function useContentGeneration() {
  const store = useGeneratorStore()

  /**
   * 生成成功与每次编辑保存后，防抖把标题/文案/标签同步进历史记录。
   * 失败静默（本地 store 已持久化到 localStorage，不打扰用户）。
   */
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
    }, CONTENT_SYNC_DEBOUNCE_MS)
  }

  /**
   * 发起一次内容生成（标题/文案/标签）。
   * 请求参数与结果页原有手动逻辑完全一致：topic + outline.raw + brandId，
   * 用户填了目标搜索词时额外带上 seoKeywords（搜索埋词）
   */
  async function generate() {
    if (inFlight) return
    inFlight = true
    store.startContentGeneration()

    try {
      const result = await generateContent(
        store.topic,
        store.outline.raw,
        store.brandId || undefined,
        // 未填搜索词时不传该参数，请求体保持向后兼容
        store.seoKeywords.length > 0 ? [...store.seoKeywords] : undefined
      )

      if (result.success && result.titles && result.copywriting && result.tags) {
        store.setContent(result.titles, result.copywriting, result.tags)
        scheduleContentSync()
      } else {
        store.setContentError(
          formatErrorMessage(result.error || result.error_message || '生成失败', '内容生成失败')
        )
      }
    } catch (error: unknown) {
      store.setContentError(formatErrorMessage(error, '内容生成失败'))
    } finally {
      inFlight = false
    }
  }

  /**
   * 生成页出图启动后调用：与出图并行自动生成一次内容。
   * 已有内容（done）或正在生成时不触发；同一条记录只自动触发一次，
   * 避免重试出图/返回大纲再进入等场景重复消耗生成额度。
   * 结果页手动点「重新生成」走 generate()，不受本函数限制。
   */
  function autoGenerateOnce() {
    if (store.content.status === 'done' || store.content.status === 'generating') return

    const key = store.recordId || ''
    if (autoTriggeredKeys.has(key)) return
    autoTriggeredKeys.add(key)

    void generate()
  }

  /**
   * 校正刷新残留的「生成中」孤儿状态。
   * content.status 会随 localStorage 持久化：内容生成中途刷新页面后，
   * 状态仍是 generating 但请求早已不存在，不校正的话结果页会永远停在 loading。
   * 置为 error 让用户看到手动「重新生成」入口。
   */
  function reconcileInterruptedGeneration() {
    if (store.content.status === 'generating' && !inFlight) {
      store.setContentError('内容生成因页面刷新中断，请点击重新生成')
    }
  }

  return {
    autoGenerateOnce,
    generate,
    reconcileInterruptedGeneration,
    scheduleContentSync
  }
}
