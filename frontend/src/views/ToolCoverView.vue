<template>
  <div class="container cover-container">
    <!-- 页头 -->
    <div class="cover-header">
      <h1 class="page-title">封面 A/B 方向</h1>
      <p class="page-subtitle">输入主题，AI 一次生成多个差异化封面方向，并排对比选出最能打的那一个</p>
    </div>

    <!-- 输入区 -->
    <div class="card cover-form">
      <div class="form-field">
        <label class="form-label" for="cover-topic">主题 <span class="required-mark">*</span></label>
        <input
          id="cover-topic"
          v-model="topic"
          class="form-input"
          type="text"
          placeholder="例如：新手化妆避坑指南"
          maxlength="100"
          :disabled="loading"
          @keyup.enter="handleGenerate"
        />
      </div>

      <div class="form-field">
        <label class="form-label" for="cover-content">补充内容/背景（可选）</label>
        <textarea
          id="cover-content"
          v-model="content"
          class="form-textarea"
          rows="3"
          placeholder="可粘贴笔记正文、卖点、目标人群等，帮助 AI 更贴合内容"
          maxlength="2000"
          :disabled="loading"
        ></textarea>
      </div>

      <button
        type="button"
        class="btn btn-primary generate-btn"
        :disabled="loading || !topic.trim()"
        @click="handleGenerate"
      >
        <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
        {{ loading ? '生成中，约需 10-30 秒…' : directions.length > 0 ? '重新生成方向' : '生成封面方向' }}
      </button>
    </div>

    <!-- 结果对比区 -->
    <div v-if="directions.length > 0" class="directions-grid">
      <div
        v-for="(direction, index) in directions"
        :key="index"
        class="direction-card"
        :class="{ 'direction-card-best': index === bestIndex }"
      >
        <div class="card-top">
          <span class="direction-label">方向 {{ String.fromCharCode(65 + index) }}</span>
          <span v-if="index === bestIndex" class="best-badge">推荐</span>
        </div>

        <!-- 评分 -->
        <div class="score-row">
          <div class="score-value">{{ direction.score }}</div>
          <div class="score-meta">
            <span class="score-caption">预估点击力</span>
            <div class="score-bar">
              <div class="score-bar-fill" :style="{ width: direction.score + '%' }"></div>
            </div>
          </div>
        </div>

        <!-- 文案 -->
        <div class="direction-title">{{ direction.title }}</div>
        <div v-if="direction.subtitle" class="direction-subtitle">{{ direction.subtitle }}</div>
        <div v-if="direction.style" class="style-tag">{{ direction.style }}</div>

        <!-- 视觉概念 -->
        <div class="section-block">
          <div class="section-caption">视觉概念</div>
          <p class="section-text">{{ direction.visual_concept }}</p>
        </div>

        <!-- 点击理由 -->
        <div class="section-block">
          <div class="section-caption">为什么可能更吸引点击</div>
          <p class="section-text">{{ direction.reason }}</p>
        </div>

        <!-- 复制操作 -->
        <div class="card-actions">
          <button
            type="button"
            class="copy-btn"
            :aria-label="`复制方向 ${String.fromCharCode(65 + index)} 的文案`"
            @click="copyText(copyKeyOf(index, 'text'), buildCopyText(direction))"
          >
            {{ copiedKey === copyKeyOf(index, 'text') ? '已复制 ✓' : '复制文案' }}
          </button>
          <button
            type="button"
            class="copy-btn copy-btn-secondary"
            :aria-label="`复制方向 ${String.fromCharCode(65 + index)} 的视觉概念`"
            @click="copyText(copyKeyOf(index, 'visual'), direction.visual_concept)"
          >
            {{ copiedKey === copyKeyOf(index, 'visual') ? '已复制 ✓' : '复制视觉概念' }}
          </button>
        </div>
      </div>
    </div>

    <!-- 空状态 -->
    <div v-else-if="!loading" class="empty-state">
      <p>生成后，各方向将在这里并排展示，方便对比评分与创意角度</p>
    </div>

    <ErrorCard
      v-if="error"
      class="cover-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { generateCoverDirections, type CoverDirection } from '../api/cover'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const topic = ref('')
const content = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const directions = ref<CoverDirection[]>([])

/** 已复制标记（key 形如 "0-text"），短暂显示"已复制"反馈 */
const copiedKey = ref('')
let copiedTimer: ReturnType<typeof setTimeout> | undefined

/** 评分最高的方向下标，用于"推荐"角标 */
const bestIndex = computed(() => {
  if (directions.value.length === 0) return -1
  let best = 0
  directions.value.forEach((d, i) => {
    if (d.score > directions.value[best].score) best = i
  })
  return best
})

function copyKeyOf(index: number, kind: 'text' | 'visual') {
  return `${index}-${kind}`
}

/** 拼装可直接粘贴使用的文案（主标题 + 副标题 + 风格） */
function buildCopyText(direction: CoverDirection) {
  const lines = [direction.title]
  if (direction.subtitle) lines.push(direction.subtitle)
  if (direction.style) lines.push(`风格：${direction.style}`)
  return lines.join('\n')
}

async function copyText(key: string, text: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文降级：用临时 textarea 复制
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedKey.value = key
  if (copiedTimer !== undefined) clearTimeout(copiedTimer)
  copiedTimer = setTimeout(() => {
    copiedKey.value = ''
  }, 1500)
}

async function handleGenerate() {
  if (!topic.value.trim() || loading.value) return

  loading.value = true
  error.value = null

  try {
    const result = await generateCoverDirections(
      topic.value.trim(),
      content.value.trim() || undefined
    )

    if (result.success && result.directions && result.directions.length > 0) {
      directions.value = result.directions
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成封面方向失败',
        '生成封面方向失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成封面方向失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.cover-container {
  max-width: 1100px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.cover-header {
  text-align: center;
  margin-bottom: 28px;
  animation: fadeIn 0.6s ease-out;
}

.page-subtitle {
  font-size: 15px;
  color: var(--text-sub);
  margin-top: 10px;
}

/* 输入表单（基于全局 .card，仅覆盖布局） */
.cover-form {
  padding: 28px 32px;
  margin-bottom: 32px;
}

.form-field {
  margin-bottom: 18px;
}

.form-label {
  display: block;
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
  margin-bottom: 8px;
}

.required-mark {
  color: var(--primary);
}

.form-input,
.form-textarea {
  width: 100%;
  padding: 12px 14px;
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-body, #fff);
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 10px;
  transition: border-color 0.2s ease;
  font-family: inherit;
  box-sizing: border-box;
}

.form-textarea {
  resize: vertical;
  line-height: 1.6;
}

.form-input:focus,
.form-textarea:focus {
  border-color: var(--primary);
  outline: none;
}

.form-input:disabled,
.form-textarea:disabled {
  opacity: 0.6;
  cursor: not-allowed;
}

/* 方向对比网格 */
.directions-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(280px, 1fr));
  gap: 20px;
  animation: fadeIn 0.5s ease-out;
}

.direction-card {
  display: flex;
  flex-direction: column;
  background: var(--bg-card);
  border: 1px solid var(--border-color, #e5e5e5);
  border-radius: 16px;
  padding: 20px;
  transition: box-shadow 0.2s ease, transform 0.2s ease;
}

.direction-card:hover {
  box-shadow: 0 8px 24px rgba(0, 0, 0, 0.08);
  transform: translateY(-2px);
}

.direction-card-best {
  border-color: var(--primary);
  box-shadow: 0 4px 16px rgba(255, 36, 66, 0.12);
}

.card-top {
  display: flex;
  align-items: center;
  justify-content: space-between;
  margin-bottom: 14px;
}

.direction-label {
  font-size: 13px;
  font-weight: 700;
  color: var(--text-sub);
  letter-spacing: 0.5px;
}

.best-badge {
  padding: 2px 10px;
  font-size: 12px;
  font-weight: 600;
  color: var(--primary);
  background: var(--primary-fade);
  border-radius: 100px;
}

/* 评分 */
.score-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 14px;
}

.score-value {
  font-size: 32px;
  font-weight: 800;
  color: var(--primary);
  line-height: 1;
}

.score-meta {
  flex: 1;
  min-width: 0;
}

.score-caption {
  display: block;
  font-size: 12px;
  color: var(--text-sub);
  margin-bottom: 4px;
}

.score-bar {
  height: 6px;
  background: rgba(0, 0, 0, 0.06);
  border-radius: 100px;
  overflow: hidden;
}

.score-bar-fill {
  height: 100%;
  background: var(--primary);
  border-radius: 100px;
  transition: width 0.4s ease;
}

/* 文案 */
.direction-title {
  font-size: 18px;
  font-weight: 700;
  color: var(--text-main);
  line-height: 1.4;
  margin-bottom: 6px;
}

.direction-subtitle {
  font-size: 14px;
  color: var(--text-sub);
  margin-bottom: 10px;
}

.style-tag {
  display: inline-block;
  align-self: flex-start;
  padding: 3px 10px;
  font-size: 12px;
  color: var(--text-sub);
  background: rgba(0, 0, 0, 0.04);
  border-radius: 100px;
  margin-bottom: 12px;
}

.section-block {
  margin-bottom: 12px;
}

.section-caption {
  font-size: 12px;
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: 4px;
}

.section-text {
  font-size: 13px;
  color: var(--text-main);
  line-height: 1.7;
  margin: 0;
  white-space: pre-wrap;
  word-break: break-word;
}

/* 复制操作 */
.card-actions {
  display: flex;
  gap: 10px;
  margin-top: auto;
  padding-top: 12px;
}

.copy-btn {
  flex: 1;
  padding: 9px 12px;
  font-size: 13px;
  font-weight: 600;
  color: #fff;
  background: var(--primary);
  border: none;
  border-radius: 8px;
  cursor: pointer;
  transition: opacity 0.2s ease;
}

.copy-btn:hover {
  opacity: 0.88;
}

.copy-btn-secondary {
  color: var(--primary);
  background: var(--primary-fade);
}

/* 空状态 */
.empty-state {
  text-align: center;
  padding: 48px 20px;
  color: var(--text-sub);
  font-size: 14px;
}

.cover-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s ease-out;
}

/* 移动端 */
@media (max-width: 768px) {
  .cover-form {
    padding: 20px;
  }

  .directions-grid {
    grid-template-columns: 1fr;
  }

  .generate-btn {
    width: 100%;
    justify-content: center;
  }
}

@media (max-width: 640px) {
  .cover-container {
    padding-top: 12px;
  }

  .cover-form {
    padding: 18px 16px;
  }

  .direction-card {
    padding: 16px;
  }
}

/* Animations */
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}
</style>
