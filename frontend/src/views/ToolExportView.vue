<template>
  <div class="container export-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">多尺寸导出</h1>
        <p class="page-subtitle">把已有图片一键适配小红书、抖音、公众号等平台尺寸，浏览器本地完成，不上传服务器</p>
      </div>
    </div>

    <!-- 1. 图片来源 -->
    <div class="card">
      <h2 class="section-title">1. 选择图片来源</h2>
      <div class="source-tabs">
        <button
          v-for="tab in sourceTabs"
          :key="tab.key"
          type="button"
          class="source-tab"
          :class="{ active: sourceTab === tab.key }"
          :aria-pressed="sourceTab === tab.key"
          @click="switchSourceTab(tab.key)"
        >
          {{ tab.label }}
        </button>
      </div>

      <!-- 上传 -->
      <div v-if="sourceTab === 'upload'">
        <label class="upload-zone">
          <input
            type="file"
            accept="image/*"
            multiple
            style="display: none;"
            @change="onFilesSelected"
          />
          <svg width="28" height="28" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"></path><polyline points="17 8 12 3 7 8"></polyline><line x1="12" y1="3" x2="12" y2="15"></line></svg>
          <span>点击选择图片（支持多选）</span>
        </label>
        <p v-if="uploadedItems.length === 0" class="empty-tip">
          三步完成：① 上传或选择图片 → ② 勾选目标尺寸与适配策略 → ③ 批量导出下载，全程在浏览器本地完成。
        </p>
      </div>

      <!-- 从当前结果 -->
      <div v-else-if="sourceTab === 'result'">
        <p v-if="resultImages.length === 0" class="empty-tip">
          当前工作区没有已生成的图片，先去「首页」创作一篇，或改用上传图片。
        </p>
      </div>

      <!-- 从历史记录 -->
      <div v-else>
        <div class="history-bar">
          <select v-model="selectedRecordId" class="history-select" @change="loadHistoryImages">
            <option value="" disabled>选择一条历史记录…</option>
            <option v-for="record in historyRecords" :key="record.id" :value="record.id">
              {{ record.title }}（{{ record.page_count }} 页）
            </option>
          </select>
          <span v-if="historyLoading" class="loading-tip">加载中…</span>
        </div>
        <p v-if="historyError" class="error-tip">{{ historyError }}</p>
        <p v-else-if="!historyLoading && selectedRecordId && candidateSources.length === 0" class="empty-tip">
          这条记录没有可用图片。
        </p>
      </div>

      <!-- 候选图片列表（可勾选） -->
      <div v-if="candidateSources.length > 0" class="thumb-grid">
        <div
          v-for="item in candidateSources"
          :key="item.key"
          class="thumb-item"
          :class="{ selected: selectedKeys.has(item.key) }"
          @click="toggleSource(item.key)"
        >
          <img :src="item.thumbUrl" :alt="item.name" loading="lazy" @error="markThumbBroken(item.key)" />
          <span v-if="brokenThumbKeys.has(item.key)" class="thumb-broken">图片加载失败</span>
          <span class="thumb-check">✓</span>
          <span class="thumb-name">{{ item.name }}</span>
          <button
            v-if="item.removable"
            type="button"
            class="thumb-remove"
            title="移除"
            :aria-label="`移除 ${item.name}`"
            @click.stop="removeUpload(item.key)"
          >×</button>
        </div>
      </div>
      <p v-if="candidateSources.length > 0" class="select-summary">
        已选 {{ selectedKeys.size }} / {{ candidateSources.length }} 张
        <button type="button" class="link-btn" @click="selectAllSources">全选</button>
        <button type="button" class="link-btn" @click="selectedKeys.clear()">清空</button>
      </p>
    </div>

    <!-- 2. 尺寸与选项 -->
    <div class="card">
      <h2 class="section-title">2. 目标尺寸（可多选）</h2>
      <div class="preset-grid">
        <label
          v-for="preset in SIZE_PRESETS"
          :key="preset.id"
          class="preset-item"
          :class="{ selected: selectedPresetIds.has(preset.id) }"
        >
          <input
            type="checkbox"
            :checked="selectedPresetIds.has(preset.id)"
            style="display: none;"
            @change="togglePreset(preset.id)"
          />
          <span class="preset-label">{{ preset.label }}</span>
          <span class="preset-ratio">{{ preset.ratio }}</span>
          <span class="preset-size">{{ preset.width }}×{{ preset.height }}</span>
        </label>
      </div>

      <h2 class="section-title" style="margin-top: 24px;">3. 适配策略</h2>
      <div class="option-row">
        <label class="radio-item" :class="{ selected: fit === 'contain' }">
          <input v-model="fit" type="radio" value="contain" style="display: none;" />
          留白（完整显示）
        </label>
        <label class="radio-item" :class="{ selected: fit === 'cover' }">
          <input v-model="fit" type="radio" value="cover" style="display: none;" />
          裁切填满
        </label>
      </div>

      <template v-if="fit === 'contain'">
        <div class="option-row" style="margin-top: 12px;">
          <span class="option-label">留白背景：</span>
          <label class="radio-item small" :class="{ selected: bgType === 'blur' }">
            <input v-model="bgType" type="radio" value="blur" style="display: none;" />
            原图高斯模糊
          </label>
          <label class="radio-item small" :class="{ selected: bgType === 'color' }">
            <input v-model="bgType" type="radio" value="color" style="display: none;" />
            纯色
          </label>
          <input v-if="bgType === 'color'" v-model="bgColor" type="color" class="color-input" />
        </div>
      </template>

      <h2 class="section-title" style="margin-top: 24px;">4. 水印（可选）</h2>
      <div class="option-row watermark-row">
        <input
          v-model="watermarkText"
          type="text"
          class="watermark-input"
          placeholder="水印文字，留空则不加（显示在右下角）"
          maxlength="30"
        />
        <label v-if="watermarkText.trim()" class="opacity-label">
          透明度 {{ Math.round(watermarkOpacity * 100) }}%
          <input v-model.number="watermarkOpacity" type="range" min="0.1" max="1" step="0.05" />
        </label>
      </div>
    </div>

    <!-- 3. 预览 -->
    <div v-if="selectedSources.length > 0 && selectedPresets.length > 0" class="card">
      <h2 class="section-title">
        预览
        <span class="section-sub">（第一张选中图片 × 各选中尺寸）</span>
      </h2>
      <p v-if="previewError" class="error-tip">{{ previewError }}</p>
      <div class="preview-row">
        <figure v-for="p in previews" :key="p.presetId" class="preview-item">
          <img :src="p.dataUrl" :alt="p.label" />
          <figcaption>{{ p.label }}</figcaption>
        </figure>
        <span v-if="previewLoading" class="loading-tip">预览生成中…</span>
      </div>
    </div>

    <!-- 4. 导出 -->
    <div class="export-bar">
      <div class="export-summary">
        共 {{ selectedSources.length }} 张图片 × {{ selectedPresets.length }} 个尺寸 =
        <strong>{{ selectedSources.length * selectedPresets.length }}</strong> 个 PNG
      </div>
      <button
        type="button"
        class="btn btn-primary export-btn"
        :disabled="exporting || selectedSources.length === 0 || selectedPresets.length === 0"
        @click="handleExport"
      >
        <span v-if="exporting" class="loading-spinner" aria-hidden="true"></span>
        <span v-if="exporting">导出中 {{ progressText }}…</span>
        <span v-else>批量导出下载</span>
      </button>
    </div>
    <p v-if="exportDoneMessage" class="export-done" :class="{ 'has-error': failedCount > 0 }" role="status" aria-live="polite">
      {{ exportDoneMessage }}
    </p>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, reactive, ref, watch } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { getHistory, getHistoryList, getImageUrl, type HistoryRecord } from '../api'
import {
  SIZE_PRESETS,
  loadImage,
  loadImageFromBlob,
  renderToCanvas,
  type BackgroundOption
} from '../utils/canvasExport'
import { useMultiSizeExport, type ExportSource } from '../composables/useMultiSizeExport'
import { normalizeApiError } from '../utils/errors'

type SourceTabKey = 'upload' | 'result' | 'history'

interface CandidateSource {
  key: string
  name: string
  /** 缩略图地址（展示用） */
  thumbUrl: string
  /** 导出用数据：全尺寸 url 或本地文件 */
  data: string | Blob
  removable?: boolean
}

const store = useGeneratorStore()
const { exporting, progressText, failedCount, results, exportAll } = useMultiSizeExport()

/* ---------------- 来源 ---------------- */

const sourceTabs: { key: SourceTabKey; label: string }[] = [
  { key: 'upload', label: '上传图片' },
  { key: 'result', label: '从当前结果' },
  { key: 'history', label: '从历史记录' }
]
const sourceTab = ref<SourceTabKey>('upload')

// 上传的文件（object URL 用于缩略图，卸载时释放）
const uploadedItems = ref<CandidateSource[]>([])
let uploadSeq = 0

function onFilesSelected(e: Event) {
  const input = e.target as HTMLInputElement
  const files = Array.from(input.files || [])
  for (const file of files) {
    const key = `upload-${uploadSeq++}`
    uploadedItems.value.push({
      key,
      name: file.name,
      thumbUrl: URL.createObjectURL(file),
      data: file,
      removable: true
    })
    selectedKeys.add(key)
  }
  input.value = ''
}

function removeUpload(key: string) {
  const idx = uploadedItems.value.findIndex(item => item.key === key)
  if (idx >= 0) {
    URL.revokeObjectURL(uploadedItems.value[idx].thumbUrl)
    uploadedItems.value.splice(idx, 1)
    selectedKeys.delete(key)
    brokenThumbKeys.delete(key)
  }
}

// 当前生成结果（运行时读 store，不修改）
const resultImages = computed<CandidateSource[]>(() =>
  store.images
    .filter(img => img.status === 'done' && img.url)
    .map(img => ({
      key: `result-${img.index}`,
      name: `第${img.index + 1}页`,
      thumbUrl: img.url,
      // 下载/导出用全尺寸原图
      data: img.url.split('?')[0] + '?thumbnail=false'
    }))
)

// 历史记录
const historyRecords = ref<HistoryRecord[]>([])
const selectedRecordId = ref('')
const historyLoading = ref(false)
const historyError = ref('')
const historyImages = ref<CandidateSource[]>([])

async function ensureHistoryList() {
  if (historyRecords.value.length > 0) return
  historyLoading.value = true
  historyError.value = ''
  const res = await getHistoryList(1, 50)
  historyLoading.value = false
  if (res.success) {
    historyRecords.value = res.records.filter(r => r.task_id)
  } else {
    const appError = normalizeApiError(res.error || res.error_message || '获取历史记录失败', '获取历史记录失败')
    historyError.value = `${appError.title}：${appError.suggestion || appError.detail}`
  }
}

async function loadHistoryImages() {
  if (!selectedRecordId.value) return
  historyLoading.value = true
  historyError.value = ''
  historyImages.value = []
  const res = await getHistory(selectedRecordId.value)
  historyLoading.value = false
  if (!res.success || !res.record) {
    const appError = normalizeApiError(res.error || res.error_message || '获取历史记录详情失败', '获取历史记录详情失败')
    historyError.value = `${appError.title}：${appError.suggestion || appError.detail}`
    return
  }
  const taskId = res.record.images.task_id
  const generated = res.record.images.generated || []
  if (!taskId || generated.length === 0) return
  const title = res.record.title || '历史作品'
  historyImages.value = generated.map((filename, idx) => ({
    key: `history-${selectedRecordId.value}-${idx}`,
    name: `${title}_第${idx + 1}页`,
    thumbUrl: getImageUrl(taskId, filename, true),
    data: getImageUrl(taskId, filename, false)
  }))
  // 默认全选新加载的历史图片
  selectedKeys.clear()
  historyImages.value.forEach(item => selectedKeys.add(item.key))
}

function switchSourceTab(key: SourceTabKey) {
  sourceTab.value = key
  selectedKeys.clear()
  if (key === 'history') {
    ensureHistoryList()
    historyImages.value.forEach(item => selectedKeys.add(item.key))
  } else if (key === 'result') {
    resultImages.value.forEach(item => selectedKeys.add(item.key))
  } else {
    uploadedItems.value.forEach(item => selectedKeys.add(item.key))
  }
}

const candidateSources = computed<CandidateSource[]>(() => {
  if (sourceTab.value === 'upload') return uploadedItems.value
  if (sourceTab.value === 'result') return resultImages.value
  return historyImages.value
})

// 选中集合
const selectedKeys = reactive(new Set<string>())

// 缩略图加载失败的项（给出可见提示，不静默）
const brokenThumbKeys = reactive(new Set<string>())

function markThumbBroken(key: string) {
  brokenThumbKeys.add(key)
}

function toggleSource(key: string) {
  if (selectedKeys.has(key)) selectedKeys.delete(key)
  else selectedKeys.add(key)
}

function selectAllSources() {
  candidateSources.value.forEach(item => selectedKeys.add(item.key))
}

const selectedSources = computed<CandidateSource[]>(() =>
  candidateSources.value.filter(item => selectedKeys.has(item.key))
)

/* ---------------- 尺寸与选项 ---------------- */

const selectedPresetIds = reactive(new Set<string>(['xhs-3-4', 'douyin-9-16']))

function togglePreset(id: string) {
  if (selectedPresetIds.has(id)) selectedPresetIds.delete(id)
  else selectedPresetIds.add(id)
}

const selectedPresets = computed(() => SIZE_PRESETS.filter(p => selectedPresetIds.has(p.id)))

const fit = ref<'contain' | 'cover'>('contain')
const bgType = ref<'blur' | 'color'>('blur')
const bgColor = ref('#FFFFFF')

const watermarkText = ref('')
const watermarkOpacity = ref(0.5)

const background = computed<BackgroundOption>(() =>
  bgType.value === 'blur' ? { type: 'blur' } : { type: 'color', color: bgColor.value }
)

const watermark = computed(() =>
  watermarkText.value.trim()
    ? { text: watermarkText.value.trim(), opacity: watermarkOpacity.value }
    : undefined
)

/* ---------------- 预览 ---------------- */

interface PreviewItem {
  presetId: string
  label: string
  dataUrl: string
}

const previews = ref<PreviewItem[]>([])
const previewLoading = ref(false)
const previewError = ref('')
// 已加载图片缓存，避免每次调选项都重新拉图
const imageCache = new Map<string, HTMLImageElement>()
let previewTimer: ReturnType<typeof setTimeout> | null = null
let previewToken = 0

async function refreshPreview() {
  const token = ++previewToken
  const source = selectedSources.value[0]
  const presets = selectedPresets.value
  if (!source || presets.length === 0) {
    previews.value = []
    return
  }
  previewLoading.value = true
  previewError.value = ''
  try {
    let image = imageCache.get(source.key)
    if (!image) {
      image =
        typeof source.data === 'string'
          ? await loadImage(source.data)
          : await loadImageFromBlob(source.data)
      imageCache.set(source.key, image)
    }
    if (token !== previewToken) return

    const items: PreviewItem[] = []
    for (const preset of presets) {
      // 预览按小尺寸渲染，避免大画布卡顿
      const scale = 220 / preset.height
      const canvas = renderToCanvas(image, {
        width: Math.max(1, Math.round(preset.width * scale)),
        height: 220,
        fit: fit.value,
        background: background.value,
        watermark: watermark.value
      })
      items.push({
        presetId: preset.id,
        label: `${preset.label} ${preset.ratio}`,
        dataUrl: canvas.toDataURL('image/png')
      })
    }
    if (token === previewToken) previews.value = items
  } catch (e) {
    if (token === previewToken) {
      previews.value = []
      previewError.value = e instanceof Error ? e.message : '预览生成失败'
    }
  } finally {
    if (token === previewToken) previewLoading.value = false
  }
}

watch(
  [selectedSources, selectedPresets, fit, background, watermark],
  () => {
    if (previewTimer) clearTimeout(previewTimer)
    previewTimer = setTimeout(refreshPreview, 300)
  },
  { deep: true }
)

/* ---------------- 导出 ---------------- */

const exportDoneMessage = ref('')

async function handleExport() {
  if (exporting.value) return
  exportDoneMessage.value = ''
  const sources: ExportSource[] = selectedSources.value.map(item => ({
    name: item.name,
    data: item.data
  }))
  const taskResults = await exportAll(sources, selectedPresets.value, {
    fit: fit.value,
    background: background.value,
    watermark: watermark.value
  })
  if (taskResults.length === 0) return
  const failed = taskResults.filter(r => !r.success)
  exportDoneMessage.value =
    failed.length === 0
      ? `已导出 ${taskResults.length} 个 PNG，请查看浏览器下载。`
      : `完成 ${taskResults.length - failed.length} 个，失败 ${failed.length} 个：${failed[0].error || '未知错误'}`
}

// results 供 useMultiSizeExport 内部记录，模板未直接使用时避免 lint 报未使用
void results

onBeforeUnmount(() => {
  if (previewTimer) clearTimeout(previewTimer)
  uploadedItems.value.forEach(item => URL.revokeObjectURL(item.thumbUrl))
  imageCache.clear()
})
</script>

<style scoped>
.export-container {
  max-width: 960px;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0 0 14px;
}

.section-sub {
  font-size: 12px;
  font-weight: 400;
  color: var(--text-secondary);
}

/* 来源 tabs */
.source-tabs {
  display: flex;
  gap: 8px;
  margin-bottom: 16px;
  flex-wrap: wrap;
}

.source-tab {
  padding: 8px 18px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 14px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.source-tab:hover:not(.active) {
  border-color: var(--border-hover);
  color: var(--text-main);
}

.source-tab.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.upload-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 8px;
  padding: 32px;
  border: 2px dashed var(--border-hover);
  border-radius: var(--radius-md);
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.upload-zone:hover {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-fade);
}

.history-bar {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.history-select {
  flex: 1;
  min-width: 220px;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.history-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.empty-tip {
  color: var(--text-secondary);
  font-size: 14px;
  padding: 8px 0;
}

.error-tip {
  color: var(--color-danger);
  font-size: 13px;
  margin-top: 8px;
}

.loading-tip {
  color: var(--text-secondary);
  font-size: 13px;
}

/* 缩略图选择网格 */
.thumb-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(110px, 1fr));
  gap: 12px;
  margin-top: 16px;
}

.thumb-item {
  position: relative;
  border: 2px solid transparent;
  border-radius: var(--radius-sm);
  overflow: hidden;
  cursor: pointer;
  aspect-ratio: 3/4;
  background: var(--gray-1);
  transition: border-color var(--transition-fast);
}

.thumb-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

.thumb-item.selected {
  border-color: var(--primary);
}

.thumb-check {
  position: absolute;
  top: 6px;
  left: 6px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  background: rgba(255, 255, 255, 0.9);
  color: transparent;
  font-size: 12px;
  display: flex;
  align-items: center;
  justify-content: center;
  border: 1px solid var(--border-hover);
}

.thumb-item.selected .thumb-check {
  background: var(--primary);
  color: white;
  border-color: var(--primary);
}

.thumb-name {
  position: absolute;
  left: 0;
  right: 0;
  bottom: 0;
  padding: 4px 6px;
  font-size: 11px;
  color: white;
  background: linear-gradient(transparent, rgba(0, 0, 0, 0.6));
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.thumb-broken {
  position: absolute;
  inset: 0;
  display: flex;
  align-items: center;
  justify-content: center;
  font-size: 12px;
  color: var(--color-danger);
  background: var(--color-danger-soft);
  text-align: center;
  padding: 4px;
}

.thumb-remove {
  position: absolute;
  top: 4px;
  right: 4px;
  width: 20px;
  height: 20px;
  border-radius: var(--radius-full);
  border: none;
  background: rgba(33, 30, 27, 0.55);
  color: white;
  font-size: 14px;
  line-height: 1;
  cursor: pointer;
  transition: background var(--transition-fast);
}

.thumb-remove:hover {
  background: rgba(33, 30, 27, 0.75);
}

.select-summary {
  margin-top: 12px;
  font-size: 13px;
  color: var(--text-sub);
  display: flex;
  align-items: center;
  gap: 12px;
}

.link-btn {
  border: none;
  background: none;
  color: var(--primary);
  cursor: pointer;
  font-size: 13px;
  padding: 0;
}

/* 尺寸预设 */
.preset-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(150px, 1fr));
  gap: 12px;
}

.preset-item {
  display: flex;
  flex-direction: column;
  gap: 4px;
  padding: 14px 16px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.preset-item:hover {
  border-color: var(--border-hover);
  background: var(--gray-0);
}

.preset-item.selected {
  border-color: var(--primary);
  background: var(--primary-fade);
}

.preset-label {
  font-weight: 600;
  font-size: 14px;
  color: var(--text-main);
}

.preset-ratio {
  font-size: 13px;
  color: var(--primary);
  font-weight: 600;
}

.preset-size {
  font-size: 12px;
  color: var(--text-secondary);
}

/* 选项 */
.option-row {
  display: flex;
  align-items: center;
  gap: 12px;
  flex-wrap: wrap;
}

.option-label {
  font-size: 14px;
  color: var(--text-sub);
}

.radio-item {
  padding: 10px 20px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-full);
  font-size: 14px;
  color: var(--text-sub);
  cursor: pointer;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
  user-select: none;
}

.radio-item:hover:not(.selected) {
  border-color: var(--border-hover);
  color: var(--text-main);
}

.radio-item.small {
  padding: 8px 16px;
  font-size: 13px;
}

.radio-item.selected {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-fade);
  font-weight: 600;
}

.color-input {
  width: 42px;
  height: 36px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  padding: 2px;
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color var(--transition-fast);
}

.color-input:hover {
  border-color: var(--border-hover);
}

.watermark-row {
  align-items: center;
}

.watermark-input {
  flex: 1;
  min-width: 220px;
  padding: 10px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-main);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.watermark-input::placeholder {
  color: var(--text-placeholder);
}

.watermark-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.opacity-label {
  display: flex;
  align-items: center;
  gap: 8px;
  font-size: 13px;
  color: var(--text-sub);
}

/* 预览 */
.preview-row {
  display: flex;
  gap: 16px;
  overflow-x: auto;
  padding-bottom: 8px;
  align-items: flex-end;
}

.preview-item {
  margin: 0;
  flex-shrink: 0;
  text-align: center;
}

.preview-item img {
  height: 220px;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
  display: block;
  background:
    repeating-conic-gradient(#f0f0f0 0% 25%, white 0% 50%) 0 0 / 16px 16px;
}

.preview-item figcaption {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 6px;
}

/* 导出 */
.export-bar {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 16px;
  flex-wrap: wrap;
  margin-top: 8px;
}

.export-summary {
  font-size: 14px;
  color: var(--text-sub);
}

.export-summary strong {
  color: var(--primary);
  font-size: 16px;
}

.export-btn {
  display: inline-flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.loading-spinner {
  width: 14px;
  height: 14px;
  border: 2px solid rgba(255, 255, 255, 0.4);
  border-top-color: white;
  border-radius: var(--radius-full);
  animation: spin 0.8s linear infinite;
}

@keyframes spin {
  to { transform: rotate(360deg); }
}

.export-done {
  margin-top: 12px;
  font-size: 14px;
  color: var(--color-success);
}

.export-done.has-error {
  color: var(--color-danger);
}

/* 移动端 */
@media (max-width: 640px) {
  .page-header {
    flex-direction: column;
    align-items: flex-start;
    gap: 12px;
  }

  .thumb-grid {
    grid-template-columns: repeat(auto-fill, minmax(90px, 1fr));
  }

  .preset-grid {
    grid-template-columns: repeat(2, 1fr);
  }

  .export-bar {
    flex-direction: column;
    align-items: stretch;
  }

  .export-bar .btn {
    width: 100%;
  }
}
</style>
