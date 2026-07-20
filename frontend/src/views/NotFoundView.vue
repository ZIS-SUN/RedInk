<template>
  <!-- 404 兜底页：风格与历史页空态保持一致 -->
  <div class="container not-found">
    <div class="empty-img">
      <svg width="40" height="40" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line><line x1="8" y1="11" x2="14" y2="11"></line></svg>
    </div>
    <h3>页面不存在</h3>
    <p class="empty-tips">你访问的页面可能已被移除，或地址输入有误</p>
    <button class="btn btn-primary empty-cta" @click="router.push('/')">
      返回首页
    </button>
  </div>
</template>

<script setup lang="ts">
import { useRouter } from 'vue-router'

const router = useRouter()
</script>

<style scoped>
/* 空态布局：与 HistoryView 的 empty-state-large 同构 */
.not-found {
  display: flex;
  flex-direction: column;
  align-items: center;
  text-align: center;
  padding: var(--space-8) var(--space-5);
  color: var(--text-sub);
}

.empty-img {
  width: 80px;
  height: 80px;
  border-radius: var(--radius-full);
  display: flex;
  align-items: center;
  justify-content: center;
  background: var(--gray-2);
  color: var(--gray-5);
}

.not-found h3 {
  margin: var(--space-5) 0 0;
  font-size: var(--font-size-subtitle);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.empty-tips {
  margin-top: var(--space-2);
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
}

.empty-cta {
  margin-top: var(--space-5);
}
</style>
