<template>
  <Teleport to="body">
    <div class="ocr-modal-overlay" @click.self="handleClose">
      <div class="ocr-modal" role="dialog" aria-modal="true" aria-label="截图导入表现数据">
        <div class="ocr-modal-head">
          <h3>截图导入</h3>
          <button type="button" class="close-btn" aria-label="关闭" @click="handleClose">×</button>
        </div>

        <!-- 平台候选（选图与预览两步共用，需常驻渲染） -->
        <datalist id="ocr-platform-presets">
          <option value="小红书"></option>
          <option value="抖音"></option>
          <option value="B站"></option>
          <option value="视频号"></option>
          <option value="快手"></option>
          <option value="公众号"></option>
        </datalist>

        <div class="ocr-modal-body">
          <!-- 第一步：选择截图 -->
          <template v-if="step === 'pick'">
            <p class="ocr-hint">
              截图小红书创作中心 / 抖音创作者后台的数据页（最多 3 张），AI 自动识别曝光、点赞等数据。
              可点击下方区域选择图片，或直接 <kbd>Ctrl</kbd>+<kbd>V</kbd> 粘贴截图。
            </p>

            <div class="form-field">
              <label for="ocr-platform">发布平台（应用到所有识别行）<span class="required">*</span></label>
              <input
                id="ocr-platform"
                v-model="platform"
                class="input"
                type="text"
                maxlength="30"
                placeholder="如：小红书 / 抖音"
                list="ocr-platform-presets"
              />
            </div>

            <button
              type="button"
              class="ocr-drop-zone"
              :disabled="images.length >= MAX_IMAGES"
              @click="fileInput?.click()"
            >
              <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>
              <span v-if="images.length === 0">点击选择截图，或直接粘贴（{{ MAX_IMAGES }} 张以内，单张 ≤10MB）</span>
              <span v-else>已选 {{ images.length }}/{{ MAX_IMAGES }} 张，可继续添加或粘贴</span>
            </button>
            <input
              ref="fileInput"
              type="file"
              accept="image/*"
              multiple
              style="display: none;"
              @change="onFilePicked"
            />

            <ul v-if="images.length" class="ocr-thumb-list">
              <li v-for="(img, i) in images" :key="i" class="ocr-thumb">
                <img :src="img.dataUrl" :alt="img.name || `截图 ${i + 1}`" />
                <span class="ocr-thumb-name">{{ img.name || `截图 ${i + 1}` }}</span>
                <button type="button" class="ocr-thumb-remove" :aria-label="`移除第 ${i + 1} 张截图`" @click="images.splice(i, 1)">×</button>
              </li>
            </ul>

            <p v-if="errorText" class="form-error" role="alert">{{ errorText }}</p>
          </template>

          <!-- 第二步：识别中 -->
          <div v-else-if="step === 'loading'" class="ocr-loading" role="status" aria-live="polite">
            <div class="spinner"></div>
            <div>
              <p class="ocr-loading-main">AI 识别中，约 10-30 秒…</p>
              <p class="ocr-loading-sub">正在把 {{ images.length }} 张截图交给你配置的文本模型识别</p>
            </div>
          </div>

          <!-- 第三步：可编辑预览 -->
          <template v-else-if="step === 'preview'">
            <div class="ocr-preview-summary">
              <span>识别出 <strong>{{ rows.length }}</strong> 条记录，请核对并按需修改（空白表示未识别到）</span>
            </div>

            <div class="records-table-wrap ocr-preview-wrap">
              <table class="ocr-preview-table">
                <thead>
                  <tr>
                    <th class="col-title">标题 <span class="required">*</span></th>
                    <th class="col-date">发布日期</th>
                    <th>曝光</th>
                    <th>点赞</th>
                    <th>收藏</th>
                    <th>评论</th>
                    <th>转发</th>
                    <th>涨粉</th>
                    <th class="col-op"></th>
                  </tr>
                </thead>
                <tbody>
                  <tr v-for="(row, i) in rows" :key="i">
                    <td class="col-title"><input v-model="row.title" class="cell-input" type="text" maxlength="100" :aria-label="`第 ${i + 1} 行标题`" /></td>
                    <td class="col-date"><input v-model="row.publish_date" class="cell-input" type="date" :aria-label="`第 ${i + 1} 行发布日期`" /></td>
                    <td><input v-model="row.views" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行曝光`" /></td>
                    <td><input v-model="row.likes" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行点赞`" /></td>
                    <td><input v-model="row.collects" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行收藏`" /></td>
                    <td><input v-model="row.comments" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行评论`" /></td>
                    <td><input v-model="row.shares" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行转发`" /></td>
                    <td><input v-model="row.followers_gained" class="cell-input num" type="text" inputmode="numeric" placeholder="—" :aria-label="`第 ${i + 1} 行涨粉`" /></td>
                    <td class="col-op">
                      <button type="button" class="ocr-row-remove" :aria-label="`删除第 ${i + 1} 行`" @click="rows.splice(i, 1)">×</button>
                    </td>
                  </tr>
                </tbody>
              </table>
            </div>

            <div class="form-field ocr-platform-inline">
              <label for="ocr-platform-confirm">发布平台（应用到所有行）<span class="required">*</span></label>
              <input
                id="ocr-platform-confirm"
                v-model="platform"
                class="input"
                type="text"
                maxlength="30"
                placeholder="如：小红书 / 抖音"
                list="ocr-platform-presets"
              />
            </div>

            <p v-if="errorText" class="form-error" role="alert">{{ errorText }}</p>
          </template>

          <!-- 第四步：导入结果 -->
          <div v-else-if="step === 'done' && importResult" class="ocr-result" role="status">
            <p class="ocr-result-main">成功导入 {{ importResult.created }} 条记录</p>
            <template v-if="importResult.failed.length">
              <p class="ocr-result-sub">以下 {{ importResult.failed.length }} 条被后端拒绝，未导入：</p>
              <ul class="ocr-result-errors">
                <li v-for="f in importResult.failed" :key="f.index">第 {{ f.index + 1 }} 条：{{ f.error }}</li>
              </ul>
            </template>
          </div>
        </div>

        <div class="ocr-modal-foot">
          <template v-if="step === 'pick'">
            <button type="button" class="btn" @click="handleClose">取消</button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="images.length === 0"
              @click="handleRecognize"
            >
              开始识别{{ images.length ? `（${images.length} 张）` : '' }}
            </button>
          </template>
          <template v-else-if="step === 'loading'">
            <button type="button" class="btn" disabled>识别中…</button>
          </template>
          <template v-else-if="step === 'preview'">
            <button type="button" class="btn" @click="backToPick">重新选图</button>
            <button
              type="button"
              class="btn btn-primary"
              :disabled="importing || rows.length === 0"
              @click="handleConfirm"
            >
              {{ importing ? '导入中...' : `确认导入 ${rows.length} 条` }}
            </button>
          </template>
          <template v-else>
            <button type="button" class="btn btn-primary" @click="emit('close')">完成</button>
          </template>
        </div>
      </div>
    </div>
  </Teleport>
</template>

<script setup lang="ts">
import { onBeforeUnmount, onMounted, ref } from 'vue'
import {
  batchCreateAnalyticsRecords,
  ocrImportAnalyticsRecords,
  type AnalyticsBatchFailure
} from '../../api/analytics'
import { buildOcrImportPayload, toEditableRows, type EditableOcrRow } from './ocrRows'

/**
 * 截图导入弹窗（B3）：上传/粘贴创作者后台数据截图 →
 * AI 多模态识别 → 可编辑预览表格 → 走既有批量创建接口入库。
 *
 * 与手动录入、CSV 批量导入并列的第三种录入方式；
 * 识别失败（模型不支持视觉等）时展示后端的结构化错误提示，引导改用手动录入。
 */

const emit = defineEmits<{
  close: []
  /** 成功入库后触发（携带成功条数），父组件刷新列表与统计 */
  imported: [created: number]
}>()

const MAX_IMAGES = 3
const MAX_IMAGE_BYTES = 10 * 1024 * 1024

type Step = 'pick' | 'loading' | 'preview' | 'done'

const step = ref<Step>('pick')
const fileInput = ref<HTMLInputElement | null>(null)
const images = ref<Array<{ name: string; dataUrl: string }>>([])
const platform = ref('小红书')
const rows = ref<EditableOcrRow[]>([])
const errorText = ref('')
const importing = ref(false)
const importResult = ref<{ created: number; failed: AnalyticsBatchFailure[] } | null>(null)

/** 读取单个文件为 data URL */
function readFileAsDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader()
    reader.onload = () => resolve(String(reader.result))
    reader.onerror = () => reject(reader.error)
    reader.readAsDataURL(file)
  })
}

/** 追加图片（上传与粘贴共用），带张数/大小/类型校验 */
async function addFiles(files: File[]) {
  errorText.value = ''
  for (const file of files) {
    if (images.value.length >= MAX_IMAGES) {
      errorText.value = `一次最多识别 ${MAX_IMAGES} 张截图，多余的已忽略`
      return
    }
    if (!file.type.startsWith('image/')) {
      errorText.value = `「${file.name || '剪贴板内容'}」不是图片文件，已跳过`
      continue
    }
    if (file.size > MAX_IMAGE_BYTES) {
      errorText.value = `「${file.name || '截图'}」超过单张 10MB 上限，已跳过`
      continue
    }
    try {
      const dataUrl = await readFileAsDataUrl(file)
      images.value.push({ name: file.name, dataUrl })
    } catch {
      errorText.value = '读取图片失败，请重试'
    }
  }
}

function onFilePicked(event: Event) {
  const input = event.target as HTMLInputElement
  addFiles(Array.from(input.files ?? []))
  // 清空 value，允许重复选择同一文件
  input.value = ''
}

/** 粘贴截图（仅在选图步骤生效） */
function onPaste(event: ClipboardEvent) {
  if (step.value !== 'pick') return
  const files = Array.from(event.clipboardData?.items ?? [])
    .filter(item => item.kind === 'file' && item.type.startsWith('image/'))
    .map(item => item.getAsFile())
    .filter((file): file is File => file !== null)
  if (files.length) {
    event.preventDefault()
    addFiles(files)
  }
}

onMounted(() => window.addEventListener('paste', onPaste))
onBeforeUnmount(() => window.removeEventListener('paste', onPaste))

/** 调 OCR 接口识别 */
async function handleRecognize() {
  if (images.value.length === 0 || step.value === 'loading') return
  errorText.value = ''
  step.value = 'loading'

  const res = await ocrImportAnalyticsRecords(images.value.map(img => img.dataUrl))

  // 识别期间用户可能已关闭弹窗（组件保留在内存但已不可见），丢弃迟到的结果
  if (step.value !== 'loading') return

  if (res.success && res.rows) {
    if (res.rows.length === 0) {
      step.value = 'pick'
      errorText.value = '未能从截图中识别出数据行，请确认截图包含作品数据列表，或改用手动录入'
      return
    }
    rows.value = toEditableRows(res.rows)
    step.value = 'preview'
  } else {
    step.value = 'pick'
    errorText.value = res.error_message || '截图识别失败，请改用手动录入'
  }
}

function backToPick() {
  errorText.value = ''
  step.value = 'pick'
}

/** 确认导入：预览行 → 批量创建接口 */
async function handleConfirm() {
  if (importing.value) return
  errorText.value = ''

  const { records, errors } = buildOcrImportPayload(rows.value, platform.value)
  if (errors.length) {
    errorText.value = errors.slice(0, 3).join('；')
    return
  }

  importing.value = true
  const res = await batchCreateAnalyticsRecords(records)
  importing.value = false

  if (res.success) {
    importResult.value = { created: res.created ?? 0, failed: res.failed ?? [] }
    step.value = 'done'
    emit('imported', res.created ?? 0)
  } else {
    errorText.value = res.error_message || '导入失败，请重试'
  }
}

/** 关闭弹窗（识别中也允许关闭：请求无法中断，但结果会被丢弃） */
function handleClose() {
  emit('close')
}
</script>

<style scoped>
/* 弹窗骨架（与数据复盘页的录入/批量导入弹窗视觉一致） */
.ocr-modal-overlay {
  position: fixed;
  inset: 0;
  background: rgba(33, 30, 27, 0.55);
  -webkit-backdrop-filter: blur(8px);
  backdrop-filter: blur(8px);
  z-index: 1000;
  display: flex;
  align-items: center;
  justify-content: center;
  padding: 20px;
  animation: ocr-overlay-in 150ms var(--ease-out);
}

.ocr-modal {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  width: 100%;
  max-width: 760px;
  max-height: 90vh;
  display: flex;
  flex-direction: column;
  box-shadow: var(--shadow-lg);
  animation: ocr-modal-in 200ms var(--ease-out);
}

@keyframes ocr-overlay-in {
  from { opacity: 0; }
  to { opacity: 1; }
}

@keyframes ocr-modal-in {
  from { opacity: 0; transform: translateY(12px) scale(0.98); }
  to { opacity: 1; transform: translateY(0) scale(1); }
}

@media (prefers-reduced-motion: reduce) {
  .ocr-modal-overlay,
  .ocr-modal {
    animation: none;
  }
}

.ocr-modal-head {
  display: flex;
  justify-content: space-between;
  align-items: center;
  padding: 20px 24px 12px;
}

.ocr-modal-head h3 {
  margin: 0;
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.close-btn {
  border: none;
  background: transparent;
  font-size: 22px;
  line-height: 1;
  color: var(--text-secondary);
  cursor: pointer;
  border-radius: var(--radius-sm);
  transition: color var(--transition-fast), background var(--transition-fast);
}

.close-btn:hover {
  color: var(--text-main);
  background: var(--gray-2);
}

.ocr-modal-body {
  padding: 8px 24px;
  overflow-y: auto;
  display: flex;
  flex-direction: column;
  gap: 14px;
}

.ocr-modal-foot {
  display: flex;
  justify-content: flex-end;
  gap: 12px;
  padding: 16px 24px 20px;
  border-top: 1px solid var(--border-color);
  margin-top: 8px;
}

.ocr-modal-foot .btn {
  border: 1px solid var(--border-color);
}

.ocr-modal-foot .btn-primary {
  border: none;
}

/* 提示与表单 */
.ocr-hint {
  margin: 0;
  font-size: 13px;
  line-height: 1.6;
  color: var(--text-sub);
}

.ocr-hint kbd {
  padding: 1px 5px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-xs);
  background: var(--gray-1);
  font-size: 11px;
  font-family: inherit;
}

.form-field {
  display: flex;
  flex-direction: column;
  gap: 6px;
}

.form-field label {
  font-size: 13px;
  font-weight: 600;
  color: var(--text-main);
}

.required {
  color: var(--color-danger);
}

.form-error {
  margin: 0;
  font-size: 13px;
  color: var(--color-danger);
}

/* 选图区 */
.ocr-drop-zone {
  display: flex;
  flex-direction: column;
  align-items: center;
  justify-content: center;
  gap: 8px;
  padding: 26px 16px;
  border: 1.5px dashed var(--border-color);
  border-radius: var(--radius-md);
  background: var(--gray-0);
  color: var(--text-sub);
  font-size: 13px;
  cursor: pointer;
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.ocr-drop-zone:hover:not(:disabled) {
  border-color: var(--primary);
  background: var(--primary-light);
  color: var(--primary);
}

.ocr-drop-zone:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

.ocr-thumb-list {
  list-style: none;
  margin: 0;
  padding: 0;
  display: flex;
  gap: 10px;
  flex-wrap: wrap;
}

.ocr-thumb {
  position: relative;
  width: 132px;
  display: flex;
  flex-direction: column;
  gap: 4px;
}

.ocr-thumb img {
  width: 100%;
  height: 88px;
  object-fit: cover;
  border-radius: var(--radius-sm);
  border: 1px solid var(--border-color);
}

.ocr-thumb-name {
  font-size: 11px;
  color: var(--text-sub);
  overflow: hidden;
  text-overflow: ellipsis;
  white-space: nowrap;
}

.ocr-thumb-remove {
  position: absolute;
  top: -6px;
  right: -6px;
  width: 20px;
  height: 20px;
  border: none;
  border-radius: var(--radius-full);
  background: var(--text-main);
  color: var(--bg-card);
  font-size: 13px;
  line-height: 1;
  cursor: pointer;
}

/* 识别中 */
.ocr-loading {
  display: flex;
  align-items: center;
  gap: 14px;
  padding: 28px 4px;
}

.ocr-loading-main {
  margin: 0;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.ocr-loading-sub {
  margin: 4px 0 0;
  font-size: 12.5px;
  color: var(--text-sub);
}

/* 可编辑预览表格 */
.ocr-preview-summary {
  font-size: 13px;
  color: var(--text-main);
}

.records-table-wrap {
  overflow-x: auto;
  -webkit-overflow-scrolling: touch;
}

.ocr-preview-wrap {
  border: 1px solid var(--gray-2);
  border-radius: var(--radius-sm);
  max-height: 300px;
  overflow-y: auto;
}

.ocr-preview-table {
  width: 100%;
  border-collapse: collapse;
  font-size: 13px;
  min-width: 720px;
}

.ocr-preview-table th,
.ocr-preview-table td {
  padding: 6px 6px;
  text-align: left;
  border-bottom: 1px solid var(--gray-2);
  white-space: nowrap;
}

.ocr-preview-table th {
  font-weight: 600;
  color: var(--text-secondary);
  font-size: 12px;
  background: var(--gray-0);
  position: sticky;
  top: 0;
  z-index: 1;
}

.ocr-preview-table .col-title {
  min-width: 180px;
}

.ocr-preview-table .col-date {
  min-width: 130px;
}

.ocr-preview-table .col-op {
  width: 30px;
}

.cell-input {
  width: 100%;
  min-width: 56px;
  box-sizing: border-box;
  padding: 6px 8px;
  border: 1px solid transparent;
  border-radius: var(--radius-xs);
  background: transparent;
  font-size: 13px;
  font-family: inherit;
  color: var(--text-main);
  transition: border-color var(--transition-fast), background var(--transition-fast);
}

.cell-input.num {
  text-align: right;
  font-variant-numeric: tabular-nums;
}

.cell-input:hover {
  background: var(--gray-1);
}

.cell-input:focus {
  outline: none;
  border-color: var(--primary);
  background: var(--bg-card);
}

.ocr-row-remove {
  border: none;
  background: transparent;
  color: var(--text-secondary);
  font-size: 15px;
  line-height: 1;
  cursor: pointer;
  border-radius: var(--radius-xs);
  padding: 2px 6px;
}

.ocr-row-remove:hover {
  color: var(--color-danger);
  background: var(--color-danger-soft);
}

.ocr-platform-inline {
  max-width: 300px;
}

/* 导入结果 */
.ocr-result {
  padding: 8px 0;
}

.ocr-result-main {
  margin: 0 0 10px;
  font-size: 15px;
  font-weight: 700;
  color: var(--color-success);
}

.ocr-result-sub {
  margin: 0 0 8px;
  font-size: 13px;
  color: var(--text-main);
}

.ocr-result-errors {
  margin: 0;
  padding: 10px 12px 10px 28px;
  font-size: 13px;
  line-height: 1.7;
  color: var(--color-warning);
  background: var(--color-warning-soft);
  border-radius: var(--radius-sm);
  max-height: 120px;
  overflow-y: auto;
}

/* 移动端 */
@media (max-width: 640px) {
  .ocr-modal-overlay {
    padding: 0;
    align-items: flex-end;
  }

  .ocr-modal {
    max-width: none;
    max-height: 92vh;
    border-radius: var(--radius-lg) var(--radius-lg) 0 0;
  }
}
</style>
