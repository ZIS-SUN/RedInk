import { createRouter, createWebHistory } from 'vue-router'
import type { NavigationGuardWithThis } from 'vue-router'
// 首页保持同步加载（首屏直达）；其余视图均走动态 import 懒加载拆包
import HomeView from '../views/HomeView.vue'
import { useGeneratorStore } from '../stores/generator'

/**
 * 流程页路由守卫：按 store 中的数据校验能否进入，缺数据时重定向首页。
 * 注意：store 必须在守卫执行时（导航发生时）再获取，此时 pinia 已安装。
 */
const requireOutlineData: NavigationGuardWithThis<undefined> = () => {
  const store = useGeneratorStore()
  // 进入大纲页至少要有主题或已有大纲内容
  if (!store.topic && store.outline.pages.length === 0) {
    return { name: 'home' }
  }
  return true
}

const requireGenerateData: NavigationGuardWithThis<undefined> = () => {
  const store = useGeneratorStore()
  // 生成页必须已有大纲页面
  if (store.outline.pages.length === 0) {
    return { name: 'home' }
  }
  return true
}

const requireResultData: NavigationGuardWithThis<undefined> = () => {
  const store = useGeneratorStore()
  // 结果页必须已有生成的图片
  if (store.images.length === 0) {
    return { name: 'home' }
  }
  return true
}

const router = createRouter({
  history: createWebHistory(import.meta.env.BASE_URL),
  // 切换路由时回到页面顶部
  scrollBehavior: () => ({ top: 0 }),
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/outline',
      name: 'outline',
      component: () => import('../views/OutlineView.vue'),
      beforeEnter: requireOutlineData
    },
    {
      path: '/generate',
      name: 'generate',
      component: () => import('../views/GenerateView.vue'),
      beforeEnter: requireGenerateData
    },
    {
      path: '/result',
      name: 'result',
      component: () => import('../views/ResultView.vue'),
      beforeEnter: requireResultData
    },
    {
      path: '/history',
      name: 'history',
      component: () => import('../views/HistoryView.vue')
    },
    {
      path: '/history/:id',
      name: 'history-detail',
      component: () => import('../views/HistoryView.vue')
    },
    {
      path: '/settings',
      name: 'settings',
      component: () => import('../views/SettingsView.vue')
    },
    {
      path: '/tools',
      name: 'tools',
      component: () => import('../views/ToolsView.vue')
    },
    {
      path: '/tools/rewrite',
      name: 'tool-rewrite',
      component: () => import('../views/ToolRewriteView.vue')
    },
    {
      path: '/tools/title',
      name: 'tool-title',
      component: () => import('../views/ToolTitleView.vue')
    },
    {
      path: '/tools/style',
      name: 'tool-style',
      component: () => import('../views/ToolStyleView.vue')
    },
    {
      path: '/tools/brand',
      name: 'tool-brand',
      component: () => import('../views/ToolBrandView.vue')
    },
    {
      path: '/tools/link',
      name: 'tool-link',
      component: () => import('../views/ToolLinkView.vue')
    },
    {
      path: '/tools/export',
      name: 'tool-export',
      component: () => import('../views/ToolExportView.vue')
    },
    {
      path: '/tools/topic',
      name: 'tool-topic',
      component: () => import('../views/ToolTopicView.vue')
    },
    {
      path: '/tools/calendar',
      name: 'tool-calendar',
      component: () => import('../views/ToolCalendarView.vue')
    },
    {
      path: '/tools/cover',
      name: 'tool-cover',
      component: () => import('../views/ToolCoverView.vue')
    },
    {
      path: '/tools/analytics',
      name: 'tool-analytics',
      component: () => import('../views/ToolAnalyticsView.vue')
    },
    {
      path: '/tools/benchmark',
      name: 'tool-benchmark',
      component: () => import('../views/ToolBenchmarkView.vue')
    },
    {
      path: '/tools/reply',
      name: 'tool-reply',
      component: () => import('../views/ToolReplyView.vue')
    },
    {
      path: '/tools/card-studio',
      name: 'tool-card-studio',
      component: () => import('../views/ToolCardStudioView.vue')
    },
    {
      path: '/tools/publish',
      name: 'tool-publish',
      component: () => import('../views/ToolPublishView.vue')
    },
    {
      // 404 兜底：所有未匹配路径统一进入 NotFound 页
      path: '/:pathMatch(.*)*',
      name: 'not-found',
      component: () => import('../views/NotFoundView.vue')
    }
  ]
})

export default router
