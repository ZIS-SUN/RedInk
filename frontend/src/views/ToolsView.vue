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
        <svg width="26" height="26" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M12 2l2.4 7.4H22l-6 4.6 2.3 7.4-6.3-4.6L5.7 21.4 8 14 2 9.4h7.6z"></path></svg>
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
          <div class="tool-icon" :class="`tone-${tool.tone}`" v-html="tool.icon"></div>
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

type ToolTone = 'primary' | 'info' | 'success' | 'warning'

interface ToolCard {
  name: string
  title: string
  desc: string
  tone: ToolTone
  icon: string
}

interface Stage {
  title: string
  sub: string
  tools: ToolCard[]
}

const ICON = {
  topic: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M9 18h6"></path><path d="M10 22h4"></path><path d="M15.09 14c.18-.98.65-1.74 1.41-2.5A4.65 4.65 0 0 0 18 8 6 6 0 0 0 6 8c0 1 .23 2.23 1.5 3.5A4.61 4.61 0 0 1 8.91 14"></path></svg>',
  benchmark: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg>',
  title: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polygon points="13 2 3 14 12 14 11 22 21 10 12 10 13 2"></polygon></svg>',
  rewrite: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="17 1 21 5 17 9"></polyline><path d="M3 11V9a4 4 0 0 1 4-4h14"></path><polyline points="7 23 3 19 7 15"></polyline><path d="M21 13v2a4 4 0 0 1-4 4H3"></path></svg>',
  reply: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M21 15a2 2 0 0 1-2 2H7l-4 4V5a2 2 0 0 1 2-2h14a2 2 0 0 1 2 2z"></path></svg>',
  brand: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M20 7h-9"></path><path d="M14 17H5"></path><circle cx="17" cy="17" r="3"></circle><circle cx="7" cy="7" r="3"></circle></svg>',
  style: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><circle cx="13.5" cy="6.5" r="2.5"></circle><circle cx="17.5" cy="10.5" r="2.5"></circle><circle cx="8.5" cy="7.5" r="2.5"></circle><circle cx="6.5" cy="12.5" r="2.5"></circle><path d="M12 2a10 10 0 0 0 0 20 2 2 0 0 0 2-2 2 2 0 0 1 2-2h1a5 5 0 0 0 5-5c0-6-5-9-10-9z"></path></svg>',
  cover: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="7" height="18" rx="1"></rect><rect x="14" y="3" width="7" height="18" rx="1"></rect></svg>',
  link: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M10 13a5 5 0 0 0 7.54.54l3-3a5 5 0 0 0-7.07-7.07l-1.72 1.71"></path><path d="M14 11a5 5 0 0 0-7.54-.54l-3 3a5 5 0 0 0 7.07 7.07l1.71-1.71"></path></svg>',
  exportImg: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="3" width="18" height="18" rx="2" ry="2"></rect><circle cx="8.5" cy="8.5" r="1.5"></circle><polyline points="21 15 16 10 5 21"></polyline></svg>',
  calendar: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><rect x="3" y="4" width="18" height="18" rx="2" ry="2"></rect><line x1="16" y1="2" x2="16" y2="6"></line><line x1="8" y1="2" x2="8" y2="6"></line><line x1="3" y1="10" x2="21" y2="10"></line></svg>',
  analytics: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="18" y1="20" x2="18" y2="10"></line><line x1="12" y1="20" x2="12" y2="4"></line><line x1="6" y1="20" x2="6" y2="14"></line></svg>',
  cardStudio: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><polyline points="4 7 4 4 20 4 20 7"></polyline><line x1="9" y1="20" x2="15" y2="20"></line><line x1="12" y1="4" x2="12" y2="20"></line></svg>',
  publish: '<svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><line x1="22" y1="2" x2="11" y2="13"></line><polygon points="22 2 15 22 11 13 2 9 22 2"></polygon></svg>'
}

const stages: Stage[] = [
  {
    title: '找灵感 · 定选题',
    sub: '不知道写什么？从这里开始',
    tools: [
      { name: 'tool-topic', title: '选题灵感', desc: '输入赛道，生成一批带角度与热度预估的选题', tone: 'primary', icon: ICON.topic },
      { name: 'tool-benchmark', title: '对标拆解', desc: '粘贴爆款，拆解它为什么火并生成同款套路草稿', tone: 'info', icon: ICON.benchmark }
    ]
  },
  {
    title: '写文案',
    sub: '标题、正文、互动，一次搞定',
    tools: [
      { name: 'tool-title', title: '爆款标题', desc: '生成一批带评分与爆款要素的候选标题', tone: 'warning', icon: ICON.title },
      { name: 'tool-rewrite', title: '多平台改写', desc: '一段文案改写成各平台风格', tone: 'primary', icon: ICON.rewrite },
      { name: 'tool-reply', title: '评论助手', desc: '生成高互动神回复与置顶引导', tone: 'success', icon: ICON.reply }
    ]
  },
  {
    title: '定风格 · 做视觉',
    sub: '统一人设与视觉，先选好再生成',
    tools: [
      { name: 'tool-brand', title: '品牌记忆', desc: '管理个人 IP / 品牌档案，保持人设一致', tone: 'success', icon: ICON.brand },
      { name: 'tool-style', title: '风格模板', desc: '选择或自定义视觉风格，一键应用到生成', tone: 'info', icon: ICON.style },
      { name: 'tool-cover', title: '封面A/B', desc: '生成多个封面方向，并排对比点击力', tone: 'primary', icon: ICON.cover }
    ]
  },
  {
    title: '生成与导出',
    sub: '把内容变成成品图',
    tools: [
      { name: 'tool-link', title: '链接转图文', desc: '粘贴链接或长文，自动提炼成多页大纲', tone: 'info', icon: ICON.link },
      { name: 'tool-card-studio', title: '文字卡片工坊', desc: '本地渲染文字卡片，秒级出图免等待', tone: 'primary', icon: ICON.cardStudio },
      { name: 'tool-export', title: '多尺寸导出', desc: '一图适配 9:16 / 1:1 / 3:4 等多平台尺寸', tone: 'warning', icon: ICON.exportImg }
    ]
  },
  {
    title: '排期与复盘',
    sub: '规划发布节奏，用数据迭代',
    tools: [
      { name: 'tool-calendar', title: '内容日历', desc: '规划发布节奏，管理各平台内容计划', tone: 'success', icon: ICON.calendar },
      { name: 'tool-publish', title: '发布助手', desc: '管理多平台账号，一键备好图文去发布', tone: 'primary', icon: ICON.publish },
      { name: 'tool-analytics', title: '数据复盘', desc: '录入数据看表现，获取 AI 复盘洞察', tone: 'info', icon: ICON.analytics }
    ]
  }
]
</script>

<style scoped>
.tools-page {
  padding-bottom: var(--space-8);
}

/* 核心创作入口：主色仅此一处大面积使用，作为工作台的视觉锚点 */
.hero-card {
  display: flex;
  align-items: center;
  gap: var(--space-5);
  padding: var(--space-6) var(--space-6);
  margin: var(--space-5) 0 var(--space-3);
  border-radius: var(--radius-xl);
  text-decoration: none;
  color: white;
  background: linear-gradient(120deg, var(--primary), var(--primary-hover));
  box-shadow: var(--shadow-sm), 0 12px 32px var(--primary-fade);
  transition: transform var(--transition-base), box-shadow var(--transition-base);
}

.hero-card:hover {
  transform: translateY(-2px);
  box-shadow: var(--shadow-md), 0 16px 40px rgba(239, 42, 69, 0.24);
}

.hero-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-sm), 0 8px 24px var(--primary-fade);
}

.hero-icon {
  flex-shrink: 0;
  width: 56px;
  height: 56px;
  border-radius: var(--radius-lg);
  display: flex;
  align-items: center;
  justify-content: center;
  color: white;
  background: rgba(255, 255, 255, 0.18);
  box-shadow: inset 0 0 0 1px rgba(255, 255, 255, 0.14);
  transition: transform var(--transition-base), background var(--transition-base);
}

.hero-card:hover .hero-icon {
  transform: scale(1.04);
  background: rgba(255, 255, 255, 0.24);
}

.hero-body { flex: 1; min-width: 0; }

.hero-title {
  font-size: 19px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  margin-bottom: var(--space-1);
}

.hero-desc {
  font-size: var(--font-size-caption);
  line-height: 1.6;
  opacity: 0.88;
}

.hero-arrow {
  flex-shrink: 0;
  opacity: 0.85;
  transition: transform var(--transition-fast);
}

.hero-card:hover .hero-arrow {
  transform: translateX(3px);
}

/* 阶段：首个阶段与 hero 稍近，后续阶段用大留白拉开节奏 */
.stage { margin-top: var(--space-7); }

.stage:first-of-type { margin-top: var(--space-6); }

.stage-head {
  display: flex;
  align-items: center;
  gap: var(--space-3);
  margin-bottom: var(--space-4);
}

.stage-num {
  flex-shrink: 0;
  width: 28px;
  height: 28px;
  border-radius: var(--radius-full);
  background: var(--primary-light);
  color: var(--primary);
  font-size: 13px;
  font-weight: 700;
  font-variant-numeric: tabular-nums;
  display: flex;
  align-items: center;
  justify-content: center;
  box-shadow: inset 0 0 0 1px var(--primary-fade);
}

.stage-title {
  font-size: 17px;
  font-weight: 700;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
}

.stage-sub {
  font-size: var(--font-size-caption);
  color: var(--text-secondary);
  margin-top: 2px;
}

.tools-grid {
  display: grid;
  grid-template-columns: repeat(auto-fill, minmax(300px, 1fr));
  gap: var(--space-4);
}

.tool-card {
  display: flex;
  align-items: center;
  gap: var(--space-4);
  padding: var(--space-5);
  margin-bottom: 0;
  text-decoration: none;
  color: inherit;
}

/* hover 上浮由全局 .card--interactive 提供，这里补 active 回落 */
.tool-card:active {
  transform: translateY(0);
  box-shadow: var(--shadow-xs);
}

/* 图标底色统一走语义 -soft token，克制不喧哗 */
.tool-icon {
  flex-shrink: 0;
  width: 46px;
  height: 46px;
  border-radius: var(--radius-md);
  display: flex;
  align-items: center;
  justify-content: center;
  transition: transform var(--transition-base);
}

.tool-card:hover .tool-icon {
  transform: scale(1.05);
}

.tool-icon.tone-primary {
  background: var(--primary-light);
  color: var(--primary);
}

.tool-icon.tone-info {
  background: var(--color-info-soft);
  color: var(--color-info);
}

.tool-icon.tone-success {
  background: var(--color-success-soft);
  color: var(--color-success);
}

.tool-icon.tone-warning {
  background: var(--color-warning-soft);
  color: var(--color-warning);
}

.tool-body { flex: 1; min-width: 0; }

.tool-name {
  font-size: var(--font-size-body);
  font-weight: 600;
  letter-spacing: var(--tracking-tight);
  color: var(--text-main);
  margin-bottom: 3px;
}

.tool-desc {
  font-size: var(--font-size-caption);
  line-height: 1.5;
  color: var(--text-secondary);
}

.tool-arrow {
  flex-shrink: 0;
  color: var(--text-placeholder);
  transition: transform var(--transition-fast), color var(--transition-fast);
}

.tool-card:hover .tool-arrow {
  color: var(--primary);
  transform: translateX(3px);
}

@media (max-width: 640px) {
  .tools-grid { grid-template-columns: 1fr; }
  .stage { margin-top: var(--space-6); }
  .hero-card { flex-wrap: nowrap; padding: var(--space-5); gap: var(--space-4); }
  .hero-icon { width: 48px; height: 48px; }
  .hero-title { font-size: 16px; }
}
</style>
