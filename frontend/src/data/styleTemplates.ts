/**
 * 风格模板库 - 预设数据
 *
 * 纯前端静态数据，不依赖后端。
 * 封面全部用 CSS 渐变占位（coverGradient），无需真实图片。
 */

/** 模板分类 */
export type StyleCategory = '简约' | '柔和' | '潮流' | '复古' | '版式' | '商务' | '可爱' | '高级'

/** 分类筛选列表（'全部' 由视图层自行添加） */
export const styleCategories: StyleCategory[] = [
  '简约',
  '柔和',
  '潮流',
  '复古',
  '版式',
  '商务',
  '可爱',
  '高级'
]

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
  // ===== 既有模板（id/name 保持不变，stylePrompt 已打磨） =====
  {
    id: 'ins-minimal',
    name: 'ins 简约',
    category: '简约',
    description: '大量留白、克制的配色与细腻的排版层次，像 Instagram 博主的精致九宫格，安静但有质感。',
    coverGradient: 'linear-gradient(135deg, #fdfcfb 0%, #e2d1c3 100%)',
    colors: ['#FDFCFB', '#E2D1C3', '#B0A695', '#4A4238'],
    scenes: ['个人分享', '穿搭笔记', '生活方式', '摄影作品'],
    stylePrompt:
      'ins风简约设计，奶白、燕麦、浅驼的低饱和大地色，画面留白超过一半，纤细无衬线字体小字号错落排布，亚光纸张质感，柔和漫射的自然光影，干净通透不抢戏的画面气质，克制而高级的构图呼吸感，minimalist instagram aesthetic, airy negative space'
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
      '莫兰迪色系设计，灰粉、灰绿、燕麦灰等蒙了一层雾的低饱和灰调配色，雾面磨砂质感，柔和的色块渐变过渡，优雅松弛的留白排版，细腻的哑光纹理细节，安静不刺眼的高级感氛围，静物油画般的沉稳光线，morandi muted color palette, soft matte texture'
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
      '赛博朋克风格，暗夜都市雨夜街景基调，电光紫、荧光青、霓虹洋红的高对比撞色，发光霓虹灯管线条与全息投影元素，故障艺术错位与扫描线干扰，机械感等宽字体，湿漉漉路面的霓虹倒影，压迫感十足的未来都市氛围，cyberpunk neon glitch aesthetic, holographic glow'
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
      '小红书暖色手账风格，奶油橘、蜜桃粉的暖甜配色，和纸胶带、拍立得贴纸、手撕纸片层叠拼贴，可爱手写体配荧光笔划重点，圆角卡片与虚线框布局，俏皮的小涂鸦与星星爱心装饰，温暖治愈的午后氛围感，warm scrapbook journal style, cozy collage'
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
      '商务简报风格，藏青与雾灰白的专业配色，严谨的网格化分区排版，加粗无衬线大标题与清晰的信息层级，柱状图折线图等数据可视化元素，细线框与简约图标点缀，克制的商务蓝强调色，稳重可信的咨询公司报告质感，corporate business infographic style, data-driven layout'
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
      '可爱手绘涂鸦风格，蜡笔与彩铅质感的粗糙线条，奶黄、粉红、薄荷绿的高明度糖果色，圆滚滚的胖乎乎卡通字体，粗描边小图标与颜文字表情点缀，歪歪扭扭的手绘边框，童趣满满的插画元素，软萌到犯规的治愈氛围，cute hand-drawn doodle style, crayon texture'
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
      '时尚杂志编辑排版风格，超大号优雅衬线标题字体，图文错落的栅格分栏布局，米白铜版纸质感背景，黑白摄影大片搭配一抹正红点缀，精致的引言竖排与页码刊头细节，字距行距讲究的编辑级排印，高冷有格调的画面气场，editorial magazine layout, high fashion typography'
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
      '暗黑高级风格，曜石黑丝绒质感背景，香槟金金属细线条与烫金字体点缀，克制的单点聚光与深邃阴影，超大字号极简排版配大量暗部留白，细腻的暗纹肌理，神秘贵气的博物馆展柜氛围，低调却压场的奢华气质，dark luxury gold accent aesthetic, moody spotlight'
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
      '日系清新风格，微微过曝的空气感白色基调，若竹绿与淡水蓝的清透配色，细腻的胶片颗粒质感，窗边自然光与绿植光影，轻盈的细字体竖排点缀，通透干净像被水洗过的画面，夏日午后微风般的清爽治愈氛围，japanese fresh film aesthetic, airy overexposed light'
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
      '法式复古风格，奶咖、焦糖与勃艮第酒红的复古配色，做旧牛皮纸纹理与磨损边缘，优雅的衬线花体字与手写签名式笔迹，复古邮票边框与火漆印章装饰，昏黄慵懒的胶片暖调，老电影海报般的浪漫颗粒感，french vintage romantic aesthetic, aged paper texture'
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
      '孟菲斯设计风格，桃红、柠檬黄、湖水绿的波普撞色，三角圆形折线等几何图形自由拼贴，俏皮的波浪线与彩色圆点铺底，粗黑描边与错位阴影，倾斜跳跃的活力构图，八十年代波普艺术的张扬能量，年轻叛逆的视觉冲击力，memphis design pop style, playful geometric shapes'
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
      '水彩晕染风格，藕荷粉、雾蓝、薰衣草紫的梦幻渐变交融，湿画法自然晕开的柔软边缘，水彩纸的细腻纹理底色，轻盈的细体文艺排版，飞白笔触与水痕肌理细节，仙气缭绕的朦胧诗意氛围，dreamy watercolor gradient style, soft ink bleed'
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
      '极简黑白风格，纯黑白灰三色体系，超大字号与极小字号的强烈字重对比，瑞士国际主义网格排版，大面积呼吸留白，锐利的几何分割线与色块切割，冷静克制的现代主义气质，靠版式本身制造张力的高级感，monochrome minimalist typography, swiss grid layout'
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
      '国潮新中式风格，朱红、黛青、鎏金的东方配色，祥云、窗棂、回纹等传统纹样与现代几何构成融合，苍劲书法大字与现代黑体混排，宣纸肌理与朱砂印章细节，对称庄重又带潮流解构的构图，大气雅致的东方美学气韵，chinese national trend style, oriental modern fusion'
  },

  // ===== 版式流派：被验证过的爆款版式 =====
  {
    id: 'big-char-impact',
    name: '大字报冲击',
    category: '版式',
    description: '纯色底+占屏七成的超粗黑字，一句扎心话直接怼脸，观点、吐槽、情感文案的流量收割机。',
    coverGradient: 'linear-gradient(135deg, #ffffff 0%, #f5f5f5 55%, #ffd500 100%)',
    colors: ['#FFFFFF', '#111111', '#FFD500', '#FF3B30'],
    scenes: ['观点输出', '情感树洞', '犀利吐槽', '涨粉金句'],
    stylePrompt:
      '大字报冲击风格，纯白或亮黄的干净纯色背景，超大号加粗黑体汉字占据画面绝对主体，关键词用亮黄色荧光块或红色下划线粗暴强调，排版直给不绕弯，几乎没有装饰元素，像热搜词条截图一样的强烈信息压迫感，一秒看懂一秒共鸣，bold typographic poster, oversized chinese characters, high impact headline'
  },
  {
    id: 'sticky-memo',
    name: '便利贴备忘录',
    category: '版式',
    description: '一张张便利贴层层贴出干货清单，自带"记笔记"的收藏暗示，学习自律类内容的收藏率神器。',
    coverGradient: 'linear-gradient(135deg, #fff9db 0%, #ffec99 50%, #ffd43b 100%)',
    colors: ['#FFF9DB', '#FFEC99', '#FFD43B', '#4A4A4A'],
    scenes: ['学习清单', '考研打卡', '自律计划', '干货速记'],
    stylePrompt:
      '便利贴备忘录风格，米黄色方形便利贴层叠错落排布，纸张带微微卷角与柔和投影，手写马克笔字迹配打勾方框清单，回形针、透明胶带、曲别针的固定细节，浅色桌面或软木板底色，像学霸随手记下的高效笔记，让人想马上收藏照做，sticky note memo aesthetic, paper texture, checklist layout'
  },
  {
    id: 'chat-screenshot',
    name: '聊天记录',
    category: '版式',
    description: '绿白对话气泡还原聊天现场，吃瓜感和代入感拉满，讲故事、晒神回复的天选版式。',
    coverGradient: 'linear-gradient(135deg, #ebebeb 0%, #d8f5c8 55%, #95ec69 100%)',
    colors: ['#F5F5F5', '#95EC69', '#FFFFFF', '#333333'],
    scenes: ['情感故事', '闺蜜八卦', '神回复合集', '甲方吐槽'],
    stylePrompt:
      '聊天记录截图风格，浅灰色聊天界面底色，绿色与白色的圆角对话气泡左右交替排布，清晰醒目的聊天字体，圆形头像占位与时间戳细节，关键语句可用红圈或箭头标注，像正在围观一场精彩对话的现场感，真实到让人想往下滑的代入感，chat bubble ui screenshot style, messaging interface'
  },
  {
    id: 'receipt-ticket',
    name: '小票收据',
    category: '版式',
    description: '热敏纸小票逐行列出账目和清单，自带"账本被晒出来"的真实感，记账省钱类内容一贴就火。',
    coverGradient: 'linear-gradient(135deg, #f7f5ef 0%, #ecebe4 60%, #cfcdc2 100%)',
    colors: ['#F7F5EF', '#ECEBE4', '#8C8A80', '#2B2B2B'],
    scenes: ['记账复盘', '省钱攻略', '购物清单', '旅行花费'],
    stylePrompt:
      '收银小票风格，窄长条热敏纸小票版式，等宽打印字体逐行排列条目名称与金额数字，虚线分隔线与顶部底部锯齿撕边细节，微微泛黄的纸张与淡淡油墨打印质感，盖一枚红色印章或手写批注点缀，像一张被晒出来的真实账单，条理清晰又带生活气，receipt ticket print aesthetic, monospace type, thermal paper'
  },
  {
    id: 'newspaper-headline',
    name: '报纸头条',
    category: '版式',
    description: '复古报纸排版配超大号头条标题，把日常小事讲成"重磅新闻"，反差感天然带梗、自带传播。',
    coverGradient: 'linear-gradient(135deg, #f4efe3 0%, #e5dcc7 55%, #1f1f1f 100%)',
    colors: ['#F4EFE3', '#E5DCC7', '#1F1F1F', '#B3261E'],
    scenes: ['影视锐评', '热点盘点', '大事记', '瓜田速报'],
    stylePrompt:
      '复古报纸头条风格，米黄新闻纸底纹带细微油墨颗粒，超大号加粗衬线头条标题横贯版面，分栏正文与黑白网点配图，报头、日期、刊号线框等报纸细节一应俱全，一抹正红盖章标注重磅，用一本正经的新闻排版讲有梗的内容，号外既视感十足，vintage newspaper front page layout, letterpress texture'
  },
  {
    id: 'dictionary-entry',
    name: '词典释义',
    category: '版式',
    description: '一本正经的词典排版解释一个"发疯词条"，严肃壳子装梗内容，反差幽默特别容易被转发。',
    coverGradient: 'linear-gradient(135deg, #fbfaf7 0%, #efece4 60%, #d8d3c4 100%)',
    colors: ['#FBFAF7', '#EFECE4', '#333333', '#C0392B'],
    scenes: ['热词科普', '情感词条', '概念解读', '玩梗造词'],
    stylePrompt:
      '词典释义风格，纸白底色像词典内页，加粗大号词条名配注音符号与词性标注，释义分点排布带例句缩进层级，端正的衬线字体与纤细分割线，重点义项用红色标出，页眉页码等辞书细节，用最严肃的排版讲最离谱的内容，冷面幽默的反差感，dictionary entry layout, editorial typography, scholarly deadpan'
  },
  {
    id: 'ppt-knowledge',
    name: 'PPT 知识卡',
    category: '版式',
    description: '编号+色块+分条的课件式排版，信息密度高又好读，考研干货和方法论内容的收藏加速器。',
    coverGradient: 'linear-gradient(135deg, #eef4ff 0%, #dbe7fd 55%, #3b6fe0 100%)',
    colors: ['#EEF4FF', '#DBE7FD', '#3B6FE0', '#1B2A4A'],
    scenes: ['考研干货', '读书笔记', '方法论', '行业科普'],
    stylePrompt:
      'PPT知识卡片风格，浅蓝白清爽底色，醒目大标题配数字编号图标分区，重点内容装进圆角色块卡片用项目符号分条列出，细线框、箭头流程与简约几何装饰，信息层级一目了然，克制的商务蓝强调色，像一页制作精良的课程课件，看完就想截图保存，clean infographic slide design, structured knowledge card'
  },
  {
    id: 'chalkboard-note',
    name: '黑板手写',
    category: '版式',
    description: '墨绿黑板配粉笔手写划重点，一秒回到课堂的既视感，讲知识点、立老师人设的氛围利器。',
    coverGradient: 'linear-gradient(135deg, #2f4f43 0%, #26433a 60%, #1c332c 100%)',
    colors: ['#2F4F43', '#F5F1E6', '#F2C94C', '#F0A8A8'],
    scenes: ['知识点讲解', '考试划重点', '学习方法', '老师人设'],
    stylePrompt:
      '黑板手写风格，墨绿色黑板底带粉笔灰擦痕质感，白色与黄色粉笔手写字迹粗细自然，重点内容用粉笔方框和波浪下划线圈出，简笔画示意图与箭头标注辅助讲解，木质黑板边框与粉笔头细节，像老师在课堂上划重点的临场感，知识密度与亲切感兼得，chalkboard hand-drawn lecture style, chalk texture'
  },

  // ===== 复古流派：回忆杀与复古未来 =====
  {
    id: 'y2k-vaporwave',
    name: 'Y2K 蒸汽波',
    category: '复古',
    description: '镭射镀铬+粉紫青荧光渐变，千禧年辣妹网页既视感，Z 世代的回忆杀密码，潮流内容流量磁铁。',
    coverGradient: 'linear-gradient(135deg, #ff71ce 0%, #b967ff 45%, #01cdfe 100%)',
    colors: ['#FF71CE', '#B967FF', '#01CDFE', '#05FFA1'],
    scenes: ['千禧穿搭', '复古数码', 'CD 唱片安利', '剧综回忆杀'],
    stylePrompt:
      'Y2K蒸汽波风格，粉紫青的荧光渐变天空底色，镭射全息与镀铬金属质感字体，像素爱心、闪烁星星、老式电脑弹窗等千禧元素拼贴，光碟彩虹反光与网格地平线，梦核滤镜般的迷幻光晕，复古未来交织的千禧年辣妹网页既视感，y2k vaporwave chrome aesthetic, holographic retro futurism'
  },
  {
    id: 'polaroid-plog',
    name: '拍立得 plog',
    category: '复古',
    description: '白边相纸+手写日期+胶片颗粒，把日常拍成值得收藏的纪念，旅行和生活记录的氛围感首选。',
    coverGradient: 'linear-gradient(135deg, #fdfbf7 0%, #e8ddcb 55%, #a8b29b 100%)',
    colors: ['#FDFBF7', '#E8DDCB', '#A8B29B', '#4A4238'],
    scenes: ['旅行记录', '日常 plog', '宠物随拍', '约会纪念'],
    stylePrompt:
      '拍立得相纸风格，白色宽边相纸框住主画面，暖调复古的胶片显色与细腻颗粒，轻微漏光与褪色边缘，白边上手写日期与马克笔涂鸦标注，几张拍立得随性叠放错落，配纸胶带和小贴纸固定，把平凡日常拍出值得夹进相册的纪念感，polaroid instant film plog aesthetic, nostalgic snapshot'
  },
  {
    id: 'pixel-8bit',
    name: '像素游戏厅',
    category: '复古',
    description: '8bit 像素字+游戏机 UI 边框，红白机时代的电子回忆杀，游戏二次元内容的天然皮肤。',
    coverGradient: 'linear-gradient(135deg, #1a1a2e 0%, #16213e 50%, #e94560 100%)',
    colors: ['#1A1A2E', '#16213E', '#E94560', '#4DEEEA'],
    scenes: ['游戏测评', '二次元安利', '复古数码', '整活企划'],
    stylePrompt:
      '8bit像素风格，深蓝夜色的像素点阵背景，马赛克像素字体与游戏机对话框UI边框，血条、金币、方向键、马赛克云朵等复古游戏元素，高饱和红与电子青的点缀色，CRT屏幕扫描线与轻微色散质感，像投币开机的街机游戏标题画面，电子考古的怀旧兴奋感，retro 8-bit pixel game aesthetic, arcade screen'
  },

  // ===== 潮流流派：近年验证过的爆款视觉 =====
  {
    id: 'acid-design',
    name: '酸性设计',
    category: '潮流',
    description: '黑底酸绿+液态金属+扭曲字体，地下俱乐部的先锋气质，潮流音乐球鞋内容一用就出片。',
    coverGradient: 'linear-gradient(135deg, #0d0d0d 0%, #39ff14 55%, #c8ff00 100%)',
    colors: ['#0D0D0D', '#39FF14', '#C8FF00', '#B5B5B5'],
    scenes: ['音乐现场', '潮流企划', '球鞋上脚', '先锋话题'],
    stylePrompt:
      '酸性设计风格，纯黑背景上流动的酸性绿与荧光柠檬黄，液态金属镀铬图形与镜面反光质感，扭曲拉伸变形的实验性字体，条形码、警示标签、废土贴纸等元素堆叠，锋利又迷幻的视觉张力，地下俱乐部海报的反叛先锋气质，acid graphics liquid chrome aesthetic, experimental typography'
  },
  {
    id: 'dopamine-pop',
    name: '多巴胺快乐',
    category: '潮流',
    description: '糖果粉明黄天蓝大色块撞在一起，快乐浓度超标，穿搭好物和好心情内容的点赞收割机。',
    coverGradient: 'linear-gradient(135deg, #ff5d8f 0%, #ffb703 45%, #4cc9f0 100%)',
    colors: ['#FF5D8F', '#FFB703', '#4CC9F0', '#9B5DE5'],
    scenes: ['元气穿搭', '好心情日常', '开箱好物', '夏日企划'],
    stylePrompt:
      '多巴胺配色风格，糖果粉、明黄、天蓝、紫罗兰的高明度高饱和撞色，大色块拼接的活泼背景，圆润粗体字配白色描边，笑脸、爱心、波点、彩虹条纹的俏皮小元素，光滑的糖果质感与轻微立体阴影，扑面而来的快乐能量，看一眼心情就变好的元气浓度，dopamine colorful pop styling, candy color blocking'
  },
  {
    id: 'neo-ugly',
    name: '新丑风',
    category: '潮流',
    description: '故意土、故意乱、故意不讲道理的排版，土到极致就是潮，搞笑吐槽和暴论内容的抽象搭子。',
    coverGradient: 'linear-gradient(135deg, #f2ff00 0%, #ff5c00 50%, #0038ff 100%)',
    colors: ['#F2FF00', '#FF5C00', '#0038FF', '#111111'],
    scenes: ['搞笑整活', '暴论输出', '离谱测评', '自嘲日常'],
    stylePrompt:
      '新丑风设计，故意打破美学常规的粗野排版，高饱和荧光黄、橙、蓝的生硬撞色，字体大小粗细随意混搭并倾斜错位，默认宋体黑体混用配粗黑描边，艺术字阴影渐变等过时效果反向运用，元素堆叠不讲道理，土到极致反而潮的抽象喜感，一眼记住的怪诞冲击，intentionally ugly anti-design aesthetic, chaotic vernacular layout'
  },
  {
    id: 'inflated-3d',
    name: '3D 膨胀',
    category: '潮流',
    description: '充气气球质感的圆胖立体字，软乎乎想上手捏一把，节日海报和萌系安利的吸睛新宠。',
    coverGradient: 'linear-gradient(135deg, #ffd6e8 0%, #c7b9ff 50%, #9ad0ff 100%)',
    colors: ['#FFD6E8', '#C7B9FF', '#9AD0FF', '#6C5CE7'],
    scenes: ['节日祝福', '谷子晒单', '萌系安利', '活动海报'],
    stylePrompt:
      '3D膨胀风格，充气气球质感的圆胖立体字体饱满鼓起，奶油粉、香芋紫、天蓝的柔和渐变色，表面带柔软高光与哑光反射，圆滚滚的3D小物件漂浮环绕，果冻般的弹性质感与轻盈悬浮构图，软乎乎想伸手捏一把的治愈触感，可爱与科技感兼得，inflated 3d balloon typography, soft blow-up render'
  },
  {
    id: 'klein-blue',
    name: '克莱因蓝',
    category: '潮流',
    description: '一整面浓烈纯粹的克莱因蓝配大号白字，美术馆级别的色彩冲击，金句和高级感封面直接封神。',
    coverGradient: 'linear-gradient(135deg, #002fa7 0%, #0038c4 60%, #001d66 100%)',
    colors: ['#002FA7', '#FFFFFF', '#F5F5F0', '#FF6B00'],
    scenes: ['金句海报', '艺术分享', '数码新品', '高级感封面'],
    stylePrompt:
      '克莱因蓝风格，整面纯粹浓烈的克莱因蓝背景铺满画面，大号白色粗黑体文字居中或错落排布，极少量橙色小面积点睛制造张力，构图克制到只留必要元素，细腻的哑光蓝色质感，浓烈单色带来的美术馆装置般艺术气场，过目不忘的色彩冲击，international klein blue minimal poster, monochrome bold statement'
  },
  {
    id: 'fitness-fluoro',
    name: '荧光燃脂',
    category: '潮流',
    description: '炭黑底+高压荧光绿+超粗斜体数字，热血程度拉满，健身打卡和减脂内容的肾上腺素皮肤。',
    coverGradient: 'linear-gradient(135deg, #101010 0%, #1c1c1c 50%, #ccff00 100%)',
    colors: ['#101010', '#CCFF00', '#FFFFFF', '#3D3D3D'],
    scenes: ['健身打卡', '减脂餐记录', '体态对比', '运动装备'],
    stylePrompt:
      '荧光运动风格，炭黑磨砂背景配高压荧光绿点亮画面，硬朗的斜切分区版式，超粗斜体数字与冲击力标题字，速度线、心率折线、计时器等运动元素，汗水水珠与肌肉光影的力量质感，健身房射灯般的高对比打光，热血沸腾到想立刻去练的燃感，fluorescent fitness energy aesthetic, dynamic athletic layout'
  },

  // ===== 柔和流派：新一代治愈系配色 =====
  {
    id: 'cream-style',
    name: '奶油风',
    category: '柔和',
    description: '奶白杏色焦糖的温柔奶油色系，自带黄油甜香的松弛感，家居改造和好物开箱的高赞常客。',
    coverGradient: 'linear-gradient(135deg, #fdf6ec 0%, #f5e6d3 50%, #e7cdb5 100%)',
    colors: ['#FDF6EC', '#F5E6D3', '#E7CDB5', '#B98A65'],
    scenes: ['家居改造', '租房布置', '好物开箱', '婚礼灵感'],
    stylePrompt:
      '奶油风设计，奶白、杏色、浅焦糖的温柔奶油色系层层过渡，柔和的圆角卡片与奶油肌理质感，细腻的暖调光线像午后阳光洒进客厅，圆润亲切的字体排版，微微的奶油堆叠立体感，弥漫着黄油甜香般的松弛治愈氛围，cream style cozy aesthetic, warm buttery tones'
  },
  {
    id: 'mint-mambo',
    name: '薄荷曼波',
    category: '柔和',
    description: '薄荷绿+奶白的清透配色配水波纹质感，自带降温体感，春夏穿搭和清爽饮品的流量密码。',
    coverGradient: 'linear-gradient(135deg, #e8fff4 0%, #b8f0d8 50%, #6fcfb2 100%)',
    colors: ['#E8FFF4', '#B8F0D8', '#6FCFB2', '#2E6E5E'],
    scenes: ['春夏穿搭', '清爽饮品', 'citywalk', '护肤好物'],
    stylePrompt:
      '薄荷曼波风格，薄荷绿、青瓷绿、奶白的清透配色，水波纹与果冻质感的柔软元素，轻盈灵动的曲线排版与流动线条，气泡、冰块、露珠的沁凉细节，通透的浅色光感像清晨的风，含了一颗薄荷糖般自带降温体感的清爽治愈，mint mambo fresh aesthetic, cool jelly texture'
  },
  {
    id: 'glazed-beauty',
    name: '水光镜面',
    category: '柔和',
    description: '珍珠粉底色+玻璃光泽高光，水润到能掐出水的美妆大片质感，美妆护肤内容的精致滤镜。',
    coverGradient: 'linear-gradient(135deg, #ffe9f0 0%, #ffd3e2 45%, #f2b8ce 100%)',
    colors: ['#FFE9F0', '#FFD3E2', '#F2B8CE', '#A64D79'],
    scenes: ['美妆教程', '护肤测评', '仿妆安利', '发型灵感'],
    stylePrompt:
      '水光镜面美妆风格，珍珠粉与裸粉的柔雾底色，玻璃光泽的水润高光质感，镜面反射与水珠特写的晶莹细节，柔焦光晕像打了环形补光灯，优雅的细体字排版点缀，奶油肌与水光唇的精致氛围，像美妆杂志大片一样透亮细腻的画面，glazed glossy beauty editorial, dewy glass skin aesthetic'
  },

  // ===== 简约流派 =====
  {
    id: 'glassmorphism',
    name: '玻璃拟态',
    category: '简约',
    description: '磨砂半透明玻璃卡片悬浮在渐变上，苹果发布会级别的通透未来感，数码测评的高级感外挂。',
    coverGradient: 'linear-gradient(135deg, #dfe9f3 0%, #c8d8ee 50%, #a9c0e8 100%)',
    colors: ['#DFE9F3', '#FFFFFF', '#A9C0E8', '#4A6FA5'],
    scenes: ['数码测评', 'App 推荐', '效率工具', '桌面分享'],
    stylePrompt:
      '玻璃拟态风格，浅蓝紫的柔和渐变背景，磨砂半透明玻璃卡片悬浮错落排布，细腻的白色细描边与柔和弥散投影，通透的毛玻璃模糊层次感，克制的无衬线字体与简约图标，光线穿过玻璃的微妙折射高光，干净轻盈的未来感界面质感，frosted glassmorphism aesthetic, translucent ui cards'
  },

  // ===== 可爱流派：垂类萌系 =====
  {
    id: 'pet-sticker',
    name: '萌宠贴纸',
    category: '可爱',
    description: '爪印贴纸+白描边宠物照+圆嘟嘟手写字，毛茸茸治愈感直击铲屎官，宠物内容的点赞磁铁。',
    coverGradient: 'linear-gradient(135deg, #fff4e0 0%, #ffe0b8 50%, #ffc48c 100%)',
    colors: ['#FFF4E0', '#FFE0B8', '#FFC48C', '#8C5A3C'],
    scenes: ['猫狗日常', '萌宠好物', '云吸猫', '宠物用品测评'],
    stylePrompt:
      '萌宠贴纸风格，奶橘色的温暖底色，爪印、骨头、小鱼干贴纸散落点缀，宠物主体配白色贴纸描边像被剪下来的可爱周边，圆嘟嘟的手写字体与对话气泡吐槽，毛茸茸的绒毛质感细节，太阳晒过被窝般的治愈氛围，铲屎官看了走不动道的萌度，cute pet sticker collage style, fluffy heartwarming vibe'
  },
  {
    id: 'milky-baby',
    name: '奶 fufu 亲子',
    category: '可爱',
    description: '奶粉色配婴儿蓝的软糯配色，棉花云朵般安心柔软，母婴育儿内容的温柔氛围担当。',
    coverGradient: 'linear-gradient(135deg, #fdf1f3 0%, #fbdce4 50%, #cfe6f5 100%)',
    colors: ['#FDF1F3', '#FBDCE4', '#CFE6F5', '#E8A0B4'],
    scenes: ['母婴好物', '辅食记录', '成长日记', '待产清单'],
    stylePrompt:
      '奶fufu亲子风格，奶粉色与婴儿蓝的软糯马卡龙配色，棉花云朵、星星月亮、小鸭子的温柔小元素，圆润无棱角的卡片与泡泡字体，针织毛线与纯棉织物的柔软材质质感，清晨般柔和干净的光线，像婴儿房一样安心松软的氛围，soft pastel baby aesthetic, milky cotton texture'
  },
  {
    id: 'anime-goods',
    name: '吃谷二次元',
    category: '可爱',
    description: '吧唧立牌+闪粉星星+镭射膜光泽，痛 culture 美学浓度超标，晒谷安利新番一发就有同好来蹲。',
    coverGradient: 'linear-gradient(135deg, #ffe3f1 0%, #e6d6ff 50%, #c9e7ff 100%)',
    colors: ['#FFE3F1', '#E6D6FF', '#C9E7FF', '#FF6FA5'],
    scenes: ['谷子晒单', '痛包展示', '漫展打卡', '新番安利'],
    stylePrompt:
      '吃谷二次元风格，粉紫蓝的梦幻渐变底色，吧唧徽章、亚克力立牌、卡套等谷子元素精致陈列排布，闪粉星星与镭射膜的流光泽感，日系漫画网点纹与速度线装饰，蕾丝丝带花边点缀，可爱浓度爆表的痛culture美学，少女心与xp值同时拉满，anime goods kawaii collage style, sparkly ita-bag aesthetic'
  },

  // ===== 商务流派：垂类专业感 =====
  {
    id: 'resume-clean',
    name: '职场简历',
    category: '商务',
    description: '分栏+时间线的简历式排版，HR 一眼觉得靠谱的专业气质，求职攻略和职场干货的信任加成。',
    coverGradient: 'linear-gradient(135deg, #f7f9fb 0%, #e8eef4 55%, #2c3e50 100%)',
    colors: ['#F7F9FB', '#E8EEF4', '#2C3E50', '#2F80ED'],
    scenes: ['求职攻略', '简历模板', '面试经验', '职场晋升'],
    stylePrompt:
      '职场简历风格，灰白干净底色配深灰蓝主色，清晰的左右分栏与垂直时间线排版，细分割线与简约线性小图标标注，专业无衬线字体层级分明，姓名头衔式的大标题区块，一抹商务蓝强调关键信息，严谨利落让HR眼前一亮的专业气质，professional resume layout, clean corporate design'
  },
  {
    id: 'money-green',
    name: '理财绿金',
    category: '商务',
    description: '墨绿丝绒底+金色数字图表，银行级的稳重富贵感，理财搞钱内容让人觉得"跟着学能赚到"。',
    coverGradient: 'linear-gradient(135deg, #0e3b2e 0%, #14523f 55%, #d4af37 100%)',
    colors: ['#0E3B2E', '#14523F', '#D4AF37', '#F4EFE3'],
    scenes: ['理财入门', '基金复盘', '省钱心得', '搞钱思维'],
    stylePrompt:
      '理财绿金风格，墨绿丝绒质感的深色背景，金色细线图表与上升箭头曲线，衬线体金色数字大而醒目，纸币安全纹与硬币浮雕元素低调点缀，烫金分割线与徽章式边框，银行金库般的稳重与富贵气场，看着就觉得靠谱能搞到钱的可信感，money green gold finance aesthetic, wealth premium look'
  },
  {
    id: 'auto-metal',
    name: '硬核机械',
    category: '商务',
    description: '碳纤维纹理+拉丝金属+超粗斜体参数，马力与荷尔蒙齐飞，汽车机车数码硬件的气场皮肤。',
    coverGradient: 'linear-gradient(135deg, #17191c 0%, #2a2e33 55%, #c0c5cc 100%)',
    colors: ['#17191C', '#2A2E33', '#C0C5CC', '#E63946'],
    scenes: ['新车测评', '自驾装备', '改装分享', '驾照攻略'],
    stylePrompt:
      '硬核机械风格，碳纤维纹理的深灰黑背景，拉丝金属与镀铬件的冷冽质感，硬朗的斜切分区线条与工业标尺刻度元素，超粗斜体数字与参数化表格排版，一抹机能红警示色点缀，车库射灯下的金属反光，速度马力与机械荷尔蒙的硬核气场，automotive industrial metal aesthetic, carbon fiber texture'
  },

  // ===== 高级流派：新一代氛围感 =====
  {
    id: 'maillard-brown',
    name: '美拉德',
    category: '高级',
    description: '焦糖栗棕摩卡像烤面包一样层层上色，浓郁又松弛的秋冬氛围，穿搭咖啡内容的高级感buff。',
    coverGradient: 'linear-gradient(135deg, #e6c9a8 0%, #b5825a 50%, #6b4226 100%)',
    colors: ['#E6C9A8', '#B5825A', '#6B4226', '#3B2417'],
    scenes: ['秋冬穿搭', '咖啡日常', '复古街拍', '氛围感写真'],
    stylePrompt:
      '美拉德色系风格，焦糖、栗棕、摩卡的烘焙暖棕配色，像面包烤上色一样层层递进的棕调渐变，麂皮、羊绒、灯芯绒的秋冬材质质感，夕阳斜照的慵懒暖调光影，复古衬线字体与暗金点缀，咖啡香气般浓郁又松弛的高级氛围，maillard warm brown tone aesthetic, autumn cozy elegance'
  },
  {
    id: 'midnight-gourmet',
    name: '深夜食欲',
    category: '高级',
    description: '暗调背景+暖橙聚光打在食物上，锅气和酱汁油光隔屏溢出，美食探店深夜放毒的爆款配方。',
    coverGradient: 'linear-gradient(135deg, #171310 0%, #2c1f14 55%, #d97b29 100%)',
    colors: ['#171310', '#2C1F14', '#D97B29', '#F2C14E'],
    scenes: ['美食探店', '深夜放毒', '菜谱教程', '招牌菜安利'],
    stylePrompt:
      '深夜食欲风格，暗调黑棕背景把食物衬成绝对主角，暖橙色聚光像深夜大排档的灯，油亮酱汁的反光与热气腾腾的锅气质感，食材纹理与酥脆断面的诱人特写感，大字号菜名配一行手写体点缀，色香味隔着屏幕溢出来的放毒级食欲，dark moody food photography style, appetizing warm glow'
  }
]
