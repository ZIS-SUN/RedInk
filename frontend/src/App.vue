<template>
  <div id="app">
    <!-- 侧边栏 Sidebar -->
    <aside class="layout-sidebar">
      <div class="logo-area">
        <img src="/logo-banner.png" alt="红墨 - 灵感一触即发" class="logo-icon" />
      </div>
      
      <nav class="nav-menu">
        <RouterLink to="/" class="nav-item" active-class="active">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="7"></rect><rect x="14" y="3" width="7" height="7"></rect><rect x="14" y="14" width="7" height="7"></rect><rect x="3" y="14" width="7" height="7"></rect></svg>
          <span class="nav-label-full">创作中心</span><span class="nav-label-short">创作</span>
        </RouterLink>
        <RouterLink to="/tools" class="nav-item" active-class="active">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14.7 6.3a1 1 0 0 0 0 1.4l1.6 1.6a1 1 0 0 0 1.4 0l3.77-3.77a6 6 0 0 1-7.94 7.94l-6.91 6.91a2.12 2.12 0 0 1-3-3l6.91-6.91a6 6 0 0 1 7.94-7.94l-3.76 3.76z"></path></svg>
          <span class="nav-label-full">创作工具</span><span class="nav-label-short">工具</span>
        </RouterLink>
        <RouterLink to="/history" class="nav-item" active-class="active">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
          <span class="nav-label-full">历史记录</span><span class="nav-label-short">历史</span>
        </RouterLink>
        <RouterLink to="/settings" class="nav-item" active-class="active">
          <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="12" cy="12" r="3"></circle><path d="M12 1v6m0 6v6m-6-6h6m6 0h-6"></path><path d="M19.4 15a1.65 1.65 0 0 0 .33 1.82l.06.06a2 2 0 0 1 0 2.83 2 2 0 0 1-2.83 0l-.06-.06a1.65 1.65 0 0 0-1.82-.33 1.65 1.65 0 0 0-1 1.51V21a2 2 0 0 1-2 2 2 2 0 0 1-2-2v-.09A1.65 1.65 0 0 0 9 19.4a1.65 1.65 0 0 0-1.82.33l-.06.06a2 2 0 0 1-2.83 0 2 2 0 0 1 0-2.83l.06-.06a1.65 1.65 0 0 0 .33-1.82 1.65 1.65 0 0 0-1.51-1H3a2 2 0 0 1-2-2 2 2 0 0 1 2-2h.09A1.65 1.65 0 0 0 4.6 9a1.65 1.65 0 0 0-.33-1.82l-.06-.06a2 2 0 0 1 0-2.83 2 2 0 0 1 2.83 0l.06.06a1.65 1.65 0 0 0 1.82.33H9a1.65 1.65 0 0 0 1-1.51V3a2 2 0 0 1 2-2 2 2 0 0 1 2 2v.09a1.65 1.65 0 0 0 1 1.51 1.65 1.65 0 0 0 1.82-.33l.06-.06a2 2 0 0 1 2.83 0 2 2 0 0 1 0 2.83l-.06.06a1.65 1.65 0 0 0-.33 1.82V9a1.65 1.65 0 0 0 1.51 1H21a2 2 0 0 1 2 2 2 2 0 0 1-2 2h-.09a1.65 1.65 0 0 0-1.51 1z"></path></svg>
          <span class="nav-label-full">系统设置</span><span class="nav-label-short">设置</span>
        </RouterLink>
      </nav>
      
      <div class="sidebar-user">
        <div class="sidebar-user-inner">
          <div class="sidebar-user-avatar">墨</div>
          <div>
            <div class="sidebar-user-name">默子</div>
            <div class="sidebar-user-id">mozi</div>
          </div>
        </div>
      </div>
    </aside>

    <!-- 主内容区 -->
    <main class="layout-main">
      <RouterView v-slot="{ Component, route }">
        <component :is="Component" />

        <!-- 全局页脚版权信息（首页除外）：仅保留中性的品牌与协议信息 -->
        <footer v-if="route.path !== '/'" class="global-footer">
          <div class="footer-content">
            <div class="footer-text">
              © 2025 <a href="https://github.com/HisMax/RedInk" target="_blank" rel="noopener noreferrer">RedInk</a> by 默子 (Histone)
            </div>
            <div class="footer-license">
              Licensed under <a href="https://creativecommons.org/licenses/by-nc-sa/4.0/" target="_blank" rel="noopener noreferrer">CC BY-NC-SA 4.0</a>
            </div>
          </div>
        </footer>
      </RouterView>
    </main>
  </div>
</template>

<script setup lang="ts">
import { RouterView, RouterLink } from 'vue-router'
import { onMounted } from 'vue'
import { setupAutoSave } from './stores/generator'

// 启用自动保存到 localStorage
onMounted(() => {
  setupAutoSave()
})
</script>

<style scoped>
/* ==========================================================
 * 应用外壳精修（在 base.css 全局样式之上做克制的覆写）
 * ========================================================== */

/* 侧边栏：logo 与导航项左缘对齐（统一 12px 内缩进） */
.logo-area {
  padding: 0 var(--space-3);
}

.nav-item {
  padding: 11px var(--space-3);
  transition: background var(--transition-fast), color var(--transition-fast),
    box-shadow var(--transition-fast);
}

/* 选中 pill：柔和底色之上加一层极浅描边 + 静置阴影，更有"实体感" */
.nav-item.active {
  box-shadow: var(--shadow-xs), inset 0 0 0 1px var(--primary-fade);
}

/* 用户区：与导航项左缘对齐，hover 反馈与导航一致 */
.sidebar-user {
  padding-top: var(--space-4);
}

.sidebar-user-inner {
  padding: var(--space-2) var(--space-3);
}

/* 页脚：仅品牌与协议信息，视觉上更安静克制 */
.global-footer {
  padding: var(--space-5) 0 var(--space-4);
}

.footer-content {
  gap: var(--space-1);
}

.footer-text {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  font-weight: 400;
}

.footer-text a {
  color: var(--text-sub);
  font-weight: 500;
}

.footer-text a:hover {
  color: var(--primary);
}

/* 移动端底部 tab bar：还原全宽点击区，去掉桌面态的 pill 修饰 */
@media (max-width: 768px) {
  .nav-item {
    padding: 6px 4px;
  }

  .nav-item.active {
    box-shadow: none;
  }
}
</style>
