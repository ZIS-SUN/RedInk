/**
 * 多尺寸批量导出编排 composable
 *
 * 输入：图片来源列表（url 或本地 File）× 选中的尺寸预设 × 适配/背景/水印选项
 * 输出：逐张渲染 PNG 并触发浏览器下载，同时暴露进度与错误状态供 UI 展示
 */
import { computed, ref } from 'vue'
import {
  buildExportFilename,
  downloadBlob,
  exportImageToBlob,
  type BackgroundOption,
  type FitMode,
  type SizePreset,
  type WatermarkOptions
} from '../utils/canvasExport'

/** 一个待导出的图片来源 */
export interface ExportSource {
  /** 展示与命名用的名字（不含扩展名也可） */
  name: string
  /** 图片地址（同源 url）或本地文件 */
  data: string | Blob
}

/** 批量导出选项 */
export interface BatchExportOptions {
  fit: FitMode
  background?: BackgroundOption
  watermark?: WatermarkOptions
}

/** 单项导出结果 */
export interface ExportTaskResult {
  sourceName: string
  presetLabel: string
  filename: string
  success: boolean
  error?: string
}

/** 相邻两次触发下载之间的间隔（ms），避免浏览器拦截连续下载 */
const DOWNLOAD_INTERVAL_MS = 300

export function useMultiSizeExport() {
  const exporting = ref(false)
  const current = ref(0)
  const total = ref(0)
  const results = ref<ExportTaskResult[]>([])

  const failedCount = computed(() => results.value.filter(r => !r.success).length)
  const progressText = computed(() =>
    total.value > 0 ? `${current.value} / ${total.value}` : ''
  )

  /**
   * 批量导出：sources × presets 逐张渲染并下载 PNG
   * 单张失败不会中断整体，失败明细记录在 results 中
   */
  async function exportAll(
    sources: ExportSource[],
    presets: SizePreset[],
    options: BatchExportOptions
  ): Promise<ExportTaskResult[]> {
    if (exporting.value || sources.length === 0 || presets.length === 0) return []

    exporting.value = true
    current.value = 0
    total.value = sources.length * presets.length
    results.value = []

    try {
      for (const source of sources) {
        for (const preset of presets) {
          const filename = buildExportFilename(source.name, preset)
          try {
            const blob = await exportImageToBlob(source.data, {
              width: preset.width,
              height: preset.height,
              fit: options.fit,
              background: options.background,
              watermark: options.watermark
            })
            downloadBlob(blob, filename)
            results.value.push({
              sourceName: source.name,
              presetLabel: `${preset.label} ${preset.ratio}`,
              filename,
              success: true
            })
          } catch (e) {
            results.value.push({
              sourceName: source.name,
              presetLabel: `${preset.label} ${preset.ratio}`,
              filename,
              success: false,
              error: e instanceof Error ? e.message : '导出失败'
            })
          }
          current.value++
          // 间隔触发下载，避免浏览器把连续下载判定为骚扰行为
          if (current.value < total.value) {
            await new Promise(resolve => setTimeout(resolve, DOWNLOAD_INTERVAL_MS))
          }
        }
      }
      return results.value
    } finally {
      exporting.value = false
    }
  }

  return {
    exporting,
    current,
    total,
    results,
    failedCount,
    progressText,
    exportAll
  }
}
