import { useGeneratorStore } from '../stores/generator'
import {
  createHistory,
  getHistory,
  getImageUrl,
  getTaskState,
  type HistoryDetail
} from '../api'

export function useGenerationRestore() {
  const store = useGeneratorStore()

  function hasGeneratedImages(record: HistoryDetail): boolean {
    return !!record.images?.task_id && (record.images.generated || []).some(Boolean)
  }

  function hydrateFromHistory(record: HistoryDetail) {
    const taskId = record.images.task_id
    const generated = record.images.generated || []
    const pages = record.outline.pages || []
    const doneCount = pages.reduce((count, page, idx) => {
      const filename = generated[page.index] || generated[idx]
      return filename ? count + 1 : count
    }, 0)

    store.setTopic(record.title)
    store.setOutline(record.outline.raw, pages)
    store.setRecordId(record.id)
    store.setTaskId(taskId)
    store.images = pages.map((page, idx) => {
      const filename = generated[page.index] || generated[idx] || ''
      return {
        index: page.index,
        url: filename && taskId ? getImageUrl(taskId, filename) : '',
        status: filename ? 'done' : 'error',
        retryable: !filename
      }
    })
    store.progress.total = pages.length
    store.progress.current = doneCount
    store.progress.status = doneCount >= pages.length ? 'done' : 'error'
    store.stage = doneCount >= pages.length ? 'result' : 'generating'
  }

  async function restoreFromHistory(): Promise<boolean> {
    if (!store.recordId) return false

    const res = await getHistory(store.recordId)
    if (!res.success || !res.record) return false

    if (!hasGeneratedImages(res.record)) return false

    hydrateFromHistory(res.record)
    return true
  }

  /**
   * 恢复被中断的生成任务（如生成中途刷新页面）
   *
   * 判定条件：store 里已有 taskId + 本次任务的图片占位，且进度仍处于 generating。
   * 恢复策略：
   * - 优先查询后端 /task/:taskId 的任务状态，把已生成的图片补成 done、失败的标为 error
   * - 后端无该任务状态时（如后端重启），把仍在生成中的图片批量标为可重试的 error
   * 两种情况都不会重新开一个全新任务，避免重复生成、双倍消耗配额。
   *
   * @returns true 表示已按中断任务恢复，调用方不应再发起新的生成
   */
  async function restoreInterruptedGeneration(): Promise<boolean> {
    const taskId = store.taskId
    if (!taskId || store.images.length === 0) return false

    const wasInterrupted = store.progress.status === 'generating'
      || store.images.some(img => img.status === 'generating' || img.status === 'retrying')
    if (!wasInterrupted) return false

    const res = await getTaskState(taskId)
    if (res.success && res.state) {
      const generated = res.state.generated || {}
      const failed = res.state.failed || {}
      store.images.forEach(image => {
        const key = String(image.index)
        const filename = generated[key]
        if (filename) {
          store.updateProgress(image.index, 'done', getImageUrl(taskId, filename))
        } else if (image.status === 'generating' || image.status === 'retrying') {
          store.updateProgress(
            image.index,
            'error',
            undefined,
            failed[key] || '生成中断，可点击重试补全'
          )
        }
      })
    } else {
      // 后端已无该任务的内存状态：仍在生成中的一律标为可重试
      store.markGeneratingAsError('页面刷新导致生成中断，可点击重试补全')
    }

    // 重新汇总进度，避免恢复过程中的重复计数
    const doneCount = store.images.filter(img => img.status === 'done').length
    store.progress.total = store.images.length
    store.progress.current = doneCount

    if (doneCount >= store.images.length) {
      store.finishGeneration(taskId)
    } else {
      store.progress.status = 'error'
      store.stage = 'generating'
    }
    return true
  }

  async function ensureRecord() {
    if (store.recordId) return

    try {
      const result = await createHistory(store.topic, {
        raw: store.outline.raw,
        pages: store.outline.pages
      })
      if (result.success && result.record_id) {
        store.setRecordId(result.record_id)
      }
    } catch (e) {
      console.error('兜底创建历史记录失败:', e)
    }
  }

  return {
    ensureRecord,
    restoreFromHistory,
    restoreInterruptedGeneration
  }
}
