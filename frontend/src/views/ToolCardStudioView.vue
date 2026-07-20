<template>
  <div class="container studio-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">文字卡片工坊</h1>
        <p class="page-subtitle">
          Canvas 本地渲染纯文字排版卡片，输入即预览、导出即所得，适合金句卡 / 清单卡 / 封面文字卡
        </p>
      </div>
    </div>

    <!-- 批量模式：顶部页签切换各卡 -->
    <div v-if="cards.length > 1" class="batch-bar" role="tablist" aria-label="批量卡片切换">
      <button
        v-for="(card, i) in cards"
        :key="i"
        type="button"
        class="batch-tab"
        :class="{ active: i === activeIndex }"
        role="tab"
        :aria-selected="i === activeIndex"
        @click="activeIndex = i"
      >
        {{ i + 1 }} · {{ card.title.trim() ? card.title.trim().slice(0, 6) : '未命名' }}
      </button>
      <button type="button" class="batch-exit" @click="exitBatchMode">仅保留当前卡</button>
    </div>

    <div class="studio-layout">
      <!-- 左侧控制面板 -->
      <div class="panel">
        <div class="card">
          <h2 class="section-title">模板</h2>
          <div class="pill-row">
            <button
              v-for="tpl in templates"
              :key="tpl.id"
              type="button"
              class="pill"
              :class="{ selected: activeCard.template === tpl.id }"
              :aria-pressed="activeCard.template === tpl.id"
              :title="tpl.hint"
              @click="activeCard.template = tpl.id"
            >
              {{ tpl.label }}
            </button>
          </div>
          <p class="field-hint">{{ activeTemplateHint }}</p>
        </div>

        <div class="card">
          <h2 class="section-title">内容</h2>
          <label class="field-label" for="studio-title">标题</label>
          <input
            id="studio-title"
            v-model="activeCard.title"
            type="text"
            class="text-input"
            maxlength="60"
            placeholder="一句话标题"
          />

          <label class="field-label" for="studio-body">正文（清单卡按行拆条目，金句卡整体为金句）</label>
          <textarea
            id="studio-body"
            v-model="activeCard.body"
            class="text-area"
            rows="5"
            placeholder="每行一句&#10;清单卡会把每行渲染成一个条目"
          ></textarea>

          <label class="field-label" for="studio-tags">标签（逗号 / 空格分隔）</label>
          <input
            id="studio-tags"
            v-model="activeCard.tagsInput"
            type="text"
            class="text-input"
            maxlength="80"
            placeholder="如：干货, 效率 自律"
          />

          <label class="field-label" for="studio-footer">署名 / 页脚（可留空）</label>
          <input
            id="studio-footer"
            v-model="activeCard.footer"
            type="text"
            class="text-input"
            maxlength="30"
            placeholder="如：@我的账号名"
          />
        </div>

        <div class="card">
          <h2 class="section-title">配色主题</h2>
          <div class="theme-grid">
            <button
              v-for="theme in themes"
              :key="theme.id"
              type="button"
              class="theme-swatch"
              :class="{ selected: activeCard.themeId === theme.id }"
              :style="{ background: theme.bg }"
              :aria-pressed="activeCard.themeId === theme.id"
              :title="theme.name"
              @click="activeCard.themeId = theme.id"
            >
              <span class="swatch-accent" :style="{ background: theme.accent }"></span>
              <span class="swatch-name" :style="{ color: pickTextColor(theme.bg) }">
                {{ theme.name }}
              </span>
            </button>
          </div>

          <h2 class="section-title" style="margin-top: 20px;">字号与粗细</h2>
          <div class="pill-row">
            <button
              v-for="option in fontScaleOptions"
              :key="option.id"
              type="button"
              class="pill small"
              :class="{ selected: activeCard.fontScale === option.id }"
              :aria-pressed="activeCard.fontScale === option.id"
              @click="activeCard.fontScale = option.id"
            >
              {{ option.label }}
            </button>
            <span class="pill-divider" aria-hidden="true"></span>
            <button
              type="button"
              class="pill small"
              :class="{ selected: !activeCard.bold }"
              :aria-pressed="!activeCard.bold"
              @click="activeCard.bold = false"
            >
              常规
            </button>
            <button
              type="button"
              class="pill small"
              :class="{ selected: activeCard.bold }"
              :aria-pressed="activeCard.bold"
              @click="activeCard.bold = true"
            >
              加粗
            </button>
          </div>
        </div>

        <div v-if="hasOutline" class="card import-card">
          <h2 class="section-title">从大纲导入</h2>
          <p class="field-hint">
            当前工作区有 {{ store.outline.pages.length }} 页大纲，可一键生成整组卡片：
            第一页用大字报模板，其余用清单卡（每页首行作标题、剩余行作正文）。
          </p>
          <button type="button" class="btn btn-secondary import-btn" @click="importFromOutline">
            从当前大纲导入（{{ store.outline.pages.length }} 页）
          </button>
        </div>
      </div>

      <!-- 右侧实时预览 -->
      <div class="preview-pane">
        <div class="card preview-card">
          <div class="preview-frame">
            <canvas
              ref="previewCanvas"
              :width="CARD_WIDTH"
              :height="CARD_HEIGHT"
              class="preview-canvas"
              role="img"
              :aria-label="`卡片预览：${activeCard.title || '未命名卡片'}`"
            ></canvas>
          </div>
          <div class="export-row">
            <button
              type="button"
              class="btn btn-primary"
              :disabled="exporting"
              @click="exportCurrent"
            >
              {{ exporting ? '导出中…' : '导出 PNG（1080×1440）' }}
            </button>
            <button
              v-if="cards.length > 1"
              type="button"
              class="btn btn-secondary"
              :disabled="exporting"
              @click="exportAllCards"
            >
              导出全部 {{ cards.length }} 张
            </button>
          </div>
          <p
            v-if="exportMessage"
            class="export-message"
            :class="{ 'has-error': exportFailed }"
            role="status"
            aria-live="polite"
          >
            {{ exportMessage }}
          </p>
        </div>
      </div>
    </div>
  </div>
</template>

<script setup lang="ts">
import { computed, onBeforeUnmount, onMounted, ref, watch } from 'vue'
import { useGeneratorStore } from '../stores/generator'
import { useStyleLibrary } from '../composables/useStyleLibrary'
import { canvasToBlob, downloadBlob } from '../utils/canvasExport'
import { normalizeTags, parseOutlinePageToCard, pickTextColor } from '../utils/cardStudio'
import {
  CARD_HEIGHT,
  CARD_WIDTH,
  PRESET_THEMES,
  renderCard,
  type CardRenderConfig,
  type CardTemplateId,
  type CardTheme,
  type FontScaleId
} from '../utils/cardRender'

/** 页面内单张卡片的编辑状态 */
interface CardState {
  template: CardTemplateId
  title: string
  body: string
  tagsInput: string
  footer: string
  themeId: string
  fontScale: FontScaleId
  bold: boolean
}

const store = useGeneratorStore()
const { activeStyle } = useStyleLibrary()

/* ---------------- 模板与主题 ---------------- */

const templates: { id: CardTemplateId; label: string; hint: string }[] = [
  { id: 'poster', label: '大字报', hint: '大号标题居中 + 小副文 + 底部标签行' },
  { id: 'list', label: '清单卡', hint: '顶部标题 + 编号列表条目（正文每行一条）' },
  { id: 'quote', label: '金句卡', hint: '大引号装饰 + 居中金句 + 署名行（金句取正文，为空时用标题）' }
]

const activeTemplateHint = computed(
  () => templates.find(t => t.id === activeCard.value.template)?.hint || ''
)

const ACTIVE_STYLE_THEME_ID = 'active-style'

// 预设 5 组 + 已应用风格（若存在）追加为「当前风格」主题
const themes = computed<CardTheme[]>(() => {
  const list = [...PRESET_THEMES]
  const style = activeStyle.value
  if (style && style.colors.length > 0) {
    list.push({
      id: ACTIVE_STYLE_THEME_ID,
      name: `当前风格·${style.name}`,
      bg: style.colors[0],
      accent: style.colors[1] || style.colors[0]
    })
  }
  return list
})

function resolveTheme(themeId: string): CardTheme {
  return themes.value.find(t => t.id === themeId) || themes.value[0]
}

const fontScaleOptions: { id: FontScaleId; label: string }[] = [
  { id: 'small', label: '小' },
  { id: 'normal', label: '标准' },
  { id: 'large', label: '大' }
]

/* ---------------- 卡片状态（单张 / 批量共用同一数组） ---------------- */

function createDefaultCard(): CardState {
  return {
    template: 'poster',
    title: store.topic || '把想说的话做成卡片',
    body: '不用等 AI 画图\n输入文字即刻成图',
    tagsInput: '文字卡片, 干货',
    footer: '',
    themeId: PRESET_THEMES[0].id,
    fontScale: 'normal',
    bold: true
  }
}

const cards = ref<CardState[]>([createDefaultCard()])
const activeIndex = ref(0)

const activeCard = computed<CardState>(
  () => cards.value[Math.min(activeIndex.value, cards.value.length - 1)]
)

const hasOutline = computed(() => store.outline.pages.length > 0)

/** 从大纲导入：每页一张卡，第一页大字报、其余清单卡，进入批量模式 */
function importFromOutline() {
  const base = activeCard.value
  const imported = store.outline.pages.map((page, i): CardState => {
    const parsed = parseOutlinePageToCard(page.content)
    return {
      template: i === 0 ? 'poster' : 'list',
      title: parsed.title || store.topic || `第 ${i + 1} 页`,
      body: parsed.body,
      tagsInput: base.tagsInput,
      footer: base.footer,
      themeId: base.themeId,
      fontScale: base.fontScale,
      bold: base.bold
    }
  })
  if (imported.length === 0) return
  cards.value = imported
  activeIndex.value = 0
}

/** 退出批量模式：只保留当前正在编辑的卡 */
function exitBatchMode() {
  cards.value = [activeCard.value]
  activeIndex.value = 0
}

/* ---------------- 实时预览（防抖 150ms 重绘） ---------------- */

const previewCanvas = ref<HTMLCanvasElement | null>(null)
let redrawTimer: ReturnType<typeof setTimeout> | null = null

function toRenderConfig(card: CardState): CardRenderConfig {
  return {
    template: card.template,
    title: card.title.trim(),
    body: card.body,
    tags: normalizeTags(card.tagsInput),
    footer: card.footer.trim(),
    theme: resolveTheme(card.themeId),
    fontScale: card.fontScale,
    bold: card.bold
  }
}

function drawPreview() {
  const canvas = previewCanvas.value
  if (!canvas) return
  const ctx = canvas.getContext('2d')
  if (!ctx) return
  renderCard(ctx, toRenderConfig(activeCard.value))
}

function scheduleRedraw() {
  if (redrawTimer) clearTimeout(redrawTimer)
  redrawTimer = setTimeout(drawPreview, 150)
}

watch([cards, activeIndex, themes], scheduleRedraw, { deep: true })

onMounted(drawPreview)

onBeforeUnmount(() => {
  if (redrawTimer) clearTimeout(redrawTimer)
})

/* ---------------- 导出 ---------------- */

const exporting = ref(false)
const exportMessage = ref('')
const exportFailed = ref(false)

/** 用原尺寸离屏 canvas 渲染并转 PNG Blob（与预览同一套绘制逻辑） */
async function renderCardToBlob(card: CardState): Promise<Blob> {
  const canvas = document.createElement('canvas')
  canvas.width = CARD_WIDTH
  canvas.height = CARD_HEIGHT
  const ctx = canvas.getContext('2d')
  if (!ctx) throw new Error('无法创建 canvas 2d 上下文')
  renderCard(ctx, toRenderConfig(card))
  return canvasToBlob(canvas)
}

function delay(ms: number): Promise<void> {
  return new Promise(resolve => setTimeout(resolve, ms))
}

async function exportCurrent() {
  if (exporting.value) return
  exporting.value = true
  exportMessage.value = ''
  exportFailed.value = false
  try {
    const blob = await renderCardToBlob(activeCard.value)
    downloadBlob(blob, `card_${activeIndex.value + 1}.png`)
    exportMessage.value = '已导出 1 张 PNG，请查看浏览器下载。'
  } catch (e) {
    exportFailed.value = true
    exportMessage.value = e instanceof Error ? e.message : '导出失败，请重试'
  } finally {
    exporting.value = false
  }
}

async function exportAllCards() {
  if (exporting.value) return
  exporting.value = true
  exportMessage.value = ''
  exportFailed.value = false
  let done = 0
  try {
    for (let i = 0; i < cards.value.length; i++) {
      const blob = await renderCardToBlob(cards.value[i])
      downloadBlob(blob, `card_${i + 1}.png`)
      done++
      // 逐张下载间隔，避免浏览器拦截连续下载
      if (i < cards.value.length - 1) await delay(300)
    }
    exportMessage.value = `已导出 ${done} 张 PNG，请查看浏览器下载。`
  } catch (e) {
    exportFailed.value = true
    exportMessage.value = `完成 ${done} 张后出错：${e instanceof Error ? e.message : '未知错误'}`
  } finally {
    exporting.value = false
  }
}
</script>

<style scoped>
.studio-container {
  max-width: 1120px;
  padding-bottom: var(--space-8);
}

/* 批量模式页签 */
.batch-bar {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
  margin-bottom: var(--space-4);
}

.batch-tab {
  padding: 8px 16px;
  border-radius: var(--radius-full);
  border: 1px solid var(--border-color);
  background: var(--bg-card);
  color: var(--text-sub);
  font-size: 13px;
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast);
}

.batch-tab:hover:not(.active) {
  border-color: var(--border-hover);
  color: var(--text-main);
}

.batch-tab.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.batch-exit {
  margin-left: auto;
  border: none;
  background: none;
  color: var(--text-secondary);
  font-size: 13px;
  cursor: pointer;
  padding: 4px 8px;
}

.batch-exit:hover {
  color: var(--primary);
}

/* 左右布局：左控制面板 + 右预览，移动端上下堆叠 */
.studio-layout {
  display: grid;
  grid-template-columns: minmax(0, 5fr) minmax(0, 4fr);
  gap: var(--space-5);
  align-items: start;
}

.panel {
  min-width: 0;
}

.section-title {
  font-size: 16px;
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0 0 14px;
}

/* pill 选择器 */
.pill-row {
  display: flex;
  align-items: center;
  gap: var(--space-2);
  flex-wrap: wrap;
}

.pill {
  padding: 10px 20px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-full);
  background: var(--bg-card);
  font-size: 14px;
  color: var(--text-sub);
  cursor: pointer;
  user-select: none;
  transition: border-color var(--transition-fast), color var(--transition-fast),
    background var(--transition-fast);
}

.pill.small {
  padding: 8px 16px;
  font-size: 13px;
}

.pill:hover:not(.selected) {
  border-color: var(--border-hover);
  color: var(--text-main);
}

.pill.selected {
  border-color: var(--primary);
  color: var(--primary);
  background: var(--primary-fade);
  font-weight: 600;
}

.pill-divider {
  width: 1px;
  height: 22px;
  background: var(--border-color);
  margin: 0 var(--space-1);
}

.field-hint {
  margin-top: 10px;
  font-size: 13px;
  color: var(--text-secondary);
  line-height: 1.6;
}

/* 输入控件 */
.field-label {
  display: block;
  font-size: 13px;
  color: var(--text-sub);
  margin: 14px 0 6px;
}

.field-label:first-of-type {
  margin-top: 0;
}

.text-input,
.text-area {
  width: 100%;
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  font-family: var(--font-sans);
  color: var(--text-main);
  background: var(--bg-card);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.text-area {
  resize: vertical;
  min-height: 120px;
  line-height: 1.6;
}

.text-input::placeholder,
.text-area::placeholder {
  color: var(--text-placeholder);
}

.text-input:focus,
.text-area:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

/* 主题色板 */
.theme-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(130px, 1fr));
  gap: var(--space-3);
}

.theme-swatch {
  position: relative;
  display: flex;
  align-items: center;
  gap: 8px;
  padding: 14px 12px;
  border: 2px solid var(--border-color);
  border-radius: var(--radius-md);
  cursor: pointer;
  text-align: left;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.theme-swatch:hover {
  box-shadow: var(--shadow-sm);
  transform: translateY(-1px);
}

.theme-swatch:active {
  transform: translateY(0);
}

.theme-swatch.selected {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.swatch-accent {
  flex-shrink: 0;
  width: 18px;
  height: 18px;
  border-radius: var(--radius-full);
  box-shadow: inset 0 0 0 1px rgba(0, 0, 0, 0.08);
}

.swatch-name {
  font-size: 12px;
  font-weight: 600;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

/* 从大纲导入 */
.import-btn {
  width: 100%;
  margin-top: 12px;
}

/* 预览区 */
.preview-pane {
  position: sticky;
  top: calc(var(--header-height) + var(--space-4));
  min-width: 0;
}

.preview-card {
  margin-bottom: 0;
}

.preview-frame {
  border-radius: var(--radius-md);
  overflow: hidden;
  border: 1px solid var(--border-color);
  box-shadow: var(--shadow-sm);
  /* 固定 3:4，canvas 未绘制完成时占位不跳动 */
  aspect-ratio: 3 / 4;
  background: var(--gray-1);
}

.preview-canvas {
  display: block;
  width: 100%;
  height: 100%;
}

.export-row {
  display: flex;
  gap: var(--space-3);
  flex-wrap: wrap;
  margin-top: var(--space-4);
}

.export-row .btn {
  flex: 1;
  min-width: 0;
  white-space: nowrap;
}

.export-message {
  margin-top: 12px;
  font-size: 13px;
  color: var(--color-success);
}

.export-message.has-error {
  color: var(--color-danger);
}

/* 移动端：上下堆叠，预览取消吸附 */
@media (max-width: 860px) {
  .studio-layout {
    grid-template-columns: 1fr;
  }

  .preview-pane {
    position: static;
    order: -1;
  }

  .preview-frame {
    max-width: 420px;
    margin: 0 auto;
  }
}

/* 尊重系统减少动效偏好 */
@media (prefers-reduced-motion: reduce) {
  .theme-swatch,
  .theme-swatch:hover,
  .pill,
  .batch-tab {
    transition: none;
    transform: none;
  }
}
</style>
