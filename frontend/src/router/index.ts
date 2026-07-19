import { createRouter, createWebHistory } from 'vue-router'
import type { NavigationGuardWithThis } from 'vue-router'
import HomeView from '../views/HomeView.vue'
import OutlineView from '../views/OutlineView.vue'
import GenerateView from '../views/GenerateView.vue'
import ResultView from '../views/ResultView.vue'
import HistoryView from '../views/HistoryView.vue'
import SettingsView from '../views/SettingsView.vue'
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
  routes: [
    {
      path: '/',
      name: 'home',
      component: HomeView
    },
    {
      path: '/outline',
      name: 'outline',
      component: OutlineView,
      beforeEnter: requireOutlineData
    },
    {
      path: '/generate',
      name: 'generate',
      component: GenerateView,
      beforeEnter: requireGenerateData
    },
    {
      path: '/result',
      name: 'result',
      component: ResultView,
      beforeEnter: requireResultData
    },
    {
      path: '/history',
      name: 'history',
      component: HistoryView
    },
    {
      path: '/history/:id',
      name: 'history-detail',
      component: HistoryView
    },
    {
      path: '/settings',
      name: 'settings',
      component: SettingsView
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
    }
  ]
})

export default router
