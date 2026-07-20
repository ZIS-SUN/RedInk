<div align="center">

**中文 | [English](./README.md)**

[![GitHub Stars](https://img.shields.io/github/stars/HisMax/RedInk?style=flat&logo=github)](https://github.com/HisMax/RedInk)
[![License](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-blue)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Docker Pulls](https://img.shields.io/docker/pulls/histonemax/redink)](https://hub.docker.com/r/histonemax/redink)
[![GitHub Release](https://img.shields.io/github/v/release/HisMax/RedInk?include_prereleases)](https://github.com/HisMax/RedInk/releases)

<img src="images/2.png" alt="红墨 - 灵感一触即发 让创作从未如此简单" width="600"/>

## 红墨官方站点上线啦，注册即送50体验积分！

## 注册需要邀请码！可以到 https://watcha.cn/square/discuss#post_id=1380 获取

<div align="center">
<a href="https://redink.top">
  <img src="images/redink.png" alt="红墨在线体验" width="500" style="border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.1);"/>
</a>

#### [点击访问在线体验站 → Redink.top](https://redink.top)


</div>

<img src="images/showcase-grid.png" alt="使用红墨生成的各类小红书封面" width="700" style="border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);"/>

<sub>*使用红墨生成的各类小红书封面 - AI驱动，风格统一，文字准确*</sub>

</div>

---

## ✨ 效果展示

### 输入一句话，生成完整图文

首页提供**示例主题**一键填入，帮新手快速开始；创作过的内容会以**最近作品**形式展示在首页，点击即可回访，也可跳转「我的创作」查看全部。

<details open>
<summary><b>Step 1: 智能大纲生成</b></summary>

<br>

![大纲示例](./images/example-2.png)

**功能特性：**
- ✏️ 可编辑每页内容
- 🔄 可调整页面顺序（不建议）
- ✨ 自定义每页描述（强烈推荐）

</details>

<details open>
<summary><b>🎨 Step 2: 封面页生成</b></summary>

<br>

![封面示例](./images/example-3.png)

**封面亮点：**
- 🎯 符合个人风格
- 📝 文字准确无误
- 🌈 视觉统一协调

</details>

<details open>
<summary><b>📚 Step 3: 内容页批量生成</b></summary>

<br>

![内容页示例](./images/example-4.png)

**生成说明：**
- ⚡ 并发生成所有页面（默认最多 15 张）
- ⚠️ 如 API 不支持高并发，请在设置中关闭
- 🔧 支持单独重新生成不满意的页面
- 📊 生成过程实时可视化：每张图卡显示排队中 / 生成中 / 已完成 / 生成失败四种状态，生成中的图卡带单图进度条与已用时长
- ⏱️ 总进度平滑推进，并按本次已完成图片的实际耗时动态估算预计剩余时间；失败的图片可一键批量重新生成

</details>

---

## 🧰 创作工具箱

除了「一句话生成图文」的主创作流程，侧边栏「创作工具」还提供一整套围绕自媒体创作的提效工具，按创作动线分阶段编排：

| 阶段 | 工具 | 说明 |
|------|------|------|
| **找灵感** | 选题灵感 | 输入你的赛道，AI 生成一批带切入角度、内容形式与热度预估的选题；可开启「结合我的账号数据」，把数据复盘中录入的真实表现注入选题；选中的选题会携带切入角度与建议标签一键进入创作 |
| | 对标拆解 | 粘贴爆款内容或网页链接，拆解它为什么火（钩子/结构/情绪/受众），并按同款套路生成原创草稿；仿写草稿 / 结构模板可一键送入创作中心自动转成大纲；最近 20 次拆解本地存档，随时找回 |
| **写文案** | 爆款标题 | 生成一批带吸引力评分与爆款要素标注的候选标题 |
| | 多平台改写 | 一段文案一键改写成小红书 / 抖音 / 公众号 / B站 / 微博风格；改写结果可一键送入创作中心转成图文大纲 |
| | 评论助手 | 粘贴粉丝评论，生成高互动神回复与置顶引导评论 |
| **定风格・做视觉** | 品牌记忆 | 管理个人 IP / 品牌档案（语气、口头禅、签名、禁用词等），保持人设一致 |
| | 风格模板 | 精选视觉风格库（支持自定义），一键应用到图片生成 |
| | 封面 A/B | 一个主题生成多个封面方向，并排对比预估点击力 |
| **生成・导出** | 链接转图文 | 粘贴网页链接或长文，自动提炼成多页图文大纲并送入创作流程 |
| | 多尺寸导出 | 一张图适配 9:16 / 1:1 / 3:4 / 公众号头图 / B站封面等多平台尺寸并批量下载 |
| **排期・复盘** | 内容日历 | 规划各平台发布节奏，管理内容计划与状态；条目支持发布时间与关联作品（历史记录「加入内容日历」自动关联，可跳转查看）；新建条目时按你的账号数据推荐最佳发布时段；「AI 排期」一键生成一周内容计划（可结合账号数据，预览勾选后入库） |
| | 数据复盘 | 手动录入或从 Excel / CSV 批量粘贴导入已发布数据（表头自动识别，「1.2万」等数字自动换算），查看 SVG 趋势 / 对比图表与发布时段分析，并获取 AI 复盘洞察 |

> 说明：**品牌人设**与**视觉风格**会贯穿主创作流程——设置后，大纲、正文、标题及图片生成都会自动套用。文案类工具依赖已配置的文本模型，视觉/数据类工具（风格模板、多尺寸导出、品牌记忆、内容日历、数据复盘）多数无需模型即可使用。
>
> 对标拆解的「网页链接」模式仅支持公开可访问的文章页面，小红书 / 抖音等 App 内的链接通常无法直接抓取，建议切换到「粘贴内容」模式复制正文。

---

## 🎛️ 精修与自定义

生成不是终点——从大纲到成品，每个环节都可以继续打磨：

### ✍️ 大纲页

- **单页 AI 润色**：每页大纲支持「润色 / 精简 / 更抓眼球」三种一键优化，结果先对比预览，满意再应用，不满意可直接放弃

### 🖼️ 结果页

- **编辑文字**：每张卡片支持「编辑文字」，可选择仅保存文案，或保存并重画该页图片
- **标题 / 文案 / 标签 inline 编辑**：候选标题、发布文案与标签均可直接点击编辑，编辑结果会随作品保存到历史记录
- **爆款体检**：结果页 →「爆款体检」，AI 以爆款潜力为标准给成品打分——0-100 总分 + 五个维度（封面钩子 / 标题吸引力 / 内容结构 / 情绪价值 / 行动引导）逐项点评，并给出最多 5 条按影响力排序的修改建议；带改写文本的建议可一键应用到对应页面或发布文案
- **一键发布包**：「一键下载」的 zip 升级为发布包，除全部图片外还附带「发布文案.txt」（标题候选 / 正文文案 / 标签 / 大纲原文），发布时直接复制粘贴
- **多尺寸导出入口**：结果页顶部新增「多尺寸导出」按钮，直达多尺寸导出工具适配各平台尺寸

### 🗂️ 历史记录页（我的创作）

- **批量管理**：进入批量模式后可多选 / 本页全选，支持批量下载与批量删除（删除带实时进度提示）
- **状态筛选**：按 全部 / 已完成 / 部分完成 / 草稿箱 / 失败 筛选创作记录
- **加入内容日历**：任意作品可一键加入内容日历，自动与日历条目关联

### ⚙️ 设置页

- **图片生成参数**：可配置图片并发数（1-8）、图片尺寸（OpenAI 兼容接口）与宽高比（Google GenAI 接口）
- **图片生成 Prompt 模板**：整套画图指令模板可完全自定义（支持页面文案 / 页面类型 / 用户主题 / 完整大纲等占位符），随时可一键恢复默认

---

## 🏗️ 技术架构

<table>
<tr>
<td width="50%" valign="top">

### 🔧 后端技术栈

| 技术 | 说明 |
|------|------|
| **语言** | Python 3.11+ |
| **框架** | Flask |
| **包管理** | uv |
| **文案AI** | Gemini 3 |
| **图片AI** | 🍌 Nano banana Pro |

</td>
<td width="50%" valign="top">

### 🎨 前端技术栈

| 技术 | 说明 |
|------|------|
| **框架** | Vue 3 + TypeScript |
| **构建工具** | Vite |
| **状态管理** | Pinia |
| **样式** | Modern CSS |

</td>
</tr>
</table>

---

## 📦 如何自己部署

### 方式一：Docker 部署（推荐）

**最简单的部署方式，一行命令即可启动：**

```bash
docker run -d -p 12398:12398 -v ./history:/app/history -v ./output:/app/output histonemax/redink:latest
```

访问 http://localhost:12398，在 Web 界面的**设置页面**配置你的 API Key 即可使用。

**使用 docker-compose（可选）：**

下载 [docker-compose.yml](https://github.com/HisMax/RedInk/blob/main/docker-compose.yml) 后：

```bash
docker-compose up -d
```

**Docker 部署说明：**
- 容器内不包含任何 API Key，需要在 Web 界面配置
- 使用 `-v ./history:/app/history` 持久化历史记录
- 使用 `-v ./output:/app/output` 持久化生成的图片
- 可选：挂载自定义配置文件 `-v ./text_providers.yaml:/app/text_providers.yaml`

---

### 方式二：本地开发部署

**前置要求：**
- Python 3.11+
- Node.js 18+
- pnpm
- uv

### 1. 克隆项目
```bash
git clone https://github.com/HisMax/RedInk.git
cd RedInk
```

### 2. 配置 API 服务

复制配置模板文件：
```bash
cp text_providers.yaml.example text_providers.yaml
cp image_providers.yaml.example image_providers.yaml
```

编辑配置文件，填入你的 API Key 和服务配置。也可以启动后在 Web 界面的**设置页面**进行配置。

### 3. 安装后端依赖
```bash
uv sync
```

### 4. 安装前端依赖
```bash
cd frontend
pnpm install
```

### 5. 启动服务

#### 一键启动（推荐）

双击运行启动脚本，自动安装依赖并启动前后端：

- **macOS**: `start.sh` 或双击 `scripts/start-macos.command`
- **Linux**: `./start.sh`
- **Windows**: 双击 `start.bat`

启动后自动打开浏览器访问 http://localhost:5173

#### 手动启动

**启动后端:**
```bash
uv run python -m backend.app
```
访问: http://localhost:12398

**启动前端:**
```bash
cd frontend
pnpm dev
```
访问: http://localhost:5173

---

### 方式三：macOS 桌面版

红墨可以打包成原生 macOS 桌面应用（pywebview 原生窗口 + PyInstaller 打包为 `dist/RedInk.app`），像普通 App 一样双击使用：

- 🖥️ 原生窗口与应用图标，无需打开浏览器
- 🔔 图片生成完成 / 失败时发送 macOS 系统通知
- 📐 自动记忆窗口大小与位置，下次打开保持上次的布局

构建步骤详见 [BUILD_DESKTOP.md](./BUILD_DESKTOP.md)。

---

## 🔧 配置说明

### 配置方式

项目支持两种配置方式：

1. **Web 界面配置（推荐）**：启动服务后，在设置页面可视化配置
2. **YAML 文件配置**：直接编辑配置文件

### 文本生成配置

配置文件: `text_providers.yaml`

```yaml
# 当前激活的服务商
active_provider: openai

providers:
  # OpenAI 官方或兼容接口
  openai:
    type: openai_compatible
    api_key: sk-xxxxxxxxxxxxxxxxxxxx
    base_url: https://api.openai.com/v1
    model: gpt-4o

  # Google Gemini（原生接口）
  gemini:
    type: google_gemini
    api_key: AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
    model: gemini-2.0-flash
```

### 图片生成配置

配置文件: `image_providers.yaml`

```yaml
# 当前激活的服务商
active_provider: gemini

providers:
  # Google Gemini 图片生成
  gemini:
    type: google_genai
    api_key: AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
    model: gemini-3-pro-image-preview
    high_concurrency: false  # 高并发模式

  # OpenAI 兼容接口
  openai_image:
    type: image_api
    api_key: sk-xxxxxxxxxxxxxxxxxxxx
    base_url: https://your-api-endpoint.com
    model: dall-e-3
    high_concurrency: false
```

### 高并发模式说明

- **关闭（默认）**：图片逐张生成，适合 GCP 300$ 试用账号或有速率限制的 API
- **开启**：图片并行生成（最多15张同时），速度更快，但需要 API 支持高并发

⚠️ **GCP 300$ 试用账号不建议启用高并发**，可能会触发速率限制导致生成失败。

---

## ⚠️ 注意事项

1. **API 配额限制**:
   - 注意 Gemini 和图片生成 API 的调用配额
   - GCP 试用账号建议关闭高并发模式

2. **生成时间**:
   - 大纲生成通常需要 15-30 秒，请稍候
   - 图片生成需要时间,请耐心等待（不要离开页面）

---

## 🤝 参与贡献

欢迎提交 Issue 和 Pull Request!

如果这个项目对你有帮助,欢迎给个 Star ⭐


---

## 更新日志

### 未发布（Unreleased）
- ✨ 生成页实时进度可视化：排队 / 生成中 / 完成 / 失败四态图卡、单图进度条与已用时长、总进度平滑推进、按实际耗时动态估算预计剩余时间
- ✨ 新增 macOS 桌面版：pywebview 原生窗口 + PyInstaller 打包 `dist/RedInk.app`，含应用图标、生成完成 / 失败原生通知、窗口大小位置记忆（构建见 BUILD_DESKTOP.md）
- ✨ 结果页新增「编辑文字」：单页文案可仅保存或保存并重画；标题 / 文案 / 标签支持 inline 编辑并随作品保存到历史记录
- ✨ 大纲页新增单页 AI 润色：润色 / 精简 / 更抓眼球，先对比预览再应用
- ✨ 设置页支持配置图片并发数（1-8）、图片尺寸与宽高比，图片生成 Prompt 模板可整体自定义并一键恢复默认
- ✨ 结果页新增「爆款体检」：AI 审稿给出 0-100 总分、五维度点评与最多 5 条修改建议，带改写文本的建议可一键应用
- ✨ 数据复盘升级：Excel / CSV 批量粘贴导入（表头自动识别、「万」自动换算）、SVG 趋势与对比图表、发布时段分析与最佳时段结论
- ✨ 对标拆解升级：支持网页链接直接拆解，仿写草稿 / 结构模板一键送创作中心转大纲，最近 20 次拆解本地存档
- ✨ 选题升级：「结合我的账号数据」注入真实表现数据，选题携带角度与标签流转，多平台改写结果可一键送创作中心
- ✨ 一键发布包：结果页标题 / 文案 / 标签随作品存入历史记录，zip 下载升级为发布包并附带「发布文案.txt」（标题候选 / 正文 / 标签 / 大纲），结果页新增「多尺寸导出」入口
- ✨ 内容日历升级：计划条目支持发布时间与关联作品（历史记录「加入内容日历」自动关联、条目可跳转查看），新建条目按账号数据推荐最佳发布时段，「AI 排期」一键生成一周内容计划（可结合账号数据，预览勾选后入库）
- ✨ 历史记录批量管理：批量模式多选 / 本页全选、批量删除（带进度）、批量下载，状态筛选补全为 全部 / 已完成 / 部分完成 / 草稿箱 / 失败
- ✨ 首页新手体验：示例主题一键填入，「最近作品」快捷回访入口

### v1.4.3 (2026-06-30)
- ✨ 用户没有指定页数时，大纲默认改为 5 页
- ✨ 大纲生成中新增更明确的等待提示：这一步大概要 15-30 秒
- 🏗️ 图片服务商链路模块化：新增 Provider 策略、上游 API Client、响应解析器、限流器和历史图片合并器
- 🔧 修复 GPT Image 与 Nano Banana 兼容图片接口：默认不发送 `response_format`，同时支持 `b64_json`、data URL 和临时图片 URL
- 🔧 新增基于历史记录的生成恢复逻辑，刷新或重进页面不会重复消耗上游额度
- 🔧 保护历史记录图片列表，避免空数组覆盖已有图片，避免已完成/部分完成状态回退
- ✨ 新增结构化错误模型和前端错误卡片，支持友好提示、折叠诊断和复制诊断信息
- 🐛 修复思考模型连接测试：支持只返回 `reasoning_content` 或 reasoning tokens、没有最终 `content` 的响应
- 🧪 补充图片 API 兼容、历史合并、结构化错误、缓存生成、思考模型连接测试等后端覆盖

### v1.4.2 (2026-03-15)
- ✨ 新增英文版 README 并设为默认，支持中英文切换
- ✨ 新增 AI 生成的英文 banner 和 showcase 展示图片
- ✨ 致谢部分新增 Claude Opus 4.5
- ✨ 新增 shields.io 徽章（Stars、License、Docker Pulls、Release）
- ✨ 新增 GitHub Issue/PR 模板，规范化社区贡献
- ✨ 新增 CONTRIBUTING.md 贡献指南和 SECURITY.md 安全策略
- 🐛 修复 `rstrip('/v1')` 错误删除 URL 字符的问题（如 `api.openai.com` → `api.openai.co`），涉及后端 5 处
- 🐛 修复豆包/火山引擎等 chat 端点的图片 API 测试连接失败问题（使用配置的 endpoint_type 替代硬编码的 `/v1/models`）
- 🐛 修复 history 服务中裸 `except:` 改为 `except Exception:`
- 🐛 修复前端 SSE 流读取器在异常时未释放的资源泄漏
- 🐛 修复 ContentDisplay 组件 5 个 setTimeout 未清理的内存泄漏
- 🐛 修复图片重试可重复提交的问题（使用 Set 追踪进行中的索引）
- 🐛 修复 GenerateView 组件卸载后跳转定时器未清理

### v1.4.1 (2025-12-29)
- ✨ 新增一键启动脚本，支持 macOS/Linux/Windows
- ✨ 新增文案生成功能，自动生成标题、正文和标签
- 🔧 修复历史记录保存机制：大纲生成后立即保存，编辑时自动保存（300ms防抖）
- 🔧 优化跳转逻辑：点击"开始生成"前强制保存未保存的修改
- 🔧 统一启动脚本端口显示为 12398
- 🔧 清理后端生成器未使用的重试装饰器代码
- 🔧 修复前端 CSS 变量引用问题
- 🔧 优化 checkHistoryExists 接口性能，使用专用端点
- 🔧 规范 recordId 赋值方式，统一使用 setRecordId() 方法

### v1.4.0 (2025-11-30)
- 🏗️ 后端架构重构：拆分单体路由为模块化蓝图（history、images、generation、outline、config）
- 🏗️ 前端组件重构：提取可复用组件（ImageGalleryModal、OutlineModal、ShowcaseBackground等）
- ✨ 优化首页设计，移除冗余内容区块
- ✨ 背景图片预加载和渐入动画，提升加载体验
- ✨ 历史记录持久化支持（Docker部署）
- 🔧 修复历史记录预览和大纲查看功能
- 🔧 优化Modal组件可见性控制
- 🧪 新增65个后端单元测试

### v1.3.0 (2025-11-26)
- ✨ 新增 Docker 支持，一键部署
- ✨ 发布官方 Docker 镜像到 Docker Hub: `histonemax/redink`
- 🔧 Flask 自动检测前端构建产物，支持单容器部署
- 🔧 Docker 镜像内置空白配置模板，保护 API Key 安全
- 📝 更新 README，添加 Docker 部署说明

### v1.2.0 (2025-11-26)
- ✨ 新增版权信息展示，所有页面显示开源协议和项目链接
- ✨ 优化图片重新生成功能，支持单张图片重绘
- ✨ 重新生成图片时保持风格一致，传递完整上下文（封面图、大纲、用户输入）
- ✨ 修复图片缓存问题，重新生成的图片立即刷新显示
- ✨ 统一文本生成客户端接口，支持 Google Gemini 和 OpenAI 兼容接口自动切换
- ✨ 新增 Web 界面配置功能，可视化管理 API 服务商
- ✨ 新增高并发模式开关，适配不同 API 配额
- ✨ API Key 脱敏显示，保护密钥安全
- ✨ 配置自动保存，修改即时生效
- 🔧 调整默认 max_output_tokens 为 8000，兼容更多模型限制
- 🔧 优化前端路由和页面布局，提升用户体验
- 🔧 简化配置文件结构，移除冗余参数
- 🔧 优化历史记录图片显示，使用缩略图节省带宽
- 🔧 历史记录重新生成时自动从文件系统加载封面图作为参考
- 🐛 修复 `store.updateImage` 方法缺失导致的重新生成失败问题
- 🐛 修复历史记录加载时图片 URL 拼接错误
- 🐛 修复下载功能中原图参数处理问题
- 🐛 修复图片加载 500 错误问题

---

## 交流讨论与赞助

- **GitHub Issues**: [https://github.com/HisMax/RedInk/issues](https://github.com/HisMax/RedInk/issues)

### 联系作者

- **Email**: histonemax@gmail.com
- **微信**: Histone2024（添加请注明来意）
- **GitHub**: [@HisMax](https://github.com/HisMax)

### 用爱发电，如果可以，请默子喝一杯☕️咖啡吧

<img src="images/coffee.jpg" alt="赞赏码" width="300"/>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=HisMax/RedInk&type=Date)](https://star-history.com/#HisMax/RedInk&Date)

---

## 📄 开源协议

### 个人使用 - CC BY-NC-SA 4.0

本项目采用 [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/) 协议进行开源

**你可以自由地：**
- ✅ **个人使用** - 用于学习、研究、个人项目
- ✅ **分享** - 在任何媒介以任何形式复制、发行本作品
- ✅ **修改** - 修改、转换或以本作品为基础进行创作

**但需要遵守以下条款：**
- 📝 **署名** - 必须给出适当的署名，提供指向本协议的链接，同时标明是否对原始作品作了修改
- 🚫 **非商业性使用** - 不得将本作品用于商业目的
- 🔄 **相同方式共享** - 如果你修改、转换或以本作品为基础进行创作，你必须以相同的协议分发你的作品

### 商业授权

如果你希望将本项目用于**商业目的**（包括但不限于）：
- 提供付费服务
- 集成到商业产品
- 作为 SaaS 服务运营
- 其他盈利性用途

**请联系作者获取商业授权：**
- 📧 Email: histonemax@gmail.com
- 💬 微信: Histone2024（请注明"商业授权咨询"）

默子会根据你的具体使用场景提供灵活的商业授权方案。

---

### 免责声明

本软件按"原样"提供，不提供任何形式的明示或暗示担保，包括但不限于适销性、特定用途的适用性和非侵权性的担保。在任何情况下，作者或版权持有人均不对任何索赔、损害或其他责任负责。

---

## 🙏 致谢

- [Google Gemini](https://ai.google.dev/) - 强大的文案生成能力
- [Claude Opus 4.5](https://www.anthropic.com/) - 智能代码辅助与开发支持
- 图片生成服务提供商 - 惊艳的图片生成效果
- [Linux.do](https://linux.do/) - 优秀的开发者社区

---

## 👨‍💻 作者

**默子 (Histone)** - AI 创业者 

- 🏠 位置: 中国杭州
- 🚀 状态: 创业中
- 📧 Email: histonemax@gmail.com
- 💬 微信: Histone2024 （私人微信不解答任何技术问题）
- 🐙 GitHub: [@HisMax](https://github.com/HisMax)
- 

*"让 AI 帮我们做更有创造力的事"*

---

**如果这个项目帮到了你,欢迎分享给更多人!** ⭐

有任何问题或建议,欢迎提 Issue !
