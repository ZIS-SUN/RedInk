<template>
  <div class="container tools-page">
    <header class="page-header">
      <div>
        <h1 class="page-title">创作工作台</h1>
        <p class="page-subtitle">从找选题到复盘，一条龙提效工具</p>
      </div>
    </header>

    <!-- 核心创作入口 -->
    <RouterLink to="/" class="hero-card">
      <div class="hero-icon">
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7.4-6.3-4.6L5.7 21.4 8 14 2 9.4h7.6z"></path></svg>
      </div>
      <div class="hero-body">
        <div class="hero-title">一句话生成图文卡片</div>
        <div class="hero-desc">主创作流程：输入主题 → 大纲 → 封面 → 批量成图，全程套用你的品牌人设与风格</div>
      </div>
      <svg class="hero-arrow" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
    </RouterLink>

    <!-- 分阶段工具 -->
    <section v-for="(stage, si) in stages" :key="stage.title" class="stage">
      <div class="stage-head">
        <span class="stage-num">{{ si + 1 }}</span>
        <div>
          <div class="stage-title">{{ stage.title }}</div>
          <div class="stage-sub">{{ stage.sub }}</div>
        </div>
      </div>
      <div class="tools-grid">
        <RouterLink
          v-for="tool in stage.tools"
          :key="tool.name"
          :to="{ name: tool.name }"
          class="card card--interactive tool-card"
        >
          <div class="tool-icon" :style="{ background: tool.color }" v-html="tool.icon"></div>
          <div class="tool-body">
            <div class="tool-name">{{ tool.title }}</div>
            <div class="tool-desc">{{ tool.desc }}</div>
          </div>
          <svg class="tool-arrow" width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="9 18 15 12 9 6"></polyline></svg>
        </RouterLink>
      </div>
    </section>
  </div>
</template>

<script setup lang="ts">
import { RouterLink } from 'vue-router'

interface ToolCard {
  name: string
  title: string
  desc: string
  color: string
  icon: string
}

interface Stage {
  title: string
  sub: string
  tools: ToolCard[]
}

const ICON = {
  topic: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"></path></svg>',
  benchmark: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
  title: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
  rewrite: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>',
  reply: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
  brand: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7h-9"></path><path d="M14 17H5"></path><circle cx="17" cy="17" r="3"></circle><circle cx="7" cy="7" r="3"></circle></svg>',
  style: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r="2.5"></circle><circle cx="17.5" cy="10.5" r="2.5"></circle><circle cx="8.5" cy="7.5" r="2.5"></circle><circle cx="6.5" cy="12.5" r="2.5"></circle><path d="M12 2a10 10 0 0 0 0 20 2 2 0 0 0 2-2 2 2 0 0 1 2-2h1a5 5 0 0 0 5-5c0-6-5-9-10-9z"></path></svg>',
  cover: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="18" rx="1"></rect><rect x="14" y="3" width="7" height="18" rx="1"></rect></svg>',
  link: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>',
  exportImg: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
  calendar: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
  analytics: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>'
}

const stages: Stage[] = [
  {
    title: '找灵感 · 定选题',
    sub: '不知道写什么？从这里开始',
    tools: [
      { name: 'tool-topic', title: '选题灵感', desc: '输入赛道，生成一批带角度与热度预估的选题', color: 'linear-gradient(135deg, #FF5E7E, #FF2442)', icon: ICON.topic },
      { name: 'tool-benchmark', title: '对标拆解', desc: '粘贴爆款，拆解它为什么火并生成同款套路草稿', color: 'linear-gradient(135deg, #74B9FF, #0984E3)', icon: ICON.benchmark }
    ]
  },
  {
    title: '写文案',
    sub: '标题、正文、互动，一次搞定',
    tools: [
      { name: 'tool-title', title: '爆款标题', desc: '生成一批带评分与爆款要素的候选标题', color: 'linear-gradient(135deg, #FFA94D, #FF6B35)', icon: ICON.title },
      { name: 'tool-rewrite', title: '多平台改写', desc: '一段文案改写成各平台风格', color: 'linear-gradient(135deg, #FF6B9D, #FF2442)', icon: ICON.rewrite },
      { name: 'tool-reply', title: '评论助手', desc: '生成高互动神回复与置顶引导', color: 'linear-gradient(135deg, #55C57A, #2E9E5B)', icon: ICON.reply }
    ]
  },
  {
    title: '定风格 · 做视觉',
    sub: '统一人设与视觉，先选好再生成',
    tools: [
      { name: 'tool-brand', title: '品牌记忆', desc: '管理个人 IP / 品牌档案，保持人设一致', color: 'linear-gradient(135deg, #4DD4C4, #1FB6A6)', icon: ICON.brand },
      { name: 'tool-style', title: '风格模板', desc: '选择或自定义视觉风格，一键应用到生成', color: 'linear-gradient(135deg, #9B7BFF, #6C5CE7)', icon: ICON.style },
      { name: 'tool-cover', title: '封面A/B', desc: '生成多个封面方向，并排对比点击力', color: 'linear-gradient(135deg, #F368E0, #C13FCB)', icon: ICON.cover }
    ]
  },
  {
    title: '生成与导出',
    sub: '把内容变成成品图',
    tools: [
      { name: 'tool-link', title: '链接转图文', desc: '粘贴链接或长文，自动提炼成多页大纲', color: 'linear-gradient(135deg, #5AA9FF, #3B82F6)', icon: ICON.link },
      { name: 'tool-export', title: '多尺寸导出', desc: '一图适配 9:16 / 1:1 / 3:4 等多平台尺寸', color: 'linear-gradient(135deg, #FF8FA3, #E84393)', icon: ICON.exportImg }
    ]
  },
  {
    title: '排期与复盘',
    sub: '规划发布节奏，用数据迭代',
    tools: [
      { name: 'tool-calendar', title: '内容日历', desc: '规划发布节奏，管理各平台内容计划', color: 'linear-gradient(135deg, #7AC8A0, #1FB6A6)', icon: ICON.calendar },
      { name: 'tool-analytics', title: '数据复盘', desc: '录入数据看表现，获取 AI 复盘洞察', color: 'linear-gradient(135deg, #A29BFE, #6C5CE7)', icon: ICON.analytics }
    ]
  }
]
</script>

<style scoped>
.tools-page {
  padding-bottom: 40px;
}

/* 核心创作入口 */
.hero-card {
  display: flex;
  align-items: center;
  gap: var(--space-4, 16px);
  padding: 22px 24px;
  margin: var(--space-4, 16px) 0 8px;
  border-radius: var(--radius-lg, 16px);
  text-decoration: none;
  color: white;
  background: linear-gradient(120deg, #FF2442, #FF6B9D);
  box-shadow: 0 10px 28px rgba(255, 36, 66, 0.28);
  transition: transform 0.2s ease, box-shadow 0.2s ease;
}

.hero-card:hover {
  transform: translateY(-2px);
  box-shadow: 0 14px 34px rgba(255, 36, 66, 0.34);
}

.hero-icon {
  flex-shrink: 0;
  width: 52px;
  height: 52px;
  border-radius: 14px;
  display: flex;
  align-items: center;
  justify-content: center;
  background: rgba(255, 255, 255, 0.22);
}

.hero-body { flex: 1; min-width: 0; }
.hero-title { font-size: 18px; font-weight: 700; margin-bottom: 4px; }
.hero-desc { font-size: 13px; line-height: 1.5; opacity: 0.92; }
.hero-arrow { flex-shrink: 0; opacity: 0.9; }

/* 阶段 */
.stage { margin-top: 28px; }

.stage-head {
  display: flex;
  align-items: center;
  gap: 12px;
  margin-bottom: var(--space-3, 12px);
}

.stage-num {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: 50%;
  background: var(--primary);
  color: white;
  font-size: 14px;
  font-weight: 700;
  display: flex;
  align-items: center;
  justify-content: center;
}

.stage-title { font-size: 16px; font-weight: 600; color: var(--text-primary, #1f2328); }
.stage-sub { font-size: 12px; color: var(--text-secondary, #6b7280); margin-top: 2px; }

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4, 16px);
}

.tool-card {
  display: flex;
  align-items: center;
  gap: var(--space-4, 16px);
  padding: 18px;
  text-decoration: none;
  color: inherit;
}

.tool-icon {
  flex-shrink: 0;
  width: 46px;
  height: 46px;
  border-radius: var(--radius-lg, 14px);
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: 0 6px 16px rgba(0, 0, 0, 0.12);
}

.tool-body { flex: 1; min-width: 0; }
.tool-name { font-size: 15px; font-weight: 600; color: var(--text-primary, #1f2328); margin-bottom: 3px; }
.tool-desc { font-size: 12.5px; line-height: 1.5; color: var(--text-secondary, #6b7280); }

.tool-arrow {
  flex-shrink: 0;
  color: var(--text-placeholder, #c0c4cc);
  transition: transform 0.2s ease, color 0.2s ease;
}

.tool-card:hover .tool-arrow {
  color: var(--primary);
  transform: translateX(3px);
}

@media (max-width: 640px) {
  .tools-grid { grid-template-columns: 1fr; }
  .hero-card { flex-wrap: nowrap; padding: 18px; }
  .hero-title { font-size: 16px; }
}
</style>
