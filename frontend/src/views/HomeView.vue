<template>
  <div class="container home-container">
    <!-- 图片网格轮播背景 -->
    <ShowcaseBackground />

    <!-- Hero Area -->
    <div class="hero-section">
      <div class="hero-content">
        <div class="brand-pill">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right: 6px;"><path d="m12 3-1.912 5.813a2 2 0 0 1-1.275 1.275L3 12l5.813 1.912a2 2 0 0 1 1.275 1.275L12 21l1.912-5.813a2 2 0 0 1 1.275-1.275L21 12l-5.813-1.912a2 2 0 0 1-1.275-1.275L12 3Z"/></svg>
          AI 驱动的红墨创作助手
        </div>
        <div class="platform-slogan">
          让传播不再需要门槛，让创作从未如此简单
        </div>
        <h1 class="page-title">灵感一触即发</h1>
        <p class="page-subtitle">输入你的创意主题，让 AI 帮你生成爆款标题、正文和封面图</p>
      </div>

      <!-- 主题输入组合框 -->
      <ComposerInput
        ref="composerRef"
        v-model="topic"
        :loading="loading"
        @generate="handleGenerate"
        @imagesChange="handleImagesChange"
      />

      <!-- 品牌人设选择器（可选） -->
      <div v-if="brands.length > 0" class="brand-select-row">
        <label class="brand-select-label" for="brand-select">品牌人设（可选）</label>
        <select
          id="brand-select"
          class="brand-select"
          :value="store.brandId"
          @change="handleBrandChange"
        >
          <option value="">不使用</option>
          <option v-for="brand in brands" :key="brand.id" :value="brand.id">
            {{ brand.name }}
          </option>
        </select>
      </div>
    </div>

    <!-- 版权信息 -->
    <div class="page-footer">
      <div class="footer-tip">
        配置不成功？访问 <a href="https://redink.top" target="_blank" rel="noopener noreferrer">redink.top</a> 官方站点即刻体验
      </div>
      <div class="footer-copyright">
        © 2025 <a href="https://github.com/HisMax/RedInk" target="_blank" rel="noopener noreferrer">RedInk</a> by 默子 (Histone)
      </div>
      <div class="footer-license">
        Licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-NC-SA 4.0</a>
      </div>
    </div>

    <ErrorCard
      v-if="error"
      class="home-error"
      :error="error"
      dismissible
      @dismiss="error = null"
      @retry="handleGenerate"
    />
  </div>
</template>

<script setup lang="ts">
import { ref, onMounted } from 'vue'
import { useRouter } from 'vue-router'
import { useGeneratorStore } from '../stores/generator'
import { generateOutline, createHistory } from '../api'
import { getBrandList, type BrandKit } from '../api/brand'
import { normalizeApiError, type AppError } from '../utils/errors'

// 引入组件
import ShowcaseBackground from '../components/home/ShowcaseBackground.vue'
import ComposerInput from '../components/home/ComposerInput.vue'
import ErrorCard from '../components/common/ErrorCard.vue'

const router = useRouter()
const store = useGeneratorStore()

// 状态
const topic = ref('')
const loading = ref(false)
const error = ref<AppError | null>(null)
const composerRef = ref<InstanceType<typeof ComposerInput> | null>(null)

// 上传的图片文件
const uploadedImageFiles = ref<File[]>([])

// 品牌档案列表（用于品牌人设选择器）
const brands = ref<BrandKit[]>([])

// 从大纲页「上一步」返回时，回填之前输入的主题
onMounted(() => {
  if (store.topic && !topic.value) {
    topic.value = store.topic
  }
  loadBrands()
})

/**
 * 拉取品牌档案列表并确定默认选中项：
 * - store 中已持久化的 brandId 仍有效时沿用
 * - 否则默认选中当前启用档案；没有启用档案则为「不使用」
 * 拉取失败静默忽略（选择器不显示，行为与无品牌一致）
 */
async function loadBrands() {
  const result = await getBrandList()
  if (!result.success) return

  brands.value = result.brands

  const hasBrand = (id: string) => result.brands.some(b => b.id === id)
  if (store.brandId && hasBrand(store.brandId)) return

  if (result.active_id && hasBrand(result.active_id)) {
    store.setBrandId(result.active_id)
  } else {
    store.setBrandId('')
  }
}

/**
 * 品牌人设选择变化时写入 store
 */
function handleBrandChange(event: Event) {
  store.setBrandId((event.target as HTMLSelectElement).value)
}

/**
 * 处理图片变化
 */
function handleImagesChange(images: File[]) {
  uploadedImageFiles.value = images
}

/**
 * 生成大纲
 */
async function handleGenerate() {
  if (!topic.value.trim()) return

  loading.value = true
  error.value = null

  try {
    const imageFiles = uploadedImageFiles.value

    const result = await generateOutline(
      topic.value.trim(),
      imageFiles.length > 0 ? imageFiles : undefined,
      store.brandId || undefined
    )

    if (result.success && result.pages) {
      // 设置主题和大纲到 store
      store.setTopic(topic.value.trim())
      store.setOutline(result.outline || '', result.pages)

      // 大纲生成成功后，立即创建历史记录
      // 这样即使用户刷新页面或关闭浏览器，大纲也不会丢失
      try {
        const historyResult = await createHistory(
          topic.value.trim(),
          {
            raw: result.outline || '',
            pages: result.pages
          }
        )

        // 保存历史记录 ID 到 store，后续生成正文和图片时会使用
        if (historyResult.success && historyResult.record_id) {
          store.setRecordId(historyResult.record_id)
        } else {
          // 创建历史记录失败，记录错误但不阻断流程
          console.error('创建历史记录失败:', historyResult.error || '未知错误')
          store.setRecordId(null)
        }
      } catch (err: any) {
        // 创建历史记录异常，记录错误但不阻断流程
        console.error('创建历史记录异常:', err.message || err)
        store.setRecordId(null)
      }

      // 保存用户上传的图片到 store
      if (imageFiles.length > 0) {
        store.userImages = imageFiles
      } else {
        store.userImages = []
      }

      // 清理 ComposerInput 的预览
      composerRef.value?.clearPreviews()
      uploadedImageFiles.value = []

      router.push('/outline')
    } else {
      error.value = normalizeApiError(result.error || result.error_message || '生成大纲失败', '生成大纲失败')
    }
  } catch (err: any) {
    error.value = normalizeApiError(err, '生成大纲失败')
  } finally {
    loading.value = false
  }
}
</script>

<style scoped>
.home-container {
  max-width: 1100px;
  padding-top: 10px;
  position: relative;
  z-index: 1;
}

/* Hero Section */
.hero-section {
  text-align: center;
  margin-bottom: var(--space-7);
  padding: var(--space-7) var(--space-8);
  animation: fadeIn 0.6s var(--ease-out);
  background: rgba(255, 255, 255, 0.94);
  border: 1px solid rgba(255, 255, 255, 0.7);
  border-radius: var(--radius-xl);
  box-shadow: var(--shadow-md);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
}

.hero-content {
  margin-bottom: var(--space-6);
}

.brand-pill {
  display: inline-block;
  padding: 6px 16px;
  background: var(--primary-fade);
  color: var(--primary);
  border-radius: var(--radius-full);
  font-size: var(--font-size-caption);
  font-weight: 600;
  margin-bottom: var(--space-5);
  letter-spacing: 0.02em;
}

/* 品牌人设选择器 */
.brand-select-row {
  display: flex;
  align-items: center;
  justify-content: center;
  gap: 10px;
  margin-top: 16px;
}

.brand-select-label {
  font-size: 14px;
  color: var(--text-sub);
}

.brand-select {
  padding: 8px 12px;
  font-size: 14px;
  color: var(--text-main);
  background: var(--bg-card);
  border: 1px solid var(--border-color);
  border-radius: var(--radius-sm);
  cursor: pointer;
  box-shadow: var(--shadow-xs);
  transition: border-color var(--transition-fast), box-shadow var(--transition-fast);
}

.brand-select:hover {
  border-color: var(--border-hover);
}

.brand-select:focus {
  border-color: var(--primary);
  box-shadow: var(--shadow-focus);
  outline: none;
}

.platform-slogan {
  font-size: var(--font-size-subtitle);
  font-weight: 600;
  color: var(--text-sub);
  margin-bottom: var(--space-5);
  line-height: 1.6;
  letter-spacing: var(--tracking-tight);
}

.page-subtitle {
  font-size: var(--font-size-subtitle);
  color: var(--text-sub);
  margin-top: var(--space-3);
}

/* Page Footer */
.page-footer {
  text-align: center;
  padding: var(--space-5) 0 var(--space-4);
  margin-top: var(--space-5);
}

.footer-copyright {
  font-size: var(--font-size-body);
  color: var(--text-sub);
  font-weight: 500;
  margin-bottom: 6px;
}

.footer-copyright a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}

.footer-copyright a:hover {
  text-decoration: underline;
}

.footer-license {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.footer-license a {
  color: var(--text-sub);
  text-decoration: none;
  transition: color var(--transition-fast);
}

.footer-license a:hover {
  color: var(--primary);
}

.footer-tip {
  font-size: 14px;
  color: var(--text-sub);
  margin-bottom: var(--space-3);
}

.footer-tip a {
  color: var(--primary);
  text-decoration: none;
  font-weight: 600;
}

.footer-tip a:hover {
  text-decoration: underline;
}

.home-error {
  position: fixed;
  bottom: var(--space-6);
  left: 50%;
  transform: translateX(-50%);
  width: min(720px, calc(100vw - 32px));
  z-index: 1000;
  animation: slideUp 0.3s var(--ease-out);
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

@media (prefers-reduced-motion: reduce) {
  .hero-section,
  .home-error {
    animation: none;
  }
}

/* 移动端：留白收敛，保持呼吸感不溢出 */
@media (max-width: 640px) {
  .hero-section {
    padding: var(--space-6) var(--space-4);
    margin-bottom: var(--space-6);
  }
}
</style>
