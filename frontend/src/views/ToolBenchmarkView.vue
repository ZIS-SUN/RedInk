<template>
  <div class="container benchmark-container">
    <div class="benchmark-header">
      <h1 class="page-title">对标拆解</h1>
      <p class="page-subtitle">粘贴一篇对标爆款，AI 拆解它为什么火，并提炼可复用的套路模板</p>
    </div>

    <!-- 输入区 -->
    <div class="card benchmark-card">
      <label class="field-label" for="benchmark-input">对标内容（标题 + 正文）</label>
      <textarea
        id="benchmark-input"
        v-model="content"
        class="benchmark-textarea"
        rows="9"
        placeholder="把你看到的爆款内容完整粘贴到这里（建议包含标题和正文）…"
      ></textarea>

      <div class="field-block">
        <label class="field-label" for="my-topic-input">
          我的主题（可选）
          <span class="field-hint">填写后，AI 会按同样的套路帮你写一篇原创仿写草稿</span>
        </label>
        <input
          id="my-topic-input"
          v-model="myTopic"
          class="topic-input"
          type="text"
          placeholder="例如：新手如何 30 天学会做短视频"
        />
      </div>

      <div class="submit-row">
        <button
          type="button"
          class="btn btn-primary benchmark-btn"
          :disabled="loading || !content.trim()"
          @click="handleAnalyze"
        >
          <span v-if="loading" class="spinner-sm" aria-hidden="true"></span>
          {{ loading ? '拆解中…' : '开始拆解' }}
        </button>
      </div>
    </div>

    <!-- 拆解结果区 -->
    <div v-if="analysis" class="results-section">
      <div class="card result-card">
        <div class="result-header">
          <span class="section-badge">拆解结果</span>
          <button type="button" class="btn btn-secondary copy-btn" @click="copyAnalysis">
            {{ copiedKey === 'analysis' ? '已复制' : '复制全部' }}
          </button>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🪝 钩子类型</h3>
          <p class="analysis-text">{{ analysis.hook }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">⚡ 开头如何抓人</h3>
          <p class="analysis-text">{{ analysis.opening }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🧱 内容结构</h3>
          <ol class="structure-list">
            <li v-for="(step, index) in analysis.structure" :key="index" class="structure-item">
              {{ step }}
            </li>
          </ol>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">💗 情绪价值</h3>
          <p class="analysis-text">{{ analysis.emotion }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🎯 目标受众</h3>
          <p class="analysis-text">{{ analysis.audience }}</p>
        </div>

        <div class="analysis-item">
          <h3 class="analysis-label">🔥 爆点要素</h3>
          <ul class="viral-list">
            <li v-for="(element, index) in analysis.viral_elements" :key="index" class="viral-item">
              {{ element }}
            </li>
          </ul>
        </div>

        <div class="analysis-item template-item">
          <div class="template-header">
            <h3 class="analysis-label">📋 可复用套路模板</h3>
            <button type="button" class="btn btn-secondary copy-btn" @click="copyTemplate">
              {{ copiedKey === 'template' ? '已复制' : '复制模板' }}
            </button>
          </div>
          <p class="analysis-text template-text">{{ analysis.reusable_template }}</p>
        </div>
      </div>

      <!-- 仿写草稿区 -->
      <div v-if="draft" class="card result-card">
        <div class="result-header">
          <span class="section-badge draft-badge">仿写草稿</span>
          <button type="button" class="btn btn-secondary copy-btn" @click="copyDraft">
            {{ copiedKey === 'draft' ? '已复制' : '复制草稿' }}
          </button>
        </div>
        <p class="draft-text">{{ draft }}</p>
        <p class="draft-tip">草稿按对标套路生成、内容原创，建议在此基础上加入你的真实经历后再发布</p>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <p class="empty-title">还没有拆解结果</p>
      <p class="empty-desc">把一篇你觉得好的爆款内容粘贴到上方，点「开始拆解」，AI 会告诉你它为什么火</p>
    </div>

    <ErrorCard
      v-if="error"
      class="benchmark-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleAnalyze"
    />
  </div>
</template>

<script setup lang="ts">
import { ref } from 'vue'
import { analyzeBenchmark, type BenchmarkAnalysis } from '../api/benchmark'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const content = ref('')
const myTopic = ref('')
const analysis = ref<BenchmarkAnalysis | null>(null)
const draft = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const copiedKey = ref('')

let copyTimer: ReturnType<typeof setTimeout> | undefined

async function handleAnalyze() {
  if (!content.value.trim() || loading.value) return

  loading.value = true
  error.value = null
  analysis.value = null
  draft.value = ''

  try {
    const result = await analyzeBenchmark(
      content.value.trim(),
      myTopic.value.trim() || undefined
    )

    if (result.success && result.analysis) {
      analysis.value = result.analysis
      draft.value = result.draft || ''
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '对标拆解失败', '对标拆解失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '对标拆解失败')
  } finally {
    loading.value = false
  }
}

async function copyText(text: string, key: string) {
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 剪贴板 API 不可用时（如非 https）降级为手动选区复制
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
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => { copiedKey.value = '' }, 1500)
}

function copyAnalysis() {
  if (!analysis.value) return
  const a = analysis.value
  const lines = [
    `【钩子类型】\n${a.hook}`,
    `【开头如何抓人】\n${a.opening}`,
    `【内容结构】\n${a.structure.map((s, i) => `${i + 1}. ${s}`).join('\n')}`,
    `【情绪价值】\n${a.emotion}`,
    `【目标受众】\n${a.audience}`,
    `【爆点要素】\n${a.viral_elements.map(v => `- ${v}`).join('\n')}`,
    `【可复用套路模板】\n${a.reusable_template}`
  ]
  copyText(lines.join('\n\n'), 'analysis')
}

function copyTemplate() {
  if (!analysis.value) return
  copyText(analysis.value.reusable_template, 'template')
}

function copyDraft() {
  if (!draft.value) return
  copyText(draft.value, 'draft')
}
</script>

<style scoped>
.benchmark-container {
  max-width: 860px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.benchmark-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

.benchmark-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.field-hint {
  font-size: 13px;
  font-weight: 400;
  color: var(--text-sub);
  margin-left: 8px;
}

.benchmark-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  resize: vertical;
  min-height: 180px;
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.benchmark-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.benchmark-textarea::placeholder {
  color: var(--text-placeholder);
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.topic-input {
  width: 100%;
  padding: 12px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  color: var(--text-main);
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.topic-input::placeholder {
  color: var(--text-placeholder);
}

.submit-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.benchmark-btn {
  min-width: 180px;
}

/* 结果区 */
.results-section {
  margin-top: var(--space-5);
}

.result-card {
  animation: fadeIn 0.4s var(--ease-out);
  margin-bottom: var(--space-4);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.section-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.draft-badge {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.copy-btn {
  padding: 8px 18px;
  font-size: 14px;
  white-space: nowrap;
}

.analysis-item {
  margin-bottom: var(--space-4);
}

.analysis-item:last-child {
  margin-bottom: 0;
}

.analysis-label {
  font-size: 15px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-2);
}

.analysis-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.structure-list {
  padding-left: 22px;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.structure-item {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
}

.viral-list {
  list-style: none;
  padding: 0;
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.viral-item {
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  padding: 10px 14px;
  background: var(--gray-1);
  border-radius: var(--radius-sm);
}

.template-item {
  padding: var(--space-4);
  background: var(--primary-fade);
  border-radius: var(--radius-md);
}

.template-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-2);
}

.template-header .analysis-label {
  margin-bottom: 0;
}

.template-text {
  font-weight: 500;
}

.draft-text {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
}

.draft-tip {
  margin-top: var(--space-3);
  font-size: 13px;
  color: var(--text-sub);
}

/* 空/初始态 */
.empty-state {
  margin-top: var(--space-6);
  text-align: center;
  padding: 0 16px;
}

.empty-title {
  font-size: 15px;
  font-weight: 600;
  color: var(--text-main);
  margin: 0 0 6px;
}

.empty-desc {
  font-size: 13.5px;
  color: var(--text-sub);
  line-height: 1.7;
  margin: 0;
}

.benchmark-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

@keyframes slideUp {
  from { opacity: 0; transform: translateX(-50%) translateY(20px); }
  to { opacity: 1; transform: translateX(-50%) translateY(0); }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .benchmark-container {
    padding-top: 12px;
  }

  .card {
    padding: var(--space-5);
  }

  .benchmark-btn {
    width: 100%;
  }

  .result-header,
  .template-header {
    flex-wrap: wrap;
  }
}
</style>
