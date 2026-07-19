import type { ComputedRef } from 'vue'
import { ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateImagesPost } from '../api'
import { isAbortError } from '../api/client'
import { formatErrorMessage, normalizeApiError, type AppError } from '../utils/errors'
import { useGenerationRestore } from './useGenerationRestore'
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

    if (await restoreFromHistory()) return

    await ensureRecord()

    // 任务开始前就确定 taskId 并立即持久化，中途刷新也不会丢
    const taskId = store.taskId || createLocalTaskId()
    store.startGeneration()
    // 记录本次生成使用的风格提示词（空字符串表示未应用风格），
    // 写入 store 并随 setTaskId 一起立即持久化，重试/刷新恢复时沿用同一风格
    const stylePrompt = activeStyle.value?.stylePrompt || ''
    store.setStylePrompt(stylePrompt)
    store.setTaskId(taskId)

    abortController = new AbortController()

    generateImagesPost(
      store.outline.pages,
      taskId,
      store.outline.raw,
      () => {
        // progress 事件仅表示某页开始生成，占位图已在 startGeneration 中创建
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
      false,
      { signal: abortController.signal, stylePrompt }
    )
  }

  function cleanupGenerationRunner() {
    isUnmounted = true
    // 离开页面时中止 SSE fetch，避免回调操作已卸载的组件
    if (abortController) {
      abortController.abort()
      abortController = null
    }
    if (redirectTimer.value !== null) {
      clearTimeout(redirectTimer.value)
      redirectTimer.value = null
    }
  }

  return {
    cleanupGenerationRunner,
    startGenerationFlow
  }
}
