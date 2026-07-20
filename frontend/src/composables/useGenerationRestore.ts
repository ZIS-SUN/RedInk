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

  /**
   * 从历史记录水合 generator store（全项目唯一水合入口）
   *
   * @param record 历史记录详情
   * @param options.target 目标场景：
   *  - 'restore'（默认）：生成流程的刷新恢复。保留本地未同步的内容编辑与参考图，
   *    并根据图片完成度把 stage 推进到 result/generating
   *  - 'edit'：从历史页打开记录进入编辑。先定向重置上一会话残留状态
   *    （标题/文案/标签、生成进度、旧图片/任务ID/用户上传图），防止上一篇内容串到新记录；
   *    stage 停留在 outline（由调用方跳转大纲页），没有已生成图片时保持空白生成状态
   *
   * 图片 URL 统一走 getImageUrl（缩略图展示）；下载入口自行替换为 ?thumbnail=false 原图。
   */
  function hydrateFromHistory(
    record: HistoryDetail,
    options: { target?: 'restore' | 'edit' } = {}
  ) {
    const target = options.target ?? 'restore'

    if (target === 'edit') {
      store.clearContent()
      store.progress = { current: 0, total: 0, status: 'idle' }
      store.images = []
      store.taskId = null
      store.userImages = []
      // 上一会话残留的大纲编辑标记不应带入新打开的记录
      store.setOutlineDirty(false)
    }

    store.setTopic(record.title)
    store.setOutline(record.outline.raw, record.outline.pages || [])
    store.setRecordId(record.id)

    const taskId = record.images.task_id
    const generated = record.images.generated || []
    const pages = record.outline.pages || []

    // edit 场景下没有任何已生成图片时不动图片/进度（保持上面重置后的空白状态）
    if (target === 'restore' || (taskId && generated.some(Boolean))) {
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
      const doneCount = store.images.filter(img => img.status === 'done').length
      store.progress.total = pages.length
      store.progress.current = doneCount
      store.progress.status = doneCount >= pages.length ? 'done' : 'error'
      if (target === 'restore') {
        store.stage = doneCount >= pages.length ? 'result' : 'generating'
      }
    }

    // 回填服务器上保存的发布内容（标题/文案/标签）。
    // 仅在本地没有内容（idle）时回填，避免覆盖用户本地未同步的编辑；旧记录无 content 则跳过。
    const savedContent = record.content
    if (savedContent && store.content.status === 'idle') {
      store.setContent(
        savedContent.titles || [],
        savedContent.copywriting || '',
        savedContent.tags || []
      )
    }
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
      || store.images.some(img => img.status === 'queued' || img.status === 'generating' || img.status === 'retrying')
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
        } else if (image.status === 'queued' || image.status === 'generating' || image.status === 'retrying') {
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
    hydrateFromHistory,
    restoreFromHistory,
    restoreInterruptedGeneration
  }
}
