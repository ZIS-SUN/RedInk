<div align="center">

**[中文](./README_zh.md) | English**

[![GitHub Stars](https://img.shields.io/github/stars/HisMax/RedInk?style=flat&logo=github)](https://github.com/HisMax/RedInk)
[![License](https://img.shields.io/badge/license-CC%20BY--NC--SA%204.0-blue)](https://creativecommons.org/licenses/by-nc-sa/4.0/)
[![Docker Pulls](https://img.shields.io/docker/pulls/histonemax/redink)](https://hub.docker.com/r/histonemax/redink)
[![GitHub Release](https://img.shields.io/github/v/release/HisMax/RedInk?include_prereleases)](https://github.com/HisMax/RedInk/releases)

<img src="images/2_en.png" alt="RedInk - Inspiration at Your Fingertips, Making Creation Effortless" width="600"/>

#### [Official Site → Redink.top](https://redink.top)

<img src="images/showcase-grid-en.png" alt="Various social media covers generated with RedInk" width="700" style="border-radius: 12px; box-shadow: 0 8px 24px rgba(0,0,0,0.12);"/>

<sub>*Various social media covers generated with RedInk - AI-powered, consistent style, accurate text*</sub>

</div>

---

## ✨ Showcase

### Type One Sentence, Get Complete Image & Text Posts

The home page offers **sample topics** you can fill in with one click to get started quickly, plus a **Recent Works** section for quick access to what you've created — or jump to History for everything.

<details open>
<summary><b>Step 1: Smart Outline Generation</b></summary>

<br>

![Outline Example](./images/example-2.png)

**Features:**
- ✏️ Edit content for each page
- 🔄 Reorder pages (not recommended)
- ✨ Custom description per page (highly recommended)

</details>

<details open>
<summary><b>🎨 Step 2: Cover Page Generation</b></summary>

<br>

![Cover Example](./images/example-3.png)

**Cover Highlights:**
- 🎯 Matches your personal style
- 📝 Accurate text rendering
- 🌈 Visually consistent and coordinated

</details>

<details open>
<summary><b>📚 Step 3: Batch Content Page Generation</b></summary>

<br>

![Content Page Example](./images/example-4.png)

**Generation Notes:**
- ⚡ Concurrent generation for all pages (up to 15 by default)
- ⚠️ Disable high concurrency in settings if your API doesn't support it
- 🔧 Regenerate individual pages you're not satisfied with
- 📊 Real-time progress visualization: each image card shows queued / generating / done / failed states, with a per-image progress bar and elapsed time while generating
- ⏱️ Overall progress advances smoothly, with estimated time remaining dynamically calculated from the actual duration of images already completed; failed images can be retried in one click

</details>

---

## 🧰 Creator Toolbox

Beyond the "one sentence → full post" main flow, the **Creator Tools** section in the sidebar offers a full suite of productivity tools for content creators, arranged along the creation workflow:

| Stage | Tool | Description |
|-------|------|-------------|
| **Ideate** | Topic Inspiration | Enter your niche; AI generates topic ideas with angles, content formats, and estimated heat. Toggle "Use my account data" to inject real performance data logged in Analytics Review; selected topics carry their angle and suggested tags into the creation flow |
| | Benchmark Breakdown | Paste a viral post or a web link to deconstruct why it worked (hook/structure/emotion/audience) and generate an original draft in the same pattern; send the imitation draft or structure template to the creation center as an outline in one click; the last 20 breakdowns are archived locally |
| | Comment Insights | Paste fan comments and let AI cluster them into pain points, each backed by the original comments as evidence; every pain point comes with ready-to-write topic ideas you can send into the creation flow in one click |
| **Write** | Viral Titles | Generate candidate titles with attractiveness scores and viral-element tags |
| | Multi-Platform Rewrite | Rewrite one piece of copy into Xiaohongshu / Douyin / WeChat / Bilibili / Weibo styles; send any rewrite to the creation center as an outline in one click |
| | Comment Assistant | Paste fan comments to generate high-engagement replies and a pinned guiding comment |
| | Video Script | Turn a post into a 30s / 60s / 3min short-video narration script with a timestamped storyboard (hook, visual cues, spoken lines, subtitle breaks, CTA); supports brand persona injection, and you can copy the full script or any single line |
| **Style & Visuals** | Brand Memory | Manage personal IP / brand profiles (tone, catchphrases, signature, banned words) for a consistent persona |
| | Style Templates | A curated library of 43 visual styles (with custom templates) — now including viral layouts and trend styles such as big-character poster, chat log, sticky note, Y2K, dopamine, and Maillard — applied to image generation in one click; custom styles can be exported as a "style share code" that friends paste to import |
| | Cover A/B | Generate multiple cover directions for one topic and compare estimated click appeal |
| **Generate & Export** | Link to Post | Paste a URL or long text to auto-distill a multi-page outline and send it into the creation flow |
| | Multi-Size Export | Adapt one image to 9:16 / 1:1 / 3:4 / WeChat banner / Bilibili cover and batch download; preview can overlay "platform safe-zone" masks showing where Douyin's like bar or Xiaohongshu's title area would cover your image (preview only, never exported) |
| **Plan & Review** | Content Calendar | Plan publishing cadence across platforms and manage plans and statuses; entries support publish times and linked works ("Add to Calendar" from history links automatically, with jump-to-view); new entries get a best-time-slot recommendation based on your account data; "AI Scheduling" generates a one-week content plan in one click (optionally using account data, with a preview to check off before saving); a built-in hotspot calendar covers year-round marketing moments (solar and lunar festivals, e-commerce sales, seasonal rules, with 2026–2028 lunar-date mapping), shown as an overlay layer plus an "upcoming hotspots" countdown block, and any hotspot can spawn topic ideas in one click — works without an AI model |
| | Analytics Review | Log published metrics manually or bulk-paste from Excel / CSV (headers auto-detected, numbers like "1.2万" auto-converted), view SVG trend / comparison charts and publishing time-slot analysis, and get AI review insights |

> Note: **Brand persona** and **visual style** flow through the entire main pipeline — once set, outlines, copy, titles, and image generation all apply them automatically. Copywriting tools require a configured text model; most visual/data tools (Style Templates, Multi-Size Export, Brand Memory, Content Calendar, Analytics) work without a model.
>
> The "Web Link" mode of Benchmark Breakdown only supports publicly accessible article pages. In-app links from Xiaohongshu / Douyin usually cannot be fetched directly — switch to "Paste Content" mode and copy the text instead.

---

## 🎛️ Fine-Tuning & Customization

Generation is not the end — every stage can be polished further:

### ✍️ Outline Page

- **Per-page AI polish**: each outline page offers three one-click refinements — polish / shorten / make it punchier — with a side-by-side preview before applying, so you can discard results you don't like

### 🖼️ Result Page

- **Edit text**: every card has an "Edit Text" action — save the copy only, or save and redraw that page's image
- **Inline editing for titles / copy / tags**: candidate titles, publishing copy, and tags are all directly editable, and edits are saved with the work in history
- **Viral Review**: Result page → "Viral Review" — AI scores the finished post for viral potential, with a 0-100 overall score, five dimension reviews (cover hook / title appeal / content structure / emotional value / call to action), and up to 5 suggestions sorted by impact; suggestions that include rewritten text can be applied in one click
- **One-click publishing package**: the "Download All" zip is upgraded to a publishing package — besides all images it includes a "发布文案.txt" file (candidate titles / body copy / tags / raw outline) ready to copy-paste when publishing
- **Multi-size export entry**: a "Multi-Size Export" button at the top of the result page jumps straight to the multi-size export tool for platform-specific sizes

### 🗂️ History Page

- **Batch management**: enter batch mode to multi-select / select all on page, with batch download and batch delete (with live progress)
- **Status filters**: filter records by All / Completed / Partial / Drafts / Failed
- **Add to Calendar**: add any work to the content calendar in one click, automatically linked to the calendar entry

### ⚙️ Settings Page

- **Image generation parameters**: configure image concurrency (1-8), image size (OpenAI-compatible APIs), and aspect ratio (Google GenAI APIs)
- **Image generation prompt template**: the entire image prompt template is fully customizable (with placeholders for page content / page type / user topic / full outline), and can be restored to default at any time

---

## 🏗️ Tech Stack

<table>
<tr>
<td width="50%" valign="top">

### 🔧 Backend

| Technology | Description |
|------|------|
| **Language** | Python 3.11+ |
| **Framework** | Flask |
| **Package Manager** | uv |
| **Text AI** | Gemini 3 |
| **Image AI** | 🍌 Nano Banana Pro |

</td>
<td width="50%" valign="top">

### 🎨 Frontend

| Technology | Description |
|------|------|
| **Framework** | Vue 3 + TypeScript |
| **Build Tool** | Vite |
| **State Management** | Pinia |
| **Styling** | Modern CSS |

</td>
</tr>
</table>

---

## 📦 Deployment

### Option 1: Docker (Recommended)

**The simplest way — one command to start:**

```bash
docker run -d -p 12398:12398 -v ./history:/app/history -v ./output:/app/output histonemax/redink:latest
```

Visit http://localhost:12398 and configure your API Key in the **Settings** page.

**Using docker-compose (optional):**

Download [docker-compose.yml](https://github.com/HisMax/RedInk/blob/main/docker-compose.yml), then:

```bash
docker-compose up -d
```

**Docker Notes:**
- The container does not include any API Keys — configure them in the web UI
- Use `-v ./history:/app/history` to persist history
- Use `-v ./output:/app/output` to persist generated images
- Optional: mount custom config `-v ./text_providers.yaml:/app/text_providers.yaml`

---

### Option 2: Local Development

**Prerequisites:**
- Python 3.11+
- Node.js 18+
- pnpm
- uv

### 1. Clone the Repository
```bash
git clone https://github.com/HisMax/RedInk.git
cd RedInk
```

### 2. Configure API Services

Copy the config templates:
```bash
cp text_providers.yaml.example text_providers.yaml
cp image_providers.yaml.example image_providers.yaml
```

Edit the config files with your API Key and service settings, or configure them later via the **Settings** page in the web UI.

### 3. Install Backend Dependencies
```bash
uv sync
```

### 4. Install Frontend Dependencies
```bash
cd frontend
pnpm install
```

### 5. Start the Services

#### One-Click Start (Recommended)

Run the start script to automatically install dependencies and launch both frontend and backend:

- **macOS**: `start.sh` or double-click `scripts/start-macos.command`
- **Linux**: `./start.sh`
- **Windows**: Double-click `start.bat`

The browser will automatically open at http://localhost:5173

#### Manual Start

**Start Backend:**
```bash
uv run python -m backend.app
```
Visit: http://localhost:12398

**Start Frontend:**
```bash
cd frontend
pnpm dev
```
Visit: http://localhost:5173

---

### Option 3: macOS Desktop App

RedInk can be packaged as a native macOS desktop app (pywebview native window + PyInstaller bundle at `dist/RedInk.app`) that runs like a regular app:

- 🖥️ Native window with app icon — no browser needed
- 🔔 Native macOS notifications when image generation completes or fails
- 📐 Window size and position are remembered across launches

See [BUILD_DESKTOP.md](./BUILD_DESKTOP.md) for build instructions.

---

## 🔧 Configuration

### Configuration Methods

The project supports two configuration methods:

1. **Web UI (Recommended)**: Visual configuration via the Settings page after starting the service
2. **YAML Files**: Edit config files directly

### Text Generation Config

Config file: `text_providers.yaml`

```yaml
# Active provider
active_provider: openai

providers:
  # OpenAI or compatible API
  openai:
    type: openai_compatible
    api_key: sk-xxxxxxxxxxxxxxxxxxxx
    base_url: https://api.openai.com/v1
    model: gpt-4o

  # Google Gemini (native API)
  gemini:
    type: google_gemini
    api_key: AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
    model: gemini-2.0-flash
```

### Image Generation Config

Config file: `image_providers.yaml`

```yaml
# Active provider
active_provider: gemini

providers:
  # Google Gemini image generation
  gemini:
    type: google_genai
    api_key: AIzaxxxxxxxxxxxxxxxxxxxxxxxxx
    model: gemini-3-pro-image-preview
    high_concurrency: false

  # OpenAI compatible API
  openai_image:
    type: image_api
    api_key: sk-xxxxxxxxxxxxxxxxxxxx
    base_url: https://your-api-endpoint.com
    model: dall-e-3
    high_concurrency: false
```

### High Concurrency Mode

- **Off (default)**: Images generated one by one — suitable for GCP $300 trial accounts or rate-limited APIs
- **On**: Images generated in parallel (up to 15 simultaneously) — faster but requires API support for high concurrency

⚠️ **Not recommended for GCP $300 trial accounts** — may trigger rate limits and cause generation failures.

---

## ⚠️ Notes

1. **API Quota Limits**:
   - Be aware of Gemini and image generation API call quotas
   - GCP trial accounts should keep high concurrency disabled

2. **Generation Time**:
   - Outline generation usually takes 15-30 seconds
   - Image generation takes time — please be patient (don't leave the page)

---

## 🤝 Contributing

Issues and Pull Requests are welcome!

If this project helps you, please give it a Star ⭐

---

## Changelog

### Unreleased
- ✨ Creator preference profile: automatically aggregates "topics the user liked / preferred length / editing habits" from work ratings and edit traces, and injects it into outline generation so the AI understands you better over time (no conclusions until 3+ rated samples); a profile summary card is available in Settings
- ✨ Platform safe-zone preview in Multi-Size Export: overlays translucent masks for Douyin like/comment bar and bottom caption area, Xiaohongshu title area, and Bilibili duration badge so text can avoid covered regions — preview only, never exported into images
- ✨ Style share codes in Style Templates: generate a RINK1 share code from any custom style and send it to friends, who can paste to import (with validation preview, automatic rename on conflicts, and malicious-content protection)
- ✨ Work rating (1-5 stars) and edit traces on the result page: accumulates data for the quality feedback loop, with star badges on history cards
- ✨ Data management center in Settings: one-click backup of all local data as zip / import restore (with automatic pre-import backup) / sanitized diagnostics package export
- ✨ Windows desktop build support with cross-platform data directories, plus a Release CI pipeline for automated packaging
- ✨ Local archive with quick restore for Topic Inspiration / Comment Insight, and one-click "Add to Calendar" for topics
- ✨ Real-time generation progress visualization: queued / generating / done / failed image card states, per-image progress bar with elapsed time, smooth overall progress, and estimated time remaining based on actual completion times
- ✨ Added macOS desktop app: pywebview native window packaged with PyInstaller as `dist/RedInk.app`, with app icon, native completion/failure notifications, and window size/position memory (see BUILD_DESKTOP.md)
- ✨ Added "Edit Text" on the result page: save copy only or save and redraw; titles / copy / tags support inline editing and are saved with the work in history
- ✨ Added per-page AI polish on the outline page: polish / shorten / punchier, with preview before applying
- ✨ Settings page now supports image concurrency (1-8), image size, and aspect ratio; the image generation prompt template is fully customizable with one-click restore to default
- ✨ Added "Viral Review" on the result page: AI review with a 0-100 overall score, five dimension reviews, and up to 5 suggestions — those with rewritten text can be applied in one click
- ✨ Analytics Review upgrade: bulk paste import from Excel / CSV (auto header detection, "万" auto-conversion), SVG trend and comparison charts, publishing time-slot analysis with best-slot conclusion
- ✨ Benchmark Breakdown upgrade: direct breakdown from web links, one-click send of imitation draft / structure template to the creation center as an outline, local archive of the last 20 breakdowns
- ✨ Topic Inspiration upgrade: "Use my account data" injects real performance data, topics carry angle and tags into creation, and multi-platform rewrites can be sent to the creation center in one click
- ✨ One-click publishing package: titles / copy / tags on the result page are saved with the work in history, the zip download is upgraded to a publishing package with a "发布文案.txt" file (candidate titles / body / tags / outline), and the result page gains a "Multi-Size Export" entry
- ✨ Content Calendar upgrade: entries support publish times and linked works ("Add to Calendar" from history links automatically, with jump-to-view), new entries get best-time-slot recommendations from account data, and "AI Scheduling" generates a one-week plan (optionally using account data, preview and check off before saving)
- ✨ History batch management: batch mode with multi-select / select all on page, batch delete (with progress), batch download, and status filters completed as All / Completed / Partial / Drafts / Failed
- ✨ Home page onboarding: sample topics filled in with one click, plus a "Recent Works" quick-access section

### v1.4.3 (2026-06-30)
- ✨ Default outline length changed to 5 pages when the user does not specify a page count
- ✨ Added clearer outline generation loading copy: "please wait, this step usually takes 15-30 seconds"
- 🏗️ Modularized image provider logic with reusable provider policy, API client, response extractor, rate limiter, and history image merger
- 🔧 Fixed GPT Image and Nano Banana compatible image APIs by omitting `response_format` by default and supporting `b64_json`, data URLs, and temporary image URLs
- 🔧 Added per-record image generation recovery so refreshes or retries reuse existing images instead of spending upstream quota again
- 🔧 Protected history records from empty image overwrites and status regressions; history reads can self-heal from task image folders
- ✨ Added structured Problem Details-style API errors and reusable frontend error cards with copyable diagnostics
- 🐛 Fixed provider connection tests for reasoning models that return `reasoning_content` or reasoning tokens without final `content`
- 🧪 Added backend coverage for image API compatibility, history merging, structured errors, cached generation, and reasoning-model connection tests

### v1.4.2 (2026-03-15)
- ✨ Added English README as default with language toggle (中文/English)
- ✨ Added AI-generated English banner and showcase grid images
- ✨ Added Claude Opus 4.5 to acknowledgments
- ✨ Added shields.io badges (Stars, License, Docker Pulls, Release)
- ✨ Added GitHub Issue/PR templates for standardized contributions
- ✨ Added CONTRIBUTING.md and SECURITY.md
- 🐛 Fixed `rstrip('/v1')` incorrectly stripping URL characters (e.g. `api.openai.com` → `api.openai.co`) — 5 occurrences across backend
- 🐛 Fixed image API test connection failing for chat-based endpoints (Doubao/Volcengine) by using configured endpoint_type instead of hardcoded `/v1/models`
- 🐛 Fixed bare `except:` clause replaced with `except Exception:` in history service
- 🐛 Fixed SSE stream reader not released on error in frontend API layer (resource leak)
- 🐛 Fixed 5 uncleared `setTimeout` calls in ContentDisplay component (memory leak)
- 🐛 Fixed duplicate image regeneration requests by tracking in-progress indices
- 🐛 Fixed GenerateView redirect timer not cleared on component unmount

### v1.4.1 (2025-12-29)
- ✨ Added one-click start scripts for macOS/Linux/Windows
- ✨ Added copywriting generation: auto-generate titles, body text, and tags
- 🔧 Fixed history saving: immediate save after outline generation, auto-save on edit (300ms debounce)
- 🔧 Optimized navigation: force-save unsaved changes before clicking "Start Generation"
- 🔧 Unified startup script port display to 12398
- 🔧 Cleaned up unused retry decorator code in backend generators
- 🔧 Fixed frontend CSS variable reference issues
- 🔧 Optimized checkHistoryExists API performance with dedicated endpoint
- 🔧 Standardized recordId assignment using setRecordId() method

### v1.4.0 (2025-11-30)
- 🏗️ Backend refactored: split monolithic routes into modular blueprints (history, images, generation, outline, config)
- 🏗️ Frontend refactored: extracted reusable components (ImageGalleryModal, OutlineModal, ShowcaseBackground, etc.)
- ✨ Optimized homepage design, removed redundant content blocks
- ✨ Background image preloading with fade-in animation for better loading experience
- ✨ History persistence support (Docker deployment)
- 🔧 Fixed history preview and outline viewing
- 🔧 Optimized Modal component visibility control
- 🧪 Added 65 backend unit tests

### v1.3.0 (2025-11-26)
- ✨ Added Docker support for one-click deployment
- ✨ Published official Docker image to Docker Hub: `histonemax/redink`
- 🔧 Flask auto-detects frontend build artifacts for single-container deployment
- 🔧 Docker image includes blank config templates to protect API Key security
- 📝 Updated README with Docker deployment instructions

### v1.2.0 (2025-11-26)
- ✨ Added copyright info display on all pages
- ✨ Improved image regeneration with single image redraw support
- ✨ Regenerated images maintain style consistency with full context (cover, outline, user input)
- ✨ Fixed image cache issues — regenerated images refresh immediately
- ✨ Unified text generation client supporting Google Gemini and OpenAI-compatible APIs with auto-switching
- ✨ Added web UI configuration for visual API provider management
- ✨ Added high concurrency mode toggle for different API quotas
- ✨ API Key masking for security
- ✨ Auto-save configuration with instant effect
- 🔧 Adjusted default max_output_tokens to 8000 for broader model compatibility
- 🔧 Optimized frontend routing and page layout for better UX
- 🔧 Simplified config file structure, removed redundant parameters
- 🔧 Optimized history image display with thumbnails to save bandwidth
- 🔧 History regeneration auto-loads cover image from filesystem as reference
- 🐛 Fixed missing `store.updateImage` method causing regeneration failure
- 🐛 Fixed image URL concatenation error during history loading
- 🐛 Fixed raw image parameter handling in download function
- 🐛 Fixed image loading 500 error

---

## Community & Support

- **GitHub Issues**: [https://github.com/HisMax/RedInk/issues](https://github.com/HisMax/RedInk/issues)

### Contact the Author

- **Email**: histonemax@gmail.com
- **WeChat**: Histone2024 (please state your purpose)
- **GitHub**: [@HisMax](https://github.com/HisMax)

### Support the Project

<img src="images/coffee.jpg" alt="Buy me a coffee" width="300"/>

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=HisMax/RedInk&type=Date)](https://star-history.com/#HisMax/RedInk&Date)

---

## 📄 License

### Personal Use - CC BY-NC-SA 4.0

This project is licensed under [CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/)

**You are free to:**
- ✅ **Personal Use** — for learning, research, and personal projects
- ✅ **Share** — copy and redistribute the material in any medium or format
- ✅ **Adapt** — remix, transform, and build upon the material

**Under the following terms:**
- 📝 **Attribution** — You must give appropriate credit, provide a link to the license, and indicate if changes were made
- 🚫 **NonCommercial** — You may not use the material for commercial purposes
- 🔄 **ShareAlike** — If you remix, transform, or build upon the material, you must distribute your contributions under the same license

### Commercial License

If you wish to use this project for **commercial purposes** (including but not limited to):
- Providing paid services
- Integrating into commercial products
- Operating as a SaaS service
- Other for-profit uses

**Please contact the author for a commercial license:**
- 📧 Email: histonemax@gmail.com
- 💬 WeChat: Histone2024 (please note "Commercial License Inquiry")

The author will provide flexible commercial licensing options based on your specific use case.

---

### Disclaimer

This software is provided "as is", without warranty of any kind, express or implied, including but not limited to the warranties of merchantability, fitness for a particular purpose, and noninfringement. In no event shall the authors or copyright holders be liable for any claim, damages, or other liability.

---

## 🙏 Acknowledgments

- [Google Gemini](https://ai.google.dev/) — Powerful text generation capabilities
- [Claude Opus 4.5](https://www.anthropic.com/) — Intelligent code assistance and development support
- Image generation service providers — Stunning image generation
- [Linux.do](https://linux.do/) — Excellent developer community

---

## 👨‍💻 Author

**Mozi (Histone)** - AI Entrepreneur

- 🏠 Location: Hangzhou, China
- 🚀 Status: Startup in progress
- 📧 Email: histonemax@gmail.com
- 💬 WeChat: Histone2024 (personal WeChat — no tech support)
- 🐙 GitHub: [@HisMax](https://github.com/HisMax)

*"Let AI do the creative work for us"*

---

**If this project helped you, share it with others!** ⭐

Questions or suggestions? Feel free to open an Issue!
