<template>
  <!-- 图片网格轮播背景 -->
  <div class="showcase-background" :class="{ 'is-ready': isReady }">
    <div class="showcase-grid" :style="{ '--scroll-duration': scrollDuration }">
      <!-- 两份相同副本实现无缝循环：动画位移 -50% 恰好等于一份内容的高度 -->
      <div v-for="(image, index) in doubledImages" :key="index" class="showcase-item">
        <img :src="`/assets/showcase/${image}`" :alt="`封面 ${(index % originalCount) + 1}`" loading="lazy" />
      </div>
    </div>
    <div class="showcase-overlay"></div>
  </div>
</template>

<script setup lang="ts">
import { computed, onMounted, ref } from 'vue'

/**
 * 图片展示背景组件
 *
 * 功能：
 * - 加载展示图片列表
 * - 纯 CSS @keyframes 无限循环滚动（无 JS 定时器，避免高频组件更新）
 * - 毛玻璃遮罩效果
 * - 平滑淡入过渡
 */

// 原始展示图片列表
const showcaseImages = ref<string[]>([])

// 是否准备好显示
const isReady = ref(false)

const originalCount = computed(() => showcaseImages.value.length || 1)

// 只保留 2 份副本用于无缝循环
const doubledImages = computed(() => [...showcaseImages.value, ...showcaseImages.value])

// 保持原有约 33px/s 的滚动速度：一份内容的高度 / 33
const scrollDuration = computed(() => {
  const rowHeight = 180
  const itemsPerRow = 11
  const totalRows = Math.ceil(originalCount.value / itemsPerRow)
  const sectionHeight = totalRows * rowHeight
  return `${Math.max(sectionHeight / 33, 10)}s`
})

/**
 * 预加载首屏图片
 */
function preloadImages(images: string[]): Promise<void[]> {
  const promises = images.map(image => {
    return new Promise<void>((resolve) => {
      const img = new Image()
      img.onload = () => resolve()
      img.onerror = () => resolve() // 即使加载失败也继续
      img.src = `/assets/showcase/${image}`
    })
  })
  return Promise.all(promises)
}

/**
 * 加载展示图片列表
 */
async function loadShowcaseImages() {
  try {
    const response = await fetch('/assets/showcase_manifest.json')
    const data = await response.json()
    const originalImages: string[] = data.covers || []

    // 预加载前几张图片（可视区域内的）
    const preloadCount = Math.min(originalImages.length, 22) // 约2行
    await preloadImages(originalImages.slice(0, preloadCount))

    showcaseImages.value = originalImages

    // 短暂延迟后显示，确保 DOM 渲染完成
    requestAnimationFrame(() => {
      requestAnimationFrame(() => {
        isReady.value = true
      })
    })
  } catch (e) {
    console.error('加载展示图片失败:', e)
    isReady.value = true // 即使失败也显示
  }
}

onMounted(() => {
  loadShowcaseImages()
})
</script>

<style scoped>
/* 背景容器 */
.showcase-background {
  position: fixed;
  top: 0;
  left: 0;
  width: 100%;
  height: 100vh;
  z-index: -1;
  overflow: hidden;
  opacity: 0;
  transition: opacity 0.6s ease-out;
}

.showcase-background.is-ready {
  opacity: 1;
}

/* 图片网格：纯 CSS 无限滚动，-50% 正好是一份副本的高度 */
.showcase-grid {
  display: grid;
  grid-template-columns: repeat(11, 1fr);
  gap: 16px;
  padding: 20px;
  width: 100%;
  will-change: transform;
  animation: showcase-scroll var(--scroll-duration, 60s) linear infinite;
}

@keyframes showcase-scroll {
  from {
    transform: translateY(0);
  }
  to {
    transform: translateY(-50%);
  }
}

/* 单个展示项 */
.showcase-item {
  width: 100%;
  aspect-ratio: 3 / 4;
  border-radius: 12px;
  overflow: hidden;
  box-shadow: 0 4px 12px rgba(0, 0, 0, 0.08);
}

.showcase-item img {
  width: 100%;
  height: 100%;
  object-fit: cover;
  display: block;
}

/* 毛玻璃遮罩层 */
.showcase-overlay {
  position: absolute;
  top: 0;
  left: 0;
  right: 0;
  bottom: 0;
  background: linear-gradient(
    to bottom,
    rgba(255, 255, 255, 0.7) 0%,
    rgba(255, 255, 255, 0.65) 30%,
    rgba(255, 255, 255, 0.6) 100%
  );
  backdrop-filter: blur(2px);
}

/* 用户偏好减少动态效果时暂停背景滚动 */
@media (prefers-reduced-motion: reduce) {
  .showcase-grid {
    animation: none;
  }
}

/* 响应式布局 */
@media (max-width: 768px) {
  .showcase-grid {
    grid-template-columns: repeat(3, 1fr);
    gap: 12px;
    padding: 12px;
  }
}
</style>
