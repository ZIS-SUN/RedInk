import { computed, ref, watch } from 'vue'
import type { GeneratedImage } from '../stores/generator'
import { useGeneratorStore } from '../stores/generator'
import {
  estimateRemainingMs,
  expectedDurationMs,
  formatDuration,
  overallPercent,
  singleImagePercent
} from '../utils/generationTiming'

/**
 * 生成中实时进度可视化的数据源
 *
 * 内部用 500ms 节拍器驱动 now，把 store 里的 startedAt/durationMs
 * 换算成平滑的整体百分比、单图百分比、已用时长和剩余时间估算。
 * 节拍器只在有图片处于生成/重试中时运行，watch 自动启停。
 *
 * 注意：节拍器驱动的是信息更新（不是装饰动画），prefers-reduced-motion
 * 下照常运行；过渡动画的关闭由组件的 CSS media query 负责。
 */
export function useGenerationProgress() {
  const store = useGeneratorStore()

  const now = ref(Date.now())
  let timer: ReturnType<typeof setInterval> | null = null

  const isActive = computed(() =>
    store.progress.status === 'generating' ||
    store.images.some(img => img.status === 'generating' || img.status === 'retrying')
  )

  function startTicker() {
    if (timer !== null) return
    now.value = Date.now()
    timer = setInterval(() => {
      now.value = Date.now()
    }, 500)
  }

  function stopTicker() {
    if (timer !== null) {
      clearInterval(timer)
      timer = null
    }
  }

  const stopWatcher = watch(isActive, (active) => {
    if (active) {
      startTicker()
    } else {
      stopTicker()
    }
  }, { immediate: true })

  /** 组件卸载时调用，停止节拍器和监听 */
  function stop() {
    stopWatcher()
    stopTicker()
  }

  /** 单张图片预期时长：优先用本次已完成图片的实际耗时样本 */
  const expected = computed(() => {
    const samples = store.images
      .filter(img => img.status === 'done' && typeof img.durationMs === 'number')
      .map(img => img.durationMs as number)
    return expectedDurationMs(samples)
  })

  function elapsedMsFor(image: GeneratedImage): number {
    if (!image.startedAt) return 0
    return Math.max(0, now.value - image.startedAt)
  }

  /** 单张图片的伪进度百分比（0~97） */
  function percentFor(image: GeneratedImage): number {
    return singleImagePercent(elapsedMsFor(image), expected.value)
  }

  /** 单张图片的已用时长文案，如「已用 45 秒」；无 startedAt 返回 '' */
  function elapsedTextFor(image: GeneratedImage): string {
    if (!image.startedAt) return ''
    return `已用 ${formatDuration(elapsedMsFor(image))}`
  }

  /** 整体进度百分比：已完成数 + 进行中图片的完成比例，平滑增长 */
  const overallPercentValue = computed(() => {
    const doneCount = store.images.filter(img => img.status === 'done').length
    const activeFractions = store.images
      .filter(img => img.status === 'generating' || img.status === 'retrying')
      .map(img => percentFor(img) / 100)
    return overallPercent(doneCount, store.progress.total, activeFractions)
  })

  /** 剩余时间估算文案，如「约剩 3 分 20 秒」；无进行中/排队图片返回 '' */
  const etaText = computed(() => {
    const activeElapsed = store.images
      .filter(img => img.status === 'generating' || img.status === 'retrying')
      .map(img => elapsedMsFor(img))
    const queuedCount = store.images.filter(img => img.status === 'queued').length
    if (activeElapsed.length === 0 && queuedCount === 0) return ''
    const remaining = estimateRemainingMs(queuedCount, activeElapsed, expected.value)
    return `约剩 ${formatDuration(remaining)}`
  })

  /** 当前阶段文案 */
  const phaseText = computed(() => {
    if (store.progress.phase === 'cover') return '正在生成封面'
    if (store.progress.phase === 'content') return '正在生成内容页'
    return '正在生成'
  })

  return {
    expected,
    overallPercentValue,
    etaText,
    phaseText,
    percentFor,
    elapsedTextFor,
    stop
  }
}
