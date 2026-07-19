<template>
  <div class="container rewrite-container">
    <div class="rewrite-header">
      <h1 class="page-title">多平台文案改写</h1>
      <p class="page-subtitle">粘贴一段文案，AI 帮你一键改写成各平台的原生风格</p>
    </div>

    <!-- 输入区 -->
    <div class="card rewrite-card">
      <label class="field-label" for="rewrite-input">原始文案 / 主题</label>
      <textarea
        id="rewrite-input"
        v-model="content"
        class="rewrite-textarea"
        rows="7"
        placeholder="粘贴你的文案，或直接输入一个主题…"
      ></textarea>

      <div class="field-row">
        <label class="field-label" for="source-select">源平台（可选）</label>
        <select id="source-select" v-model="sourcePlatform" class="source-select">
          <option value="">通用 / 不指定</option>
          <option v-for="p in platforms" :key="p.code" :value="p.code">{{ p.label }}</option>
        </select>
      </div>

      <div class="field-row">
        <label class="field-label" for="brand-select">品牌人设（可选）</label>
        <select
          v-if="brands.length > 0"
          id="brand-select"
          v-model="selectedBrandId"
          class="source-select"
        >
          <option value="">不使用品牌人设</option>
          <option v-for="b in brands" :key="b.id" :value="b.id">
            {{ b.name }}{{ b.id === activeBrandId ? '（当前启用）' : '' }}
          </option>
        </select>
        <span v-else-if="brandsLoaded" class="brand-empty-hint">
          还没有品牌档案，<RouterLink to="/tools/brand" class="brand-link">去创建</RouterLink>
        </span>
      </div>

      <div class="field-block">
        <span class="field-label">目标平台（可多选）</span>
        <div class="platform-chips">
          <button
            v-for="p in platforms"
            :key="p.code"
            type="button"
            class="platform-chip"
            :class="{ active: targetPlatforms.includes(p.code) }"
            @click="toggleTarget(p.code)"
          >
            {{ p.label }}
          </button>
        </div>
      </div>

      <div class="submit-row">
        <button
          type="button"
          class="btn btn-primary rewrite-btn"
          :disabled="loading || !content.trim() || targetPlatforms.length === 0"
          @click="handleRewrite"
        >
          <span v-if="loading" class="spinner-sm"></span>
          {{ loading ? '改写中…' : '开始改写' }}
        </button>
      </div>
    </div>

    <!-- 结果区 -->
    <div v-if="results.length > 0" class="results-section">
      <div v-for="item in results" :key="item.platform" class="card result-card">
        <div class="result-header">
          <span class="platform-badge">{{ platformLabel(item.platform) }}</span>
          <button
            type="button"
            class="btn btn-secondary copy-btn"
            :aria-label="`复制${platformLabel(item.platform)}文案`"
            @click="copyResult(item)"
          >
            {{ copiedPlatform === item.platform ? '已复制 ✓' : '一键复制' }}
          </button>
        </div>
        <h3 class="result-title">{{ item.title }}</h3>
        <p class="result-content">{{ item.content }}</p>
        <div v-if="item.tags.length > 0" class="result-tags">
          <span v-for="tag in item.tags" :key="tag" class="tag result-tag">#{{ tag }}</span>
        </div>
      </div>
    </div>

    <!-- 空/初始态 -->
    <div v-else-if="!loading" class="empty-state">
      <p>粘贴一段文案、勾选目标平台，点击「开始改写」，各平台版本会在这里逐一展示</p>
    </div>

    <ErrorCard
      v-if="error"
      class="rewrite-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleRewrite"
    />
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { rewriteCopy, type RewritePlatform, type RewriteResult } from '../api/rewrite'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'
import ErrorCard from '../components/common/ErrorCard.vue'

interface PlatformOption {
  code: RewritePlatform
  label: string
}

const platforms: PlatformOption[] = [
  { code: 'xiaohongshu', label: '小红书' },
  { code: 'douyin', label: '抖音口播' },
  { code: 'wechat', label: '公众号' },
  { code: 'bilibili', label: 'B站' },
  { code: 'weibo', label: '微博' }
]

const content = ref('')
const sourcePlatform = ref<RewritePlatform | ''>('')
const targetPlatforms = ref<RewritePlatform[]>([])
const results = ref<RewriteResult[]>([])
const loading = ref(false)
const error = ref<AppError | null>(null)
const copiedPlatform = ref('')

// 品牌人设选择：'' 表示不使用，默认选中当前启用档案
const brands = ref<BrandKit[]>([])
const activeBrandId = ref<string | null>(null)
const selectedBrandId = ref('')
const brandsLoaded = ref(false)

onMounted(async () => {
  const res = await getBrandList()
  if (res.success) {
    brands.value = res.brands
    activeBrandId.value = res.active_id
    if (res.active_id && res.brands.some(b => b.id === res.active_id)) {
      selectedBrandId.value = res.active_id
    }
  }
  brandsLoaded.value = true
})

function toggleTarget(code: RewritePlatform) {
  const index = targetPlatforms.value.indexOf(code)
  if (index === -1) {
    targetPlatforms.value.push(code)
  } else {
    targetPlatforms.value.splice(index, 1)
  }
}

function platformLabel(code: string): string {
  return platforms.find(p => p.code === code)?.label || code
}

async function handleRewrite() {
  if (loading.value || !content.value.trim() || targetPlatforms.value.length === 0) return

  loading.value = true
  error.value = null
  results.value = []

  try {
    const result = await rewriteCopy(
      content.value.trim(),
      sourcePlatform.value,
      targetPlatforms.value,
      selectedBrandId.value || undefined
    )

    if (result.success && result.results) {
      results.value = result.results
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '文案改写失败', '文案改写失败')
    }
  } catch (err: unknown) {
    error.value = normalizeApiError(err, '文案改写失败')
  } finally {
    loading.value = false
  }
}

let copyTimer: ReturnType<typeof setTimeout> | undefined

async function copyResult(item: RewriteResult) {
  const parts = [item.title, item.content]
  if (item.tags.length > 0) {
    parts.push(item.tags.map(t => `#${t}`).join(' '))
  }
  const text = parts.filter(Boolean).join('\n\n')
  try {
    await navigator.clipboard.writeText(text)
  } catch {
    // 非安全上下文（非 https）降级：用临时 textarea + execCommand 复制
    const textarea = document.createElement('textarea')
    textarea.value = text
    textarea.style.position = 'fixed'
    textarea.style.opacity = '0'
    document.body.appendChild(textarea)
    textarea.select()
    document.execCommand('copy')
    document.body.removeChild(textarea)
  }
  copiedPlatform.value = item.platform
  if (copyTimer !== undefined) clearTimeout(copyTimer)
  copyTimer = setTimeout(() => {
    copiedPlatform.value = ''
  }, 1500)
}
</script>

<style scoped>
.rewrite-container {
  max-width: 860px;
  padding-top: 24px;
  padding-bottom: 48px;
}

.rewrite-header {
  text-align: center;
  margin-bottom: 28px;
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: 10px;
}

.rewrite-card {
  display: flex;
  flex-direction: column;
  gap: var(--space-4);
}

.field-label {
  font-size: 14px;
  font-weight: 600;
  color: var(--text-main);
}

.rewrite-textarea {
  width: 100%;
  padding: 14px 16px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 15px;
  line-height: 1.7;
  color: var(--text-main);
  resize: vertical;
  min-height: 140px;
  font-family: inherit;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.rewrite-textarea:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.rewrite-textarea::placeholder {
  color: var(--text-placeholder);
}

.field-row {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  flex-wrap: wrap;
}

.source-select {
  padding: 10px 14px;
  border: 1px solid var(--border-color);
  border-radius: var(--radius-md);
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  cursor: pointer;
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.source-select:focus {
  outline: none;
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
}

.brand-empty-hint {
  font-size: 14px;
  color: var(--text-sub);
}

.brand-link {
  color: var(--primary);
  font-weight: 600;
  text-decoration: none;
}

.brand-link:hover {
  text-decoration: underline;
}

.field-block {
  display: flex;
  flex-direction: column;
  gap: var(--space-2);
}

.platform-chips {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.platform-chip {
  padding: 8px 18px;
  background: var(--gray-2);
  border: 1px solid transparent;
  border-radius: var(--radius-full);
  font-size: 14px;
  font-weight: 500;
  color: var(--text-sub);
  cursor: pointer;
  transition: background var(--transition-fast), color var(--transition-fast),
    border-color var(--transition-fast), box-shadow var(--transition-fast),
    transform var(--transition-fast);
}

.platform-chip:hover {
  background: var(--bg-card);
  border-color: var(--border-hover);
  color: var(--text-main);
  box-shadow: var(--shadow-xs);
  transform: translateY(-1px);
}

.platform-chip.active {
  background: var(--primary-light);
  border-color: var(--primary);
  color: var(--primary);
  font-weight: 600;
}

.submit-row {
  display: flex;
  justify-content: center;
  margin-top: var(--space-2);
}

.rewrite-btn {
  min-width: 180px;
}

/* 结果区 */
.results-section {
  margin-top: var(--space-5);
}

.result-card {
  animation: fadeIn 0.4s var(--ease-out);
}

.result-header {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: var(--space-3);
  margin-bottom: var(--space-3);
}

.platform-badge {
  display: inline-block;
  padding: 4px 14px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
}

.copy-btn {
  padding: 8px 18px;
  font-size: 14px;
}

.result-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: var(--space-3);
  line-height: 1.5;
}

.result-content {
  font-size: 15px;
  line-height: 1.8;
  color: var(--text-main);
  white-space: pre-wrap;
  word-break: break-word;
  margin-bottom: var(--space-3);
}

.result-tags {
  display: flex;
  flex-wrap: wrap;
  gap: var(--space-2);
}

.result-tag {
  padding: 6px 14px;
  font-size: var(--font-size-caption);
  cursor: default;
}

.result-tag:hover {
  transform: none;
  box-shadow: none;
  background: var(--gray-2);
  border-color: transparent;
  color: var(--text-sub);
}

/* 空/初始态 */
.empty-state {
  margin-top: var(--space-5);
  text-align: center;
  padding: var(--space-7) var(--space-5);
  color: var(--text-sub);
  font-size: 14px;
}

.empty-state p {
  margin: 0;
}

.rewrite-error {
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
  .rewrite-container {
    padding-top: 12px;
  }

  .card {
    padding: var(--space-5);
  }

  .field-row {
    align-items: flex-start;
    flex-direction: column;
  }

  .source-select {
    width: 100%;
  }

  .rewrite-btn {
    width: 100%;
  }

  .result-header {
    flex-wrap: wrap;
  }
}
</style>
