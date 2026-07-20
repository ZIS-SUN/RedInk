import type { ComputedRef } from 'vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost } from '../api'
import { isAbortError } from '../api/client'
import { formatErrorMessage, normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'
import { useContentGeneration } from './useContentGeneration'
import { useStyleLibrary } from './useStyleLibrary'

/**
 * 前端本地生成任务ID（后端 /generate 接受客户端传入的 task_id）
 * 与后端格式保持一致：task_ + 8 位十六进制
 */
function createLocalTaskId(): string {
  const random = typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function'
    ? crypto.randomUUID().replace(/-/g, '').slice(0, 8)
    : Math.random().toString(16).slice(2, 10).padEnd(8, '0')
  return `task_${random}`
}

export function useGenerationRunner(
  hasFailedImages: ComputedRef<boolean>,
  setError: (error: AppError | null) => void
) {
  const router = useRouter()
  const store = useGeneratorStore()
  const { activeStyle } = useStyleLibrary()
  const { ensureRecord, restoreFromHistory, restoreInterruptedGeneration } = useGenerationRestore()
  const { autoGenerateOnce } = useContentGeneration()
  const redirectTimer = ref<number | null>(null)
  let isUnmounted = false
  let abortController: AbortController | null = null

  async function startGenerationFlow() {
    if (store.outline.pages.length === 0) {
      router.push('/')
      return
    }

    // 刷新/中断恢复：已有 taskId 时按任务状态续传，不盲目重开新任务
    if (await restoreInterruptedGeneration()) return

    // 大纲在上次生成后被编辑过时跳过旧图恢复，走全新生成让编辑生效；
    // 未编辑的刷新恢复场景保持原有行为（直接恢复历史里已生成的图片）
    if (!store.outlineDirty && await restoreFromHistory()) return

    await ensureRecord()

    // 大纲编辑后必须强制后端重新出图（force=true）：
    // 后端只要 record 里有旧图且 !force 就会原样回放缓存，编辑会静默失效。
    // startGeneration() 会把 outlineDirty 重置为 false，所以必须在调用它之前取值
    const mustForce = store.outlineDirty

    // 任务开始前就确定 taskId 并立即持久化，中途刷新也不会丢
    // 大纲编辑后的重新生成不复用旧任务ID，避免与已完成任务的状态混淆
    const taskId = (!mustForce && store.taskId) || createLocalTaskId()
    store.startGeneration()
    // 记录本次生成使用的风格提示词（空字符串表示未应用风格），
    // 写入 store 并随 setTaskId 一起立即持久化，重试/刷新恢复时沿用同一风格。
    // 优先级：风格库已应用的风格 > 工具注入的风格（如封面 A/B 的视觉概念）> 无风格，
    // 避免风格库为空时把工具注入的 stylePrompt 覆盖成空串
    const stylePrompt = activeStyle.value?.stylePrompt || store.stylePrompt || ''
    store.setStylePrompt(stylePrompt)
    store.setTaskId(taskId)

    abortController = new AbortController()

    generateImagesPost(
      store.outline.pages,
      taskId,
      store.outline.raw,
      (event) => {
        // progress 事件表示某页开始生成：标记开始时间与阶段，驱动实时进度展示
        // （batch_start 等汇总事件不带 index，或 index 为 -1，直接忽略）
        if (typeof event.index === 'number' && event.index >= 0 && event.status === 'generating') {
          store.markImageStarted(event.index, event.phase)
        }
      },
      (event) => {
        if (event.image_url) {
          store.updateProgress(event.index, 'done', event.image_url)
        }
      },
      (event) => {
        store.updateProgress(
          event.index,
          'error',
          undefined,
          formatErrorMessage(event.error || event.message || '图片生成失败', '图片生成失败')
        )
      },
      (event) => {
        store.finishGeneration(event.task_id)

        if (!hasFailedImages.value) {
          redirectTimer.value = window.setTimeout(() => {
            if (!isUnmounted) {
              router.push('/result')
            }
          }, 1000)
        }
      },
      (err) => {
        // 主动取消（离开页面）不算错误
        if (isAbortError(err) || isUnmounted) return

        console.error('图片生成流中断:', err)
        // 断流时把仍在生成中的图片批量置为可重试的 error，
        // 并把整体进度置为 error，让"补全失败图片"入口出现
        store.markGeneratingAsError(formatErrorMessage(err, '生成中断'))
        setError(normalizeApiError(err, '图片生成失败'))
      },
      store.userImages.length > 0 ? store.userImages : undefined,
      store.topic,
      store.recordId,
      mustForce,
      { signal: abortController.signal, stylePrompt }
    )

    // 出图已启动：并行触发一次标题/文案/标签生成（内容只依赖 topic + 大纲，
    // 与图片零依赖），用户到结果页时内容通常已就绪，无需再手动点击等待。
    // 同一记录只自动触发一次，失败时结果页保留手动重新生成入口兜底
    autoGenerateOnce()
  }

  /**
   * 取消完成后的 1 秒自动跳转（不影响 SSE 流与卸载标志）。
   * 生成完成（isDone）时只需要取消跳转，不能把组件标记为已卸载，
   * 否则后续真实的 SSE 错误会被 onStreamError 静默吞掉。
   */
  function cancelAutoRedirect() {
    if (redirectTimer.value !== null) {
      clearTimeout(redirectTimer.value)
      redirectTimer.value = null
    }
  }

  function cleanupGenerationRunner() {
    isUnmounted = true
    // 离开页面时中止 SSE fetch，避免回调操作已卸载的组件
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    cancelAutoRedirect()
  }

  return {
    cancelAutoRedirect,
    cleanupGenerationRunner,
    startGenerationFlow
  }
}
