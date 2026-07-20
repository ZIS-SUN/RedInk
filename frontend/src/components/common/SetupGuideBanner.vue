<template>
  <div v-if="visible" class="setup-banner" role="status" aria-live="polite">
    <svg
      class="setup-banner-icon"
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      stroke-width="2"
      stroke-linecap="round"
      stroke-linejoin="round"
      aria-hidden="true"
    >
      <circle cx="12" cy="12" r="10"></circle>
      <line x1="12" y1="8" x2="12" y2="12"></line>
      <line x1="12" y1="16" x2="12.01" y2="16"></line>
    </svg>
    <span class="setup-banner-text">还没配置 AI 服务商，先去设置里填好 API Key 再开始创作</span>
    <RouterLink to="/settings" class="setup-banner-link">去设置</RouterLink>
    <button
      class="setup-banner-close"
      type="button"
      aria-label="本次会话不再提示"
      @click="dismiss"
    >
      ×
    </button>
  </div>
</template>

<script setup lang="ts">
import { onMounted, ref } from 'vue'
import { RouterLink } from 'vue-router'
import { getConfig } from '../../api'
import { getProviderConfigStatus } from '../../utils/providerConfig'

/**
 * 未配置 AI 服务商引导横幅
 *
 * - 挂载时静默拉取 /api/config，检测到任一服务商已配置 API Key 则不显示
 * - 检测失败（后端未启动等）静默不显示，绝不因此报错
 * - 关闭后写入 sessionStorage，本会话内不再弹出
 */

const DISMISS_KEY = 'redink_setup_banner_dismissed'

const visible = ref(false)

onMounted(async () => {
  if (isDismissed()) return
  try {
    const result = await getConfig()
    if (result.success && result.config) {
      visible.value = !getProviderConfigStatus(result.config).anyConfigured
    }
  } catch {
    // 静默：检测失败时不显示横幅，也不打扰用户
  }
})

function dismiss() {
  visible.value = false
  try {
    sessionStorage.setItem(DISMISS_KEY, '1')
  } catch {
    // sessionStorage 不可用（隐私模式等）时仅本次隐藏
  }
}

function isDismissed(): boolean {
  try {
    return sessionStorage.getItem(DISMISS_KEY) === '1'
  } catch {
    return false
  }
}
</script>

<style scoped>
.setup-banner {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  padding: var(--space-3) var(--space-4);
  margin-bottom: var(--space-4);
  border: 1px solid rgba(240, 158, 26, 0.28);
  background: var(--color-warning-soft);
  color: var(--color-warning);
  border-radius: var(--radius-md);
  font-size: var(--font-size-caption);
  animation: setupBannerIn 0.3s var(--ease-out);
}

.setup-banner-icon {
  flex-shrink: 0;
}

.setup-banner-text {
  flex: 1;
  min-width: 0;
  line-height: 1.5;
}

.setup-banner-link {
  flex-shrink: 0;
  padding: 5px 14px;
  border-radius: var(--radius-full);
  background: var(--color-warning);
  color: #fff;
  font-weight: 600;
  text-decoration: none;
  white-space: nowrap;
  transition: opacity var(--transition-fast), transform var(--transition-fast);
}

.setup-banner-link:hover {
  opacity: 0.9;
  transform: translateY(-1px);
}

.setup-banner-close {
  flex-shrink: 0;
  border: none;
  background: transparent;
  color: var(--color-warning);
  font-size: 18px;
  line-height: 1;
  cursor: pointer;
  padding: 0 2px;
  border-radius: var(--radius-xs);
  transition: opacity var(--transition-fast);
}

.setup-banner-close:hover {
  opacity: 0.7;
}

@keyframes setupBannerIn {
  from {
    opacity: 0;
    transform: translateY(-6px);
  }
  to {
    opacity: 1;
    transform: translateY(0);
  }
}

@media (prefers-reduced-motion: reduce) {
  .setup-banner {
    animation: none;
  }
}
</style>
