<template>
  <div class="container tool-link-container">
    <div class="page-header">
      <div>
        <h1 class="page-title">链接转图文</h1>
        <p class="page-subtitle">粘贴网页链接或长文，AI 帮你提炼成图文卡大纲</p>
      </div>
    </div>

    <!-- 输入区 -->
    <div class="card input-card">
      <!-- 模式切换 -->
      <div class="mode-tabs" role="tablist">
        <button
          class="mode-tab"
          :class="{ active: mode === 'url' }"
          role="tab"
          :aria-selected="mode === 'url'"
          @click="mode = 'url'"
        >
          网页链接
        </button>
        <button
          class="mode-tab"
          :class="{ active: mode === 'text' }"
          role="tab"
          :aria-selected="mode === 'text'"
          @click="mode = 'text'"
        >
          粘贴长文
        </button>
      </div>

      <div v-if="mode === 'url'" class="input-area">
        <input
          v-model="url"
          type="url"
          class="url-input"
          placeholder="粘贴文章链接，如 https://example.com/article"
          :disabled="loading"
          @keyup.enter="handleGenerate"
        />
        <p class="input-hint">支持公开可访问的文章页面，将自动抓取正文</p>
      </div>

      <div v-else class="input-area">
        <textarea
          v-model="text"
          class="text-input"
          placeholder="粘贴文章、文案或口播稿全文（越完整效果越好）..."
          :disabled="loading"
          rows="10"
        />
        <div class="input-hint text-count">{{ text.length }} 字</div>
      </div>

      <button
        class="btn btn-primary generate-btn"
        :disabled="loading || !canGenerate"
        @click="handleGenerate"
      >
        <span v-if="loading" class="loading-spinner" aria-hidden="true"></span>
        {{ loading ? '生成中…' : '生成图文大纲' }}
      </button>
    </div>

    <!-- 初始态：使用说明占位 -->
    <div v-if="pages.length === 0 && !loading" class="card empty-guide">
      <h2 class="empty-guide-title">如何使用</h2>
      <ol class="empty-guide-steps">
        <li>选择「网页链接」或「粘贴长文」，填入你想转换的内容</li>
        <li>点击「生成图文大纲」，AI 会自动提炼成多页图文卡大纲</li>
        <li>在预览区直接编辑每页文案，确认后发送到创作流程继续生成图片</li>
      </ol>
    </div>

    <!-- 大纲预览（可编辑） -->
    <div v-if="pages.length > 0" class="preview-section">
      <div class="preview-header">
        <h2 class="preview-title">大纲预览</h2>
        <span class="preview-count">共 {{ pages.length }} 页，可直接编辑</span>
      </div>

      <div class="topic-row">
        <label class="topic-label" for="topic-input">主题</label>
        <input
          id="topic-input"
          v-model="topic"
          type="text"
          class="topic-input"
          placeholder="图文卡主题"
        />
      </div>

      <div class="preview-grid">
        <div v-for="(page, idx) in pages" :key="idx" class="card preview-card">
          <div class="preview-card-top">
            <span class="page-number">第 {{ idx + 1 }} 页</span>
            <span class="page-type" :class="page.type">{{ getPageTypeName(page.type) }}</span>
            <button
              class="icon-btn danger"
              title="删除此页"
              aria-label="删除此页"
              @click="removePage(idx)"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="6" x2="6" y2="18"></line><line x1="6" y1="6" x2="18" y2="18"></line></svg>
            </button>
          </div>
          <textarea
            v-model="page.content"
            class="preview-textarea"
            placeholder="在此输入文案..."
          />
        </div>
      </div>

      <div class="send-bar">
        <button class="btn btn-primary send-btn" @click="sendToCreation">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>
          发送到创作流程
        </button>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      class="tool-link-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { computed, ref } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { linkToOutline } from '../api/link'
import type { Page } from '../api/types'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

const router = useRouter()
const store = useGeneratorStore()

const mode = ref<'url' | 'text'>('url')
const url = ref('')
const text = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)

// 生成结果（本地可编辑，确认后才写入 store）
const topic = ref('')
const pages = ref<Page[]>([])

const canGenerate = computed(() =>
  mode.value === 'url' ? !!url.value.trim() : !!text.value.trim()
)

const getPageTypeName = (type: string) => {
  const names = { cover: '封面', content: '内容', summary: '总结' }
  return names[type as keyof typeof names] || '内容'
}

async function handleGenerate() {
  if (!canGenerate.value || loading.value) return

  loading.value = true
  error.value = null

  try {
    const result = await linkToOutline(
      mode.value === 'url'
        ? { url: url.value.trim() }
        : { text: text.value.trim() }
    )

    if (result.success && result.pages && result.pages.length > 0) {
      topic.value = result.topic || ''
      pages.value = result.pages
    } else {
      error.value = normalizeApiError(
        result.error || result.error_message || '生成大纲失败',
        '生成大纲失败'
      )
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '生成大纲失败')
  } finally {
    loading.value = false
  }
}

function removePage(idx: number) {
  pages.value.splice(idx, 1)
  pages.value.forEach((page, i) => {
    page.index = i
  })
}

/**
 * 把主题与大纲写入 generator store，并跳转到大纲编辑页
 */
function sendToCreation() {
  if (pages.value.length === 0) return

  // 保证 index 连续
  pages.value.forEach((page, i) => {
    page.index = i
  })

  const raw = pages.value.map(page => page.content).join('\n\n<page>\n\n')

  store.setTopic(topic.value.trim() || '链接转图文')
  store.setOutline(raw, pages.value)
  // 清空旧的历史记录 ID，让大纲页为本次内容创建新的历史记录
  store.setRecordId(null)

  router.push('/outline')
}
</script>

<style scoped>
.tool-link-container {
  max-width: 1100px;
  margin: 0 auto;
  padding: 20px;
}

.page-header {
  margin-bottom: 24px;
}

/* 输入卡片 */
.input-card {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-xs);
  margin-bottom: 32px;
}

.mode-tabs {
  display: inline-flex;
  background: var(--gray-1);
  border-radius: var(--radius-md);
  padding: 4px;
  margin-bottom: 16px;
}

.mode-tab {
  border: none;
  background: transparent;
  padding: 8px 20px;
  border-radius: var(--radius-sm);
  font-size: 14px;
  font-weight: 600;
  font-family: inherit;
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast);
}

.mode-tab:hover:not(.active) {
  color: var(--text-main);
}

.mode-tab.active {
  background: var(--bg-card);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
}

.input-area {
  margin-bottom: 16px;
}

.url-input,
.text-input {
  width: 100%;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 12px 14px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
  box-sizing: border-box;
}

.url-input::placeholder,
.text-input::placeholder {
  color: var(--text-placeholder);
}

.text-input {
  resize: vertical;
  min-height: 200px;
  line-height: 1.7;
}

.url-input:focus,
.text-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.input-hint {
  font-size: 12px;
  color: var(--text-secondary);
  margin-top: 8px;
}

.text-count {
  text-align: right;
}

.generate-btn {
  width: 100%;
  padding: 12px;
  font-size: 15px;
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 8px;
}

.generate-btn:disabled {
  opacity: 0.6;
  cursor: not-allowed;
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

/* 初始态使用说明 */
.empty-guide {
  background: var(--bg-card);
  border-radius: var(--radius-lg);
  padding: 24px;
  box-shadow: var(--shadow-xs);
}

.empty-guide-title {
  font-size: 16px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0 0 12px;
}

.empty-guide-steps {
  margin: 0;
  padding-left: 20px;
  font-size: 14px;
  color: var(--text-sub);
  line-height: 2;
}

/* 预览区 */
.preview-section {
  animation: fadeIn 0.4s ease-out;
}

.preview-header {
  display: flex;
  align-items: baseline;
  gap: 12px;
  margin-bottom: 16px;
}

.preview-title {
  font-size: 20px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin: 0;
}

.preview-count {
  font-size: 13px;
  color: var(--text-secondary);
}

.topic-row {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: 20px;
}

.topic-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-sub);
  flex-shrink: 0;
}

.topic-input {
  flex: 1;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  padding: 10px 12px;
  font-size: 15px;
  font-family: inherit;
  color: var(--text-main);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.topic-input:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.preview-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
  gap: 20px;
  margin-bottom: 24px;
}

.preview-card {
  display: flex;
  flex-direction: column;
  padding: 16px;
  border-radius: var(--radius-lg);
  background: var(--bg-card);
  box-shadow: var(--shadow-xs);
  min-height: 280px;
}

.preview-card-top {
  display: flex;
  align-items: center;
  gap: 8px;
  margin-bottom: 12px;
  padding-bottom: 8px;
  border-bottom: 1px solid var(--border-color);
}

.page-number {
  font-size: 14px;
  font-weight: 700;
  color: var(--text-secondary);
}

.page-type {
  font-size: 11px;
  padding: 2px 6px;
  border-radius: var(--radius-xs);
  font-weight: 600;
}

.page-type.cover { color: var(--color-danger); background: var(--color-danger-soft); }
.page-type.content { color: var(--text-secondary); background: var(--gray-1); }
.page-type.summary { color: var(--color-success); background: var(--color-success-soft); }

.icon-btn {
  background: none;
  border: none;
  cursor: pointer;
  color: var(--text-secondary);
  padding: 2px;
  margin-left: auto;
  transition: color var(--transition-fast);
}

.icon-btn.danger:hover { color: var(--color-danger); }

.preview-textarea {
  flex: 1;
  width: 100%;
  border: none;
  background: transparent;
  padding: 0;
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  resize: none;
  font-family: inherit;
}

.preview-textarea:focus {
  outline: none;
}

.send-bar {
  display: flex;
  justify-content: center;
  padding: 8px 0 40px;
}

.send-btn {
  padding: 12px 40px;
  font-size: 15px;
  display: flex;
  align-items: center;
}

.tool-link-error {
  position: fixed;
  bottom: 32px;
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
}

@keyframes fadeIn {
  from { opacity: 0; transform: translateY(10px); }
  to { opacity: 1; transform: translateY(0); }
}

/* 移动端适配 */
@media (max-width: 640px) {
  .tool-link-container {
    padding: 12px;
  }

  .input-card {
    padding: 16px;
  }

  .mode-tab {
    padding: 8px 14px;
  }

  .preview-grid {
    grid-template-columns: 1fr;
    gap: 14px;
  }

  .preview-card {
    min-height: 200px;
  }

  .topic-row {
    flex-direction: column;
    align-items: stretch;
    gap: 6px;
  }

  .send-btn {
    width: 100%;
    justify-content: center;
  }
}
</style>
