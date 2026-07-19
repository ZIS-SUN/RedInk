/**
 * 风格模板库 - 预设数据
 *
 * 纯前端静态数据，不依赖后端。
 * 封面全部用 CSS 渐变占位（coverGradient），无需真实图片。
 */

/** 模板分类 */
export type StyleCategory = '简约' | '柔和' | '潮流' | '商务' | '可爱' | '高级'

/** 分类筛选列表（'全部' 由视图层自行添加） */
export const styleCategories: StyleCategory[] = ['简约', '柔和', '潮流', '商务', '可爱', '高级']

/** 风格模板 */
export interface StyleTemplate {
  /** 唯一标识 */
  id: string
  /** 模板名称 */
  name: string
  /** 所属分类 */
  category: StyleCategory
  /** 风格描述文案 */
  description: string
  /** 封面示意（CSS background 值，渐变/色块占位） */
  coverGradient: string
  /** 推荐配色（hex 色值） */
  colors: string[]
  /** 适用场景 */
  scenes: string[]
  /** 可直接用于图片生成的风格提示词 */
  stylePrompt: string
  /** 是否为用户自定义模板（预设为 false/缺省，自定义为 true） */
  custom?: boolean
}

export const styleTemplates: StyleTemplate[] = [
  {
    id: 'ins-minimal',
    name: 'ins 简约',
    category: '简约',
    description: '大量留白、克制的配色与细腻的排版层次，像 Instagram 博主的精致九宫格，安静但有质感。',
    coverGradient: 'linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%)',
    colors: ['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238'],
    scenes: ['个人分享', '穿搭笔记', '生活方式', '摄影作品'],
    stylePrompt:
      'ins风简约设计，大量留白，米白与浅驼色低饱和配色，细无衬线字体，极简排版，柔和自然光影，干净通透的画面质感，高级感构图，minimalist instagram aesthetic'
  },
  {
    id: 'morandi',
    name: '莫兰迪',
    category: '柔和',
    description: '灰调低饱和的莫兰迪色系，雾感十足，温柔高级不刺眼，适合传递平静与品味。',
    coverGradient: 'linear-gradient(135deg, #cdc6bd 0%, #a8b2a1 50%, #b5a8a0 100%)',
    colors: ['#CDC6BD', '#A8B2A1', '#B5A8A0', '#8A8580'],
    scenes: ['家居好物', '美学分享', '情绪随笔', '慢生活'],
    stylePrompt:
      '莫兰迪色系设计，灰调低饱和配色，雾面质感，柔和渐变背景，优雅的留白排版，细腻的纹理细节，温柔安静的高级感氛围，morandi muted color palette'
  },
  {
    id: 'cyberpunk',
    name: '赛博朋克',
    category: '潮流',
    description: '霓虹紫蓝撞色、故障艺术与暗夜都市感，视觉冲击拉满，一眼吸睛的未来感风格。',
    coverGradient: 'linear-gradient(135deg, #0f0c29 0%, #302b63 40%, #ff00cc 100%)',
    colors: ['#0F0C29', '#302B63', '#FF00CC', '#00F0FF'],
    scenes: ['科技数码', '游戏电竞', '潮流话题', '未来趋势'],
    stylePrompt:
      '赛博朋克风格，霓虹紫蓝撞色，暗夜都市背景，发光线条与全息元素，故障艺术效果，强烈的未来科技感，高对比霓虹光效，cyberpunk neon glitch aesthetic'
  },
  {
    id: 'xhs-journal',
    name: '小红书暖色手账',
    category: '可爱',
    description: '暖橘奶油色打底，配上胶带、贴纸、手写体等手账元素，亲切治愈，天然适配种草笔记。',
    coverGradient: 'linear-gradient(135deg, #fff5e6 0%, #ffd9b3 50%, #ffb88c 100%)',
    colors: ['#FFF5E6', '#FFD9B3', '#FFB88C', '#E8875B'],
    scenes: ['好物种草', '日常记录', '攻略清单', '打卡分享'],
    stylePrompt:
      '小红书暖色手账风格，奶油橘暖色调，手账贴纸与和纸胶带元素，可爱手写体标注，圆角卡片布局，温暖治愈的氛围感，俏皮的涂鸦装饰，warm scrapbook journal style'
  },
  {
    id: 'business-brief',
    name: '商务简报',
    category: '商务',
    description: '深蓝与灰白的经典组合，网格化信息排布，图表感强，专业可信，适合干货与知识输出。',
    coverGradient: 'linear-gradient(135deg, #1a2a4a 0%, #2e4a7d 60%, #5c7cad 100%)',
    colors: ['#1A2A4A', '#2E4A7D', '#5C7CAD', '#F0F2F5'],
    scenes: ['行业干货', '数据报告', '职场技能', '知识科普'],
    stylePrompt:
      '商务简报风格，深蓝灰白专业配色，网格化信息排版，简洁的图表与数据可视化元素，清晰的信息层级，稳重可信的企业级质感，corporate business infographic style'
  },
  {
    id: 'cute-doodle',
    name: '可爱手绘',
    category: '可爱',
    description: '蜡笔质感的手绘涂鸦、圆滚滚的字体和高明度糖果色，软萌有趣，让人忍不住想点赞。',
    coverGradient: 'linear-gradient(135deg, #ffe0f0 0%, #ffc4d6 50%, #a8e6cf 100%)',
    colors: ['#FFE0F0', '#FFC4D6', '#A8E6CF', '#FFD93D'],
    scenes: ['萌宠日常', '亲子内容', '轻松吐槽', '节日祝福'],
    stylePrompt:
      '可爱手绘涂鸦风格，蜡笔质感线条，糖果色高明度配色，圆润卡通字体，俏皮的小图标与表情装饰，童趣十足的插画元素，软萌治愈氛围，cute hand-drawn doodle style'
  },
  {
    id: 'magazine',
    name: '杂志风',
    category: '高级',
    description: '大标题衬线字体、图文错落的编辑式排版，像时尚杂志内页一样讲究，格调直接拉高。',
    coverGradient: 'linear-gradient(135deg, #f5f0e8 0%, #d8cfc0 55%, #2b2b2b 100%)',
    colors: ['#F5F0E8', '#D8CFC0', '#2B2B2B', '#C0392B'],
    scenes: ['时尚穿搭', '深度长文', '人物专访', '品牌故事'],
    stylePrompt:
      '时尚杂志编辑排版风格，大号衬线标题字体，图文错落的栅格布局，米白纸张质感背景，黑白摄影搭配一抹亮色点缀，精致的分栏与引言设计，editorial magazine layout'
  },
  {
    id: 'dark-luxury',
    name: '暗黑高级',
    category: '高级',
    description: '纯黑底色配金属金线条，克制的光影和大字号排版，神秘、贵气、氛围感极强。',
    coverGradient: 'linear-gradient(135deg, #0a0a0a 0%, #1f1b16 60%, #b8975a 100%)',
    colors: ['#0A0A0A', '#1F1B16', '#B8975A', '#E8DCC8'],
    scenes: ['奢品鉴赏', '高端服务', '夜景大片', '品牌发布'],
    stylePrompt:
      '暗黑高级风格，纯黑背景，金属金色线条点缀，克制的聚光光影，大字号极简排版，细腻的暗纹质感，神秘贵气的氛围感，dark luxury gold accent aesthetic'
  },
  {
    id: 'japanese-fresh',
    name: '日系清新',
    category: '柔和',
    description: '过曝白与淡蓝绿的空气感配色，胶片颗粒与自然元素，像夏日午后的一阵风，清爽舒服。',
    coverGradient: 'linear-gradient(135deg, #eef7f2 0%, #cfe8dc 50%, #a3cfe0 100%)',
    colors: ['#EEF7F2', '#CFE8DC', '#A3CFE0', '#5B8A72'],
    scenes: ['旅行游记', '美食探店', '校园日常', '治愈系分享'],
    stylePrompt:
      '日系清新风格，空气感过曝白与淡蓝绿配色，胶片颗粒质感，自然光线与植物元素，轻盈的细字体排版，通透干净的画面，清爽治愈氛围，japanese fresh film aesthetic'
  },
  {
    id: 'french-retro',
    name: '法式复古',
    category: '高级',
    description: '奶咖色与酒红的复古碰撞，衬线花体字与做旧纹理，慵懒浪漫的法式风情。',
    coverGradient: 'linear-gradient(135deg, #e8d9c5 0%, #c4a484 50%, #7b3f3f 100%)',
    colors: ['#E8D9C5', '#C4A484', '#7B3F3F', '#3E2C2C'],
    scenes: ['咖啡探店', '复古穿搭', '电影书评', '氛围写真'],
    stylePrompt:
      '法式复古风格，奶咖与酒红复古配色，做旧纸张纹理，优雅的衬线花体字，复古边框与印章装饰，慵懒浪漫的胶片色调，french vintage romantic aesthetic'
  },
  {
    id: 'memphis',
    name: '孟菲斯',
    category: '潮流',
    description: '几何图形、波普撞色与俏皮线条的自由拼贴，打破常规，年轻张扬有态度。',
    coverGradient: 'linear-gradient(135deg, #ff6b9d 0%, #ffd93d 45%, #4ecdc4 100%)',
    colors: ['#FF6B9D', '#FFD93D', '#4ECDC4', '#2D2D2D'],
    scenes: ['创意活动', '潮流测评', '观点输出', '青年文化'],
    stylePrompt:
      '孟菲斯设计风格，波普撞色配色，几何图形自由拼贴，俏皮的波浪线与圆点装饰，粗黑描边，活力张扬的构图，年轻潮流的视觉冲击，memphis design pop style'
  },
  {
    id: 'watercolor',
    name: '水彩渐变',
    category: '柔和',
    description: '水彩晕染的柔和渐变，粉紫蓝梦幻交融，边缘自然流动，文艺又带一点仙气。',
    coverGradient: 'linear-gradient(135deg, #fbc2eb 0%, #a6c1ee 60%, #c2e9fb 100%)',
    colors: ['#FBC2EB', '#A6C1EE', '#C2E9FB', '#6B5B95'],
    scenes: ['情感文案', '诗歌摘抄', '手作分享', '星座心理'],
    stylePrompt:
      '水彩晕染风格，粉紫蓝梦幻渐变，柔和的水彩笔触与自然晕开的边缘，纸张纹理底色，轻盈的文艺排版，仙气飘飘的梦幻氛围，dreamy watercolor gradient style'
  },
  {
    id: 'mono-minimal',
    name: '极简黑白',
    category: '简约',
    description: '只用黑白灰三色，靠字重、字号和留白构建张力，冷静克制，越简单越有力量。',
    coverGradient: 'linear-gradient(135deg, #fafafa 0%, #d4d4d4 50%, #171717 100%)',
    colors: ['#FAFAFA', '#D4D4D4', '#525252', '#171717'],
    scenes: ['观点金句', '设计作品', '摄影集', '极简生活'],
    stylePrompt:
      '极简黑白风格，纯黑白灰配色，超大字号粗细对比排版，大面积留白，锐利的几何分割线，冷静克制的现代感，强烈的版式张力，monochrome minimalist typography'
  },
  {
    id: 'guochao',
    name: '国潮新中式',
    category: '潮流',
    description: '朱红与黛青的东方配色，融合祥云、窗棂等传统纹样与现代排版，国风底蕴潮流表达。',
    coverGradient: 'linear-gradient(135deg, #9e2b25 0%, #d4553e 45%, #1f3a44 100%)',
    colors: ['#9E2B25', '#D4553E', '#1F3A44', '#E8D5B7'],
    scenes: ['传统文化', '国货推荐', '节气节日', '茶饮汉服'],
    stylePrompt:
      '国潮新中式风格，朱红黛青东方配色，祥云窗棂等传统纹样点缀，书法字体与现代排版结合，宣纸质感底纹，东方美学构图，大气雅致的国风潮流感，chinese national trend style'
  }
]
