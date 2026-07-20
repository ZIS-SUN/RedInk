# RedInk 桌面版（macOS）构建与使用说明

桌面版使用 [pywebview](https://pywebview.flowrl.com/) 提供原生窗口，内部在后台线程运行 Flask 后端，并用 [PyInstaller](https://pyinstaller.org/) 打包为可双击运行的 `RedInk.app`。

## 环境依赖

| 工具 | 用途 | 安装 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python 依赖与运行 | `brew install uv` |
| [pnpm](https://pnpm.io/) | 前端构建 | `brew install pnpm` |

Python 依赖（`pywebview`、`pyinstaller`）已写入 `pyproject.toml`，首次构建前执行一次：

```bash
cd RedInk
uv sync
```

## 一键构建

```bash
bash scripts/build-macos-app.sh
```

脚本会依次：

1. 进入 `frontend/` 执行 `pnpm install && pnpm run build`，生成 `frontend/dist`；
2. 检查 `build/icon.icns`，不存在则自动执行 `uv run python scripts/make_icns.py` 生成应用图标；
3. 执行 `uv run pyinstaller redink.spec --noconfirm` 打包。

## 应用图标

应用图标由 `scripts/make_icns.py` 从 `images/logo.png` 生成：脚本会自动定位
logo 左侧的红圈 R mark，合成 macOS Big Sur 风格的 1024x1024 图标
（白色圆角矩形 + 居中 mark），再经 `iconutil` 输出 `build/icon.icns`，
由 `redink.spec` 中 `BUNDLE(icon='build/icon.icns')` 引用。

手动（重新）生成：

```bash
uv run python scripts/make_icns.py
```

构建前若 `build/icon.icns` 不存在，需要先执行上面的命令
（`scripts/build-macos-app.sh` 已内置该检查，会自动生成）。

## 产物位置

构建完成后，应用位于：

```text
dist/RedInk.app
```

双击即可运行，或在终端执行：

```bash
open dist/RedInk.app
```

## 未签名应用的打开方式

应用未做代码签名与公证，首次打开时 macOS Gatekeeper 可能提示
"无法验证开发者"或"已损坏"。有以下几种处理方式（任选其一）：

- **右键打开**：在访达中右键（或按住 Control 点按）`RedInk.app`，选择
  「打开」，在弹出的对话框中再次点击「打开」。之后双击即可正常启动；
- **系统设置放行**：先双击一次 `RedInk.app`（会被拦截），然后打开
  「系统设置 → 隐私与安全性」，在页面下方找到关于 RedInk 的提示，
  点击「仍要打开」；
- **命令行移除隔离属性**：

```bash
xattr -dr com.apple.quarantine dist/RedInk.app
```

## 打包分发（DMG）

构建出 `dist/RedInk.app` 后，可进一步制作标准的 macOS 分发镜像：

```bash
bash scripts/make-dmg.sh
```

产物为压缩 DMG（卷名「红墨 RedInk」）：

```text
dist/RedInk.dmg
```

镜像内包含 `RedInk.app` 和指向 `/Applications` 的「应用程序」软链接。
用户安装方式：**双击 `RedInk.dmg` 挂载 → 把 `RedInk.app` 拖到旁边的
「应用程序」图标** 即完成安装，之后可推出镜像。

注意：应用未签名/未公证，用户首次打开安装后的 `RedInk.app` 时仍可能被
Gatekeeper 拦截，处理方式见上文[「未签名应用的打开方式」](#未签名应用的打开方式)小节。

## 代码签名与公证（可选）

### 为什么需要

当前构建产物只做了 ad-hoc 签名，分发给其他用户时会被 macOS Gatekeeper
拦截（提示"无法验证开发者"），用户必须右键打开或去系统设置放行。完成
**Developer ID 签名 + 公证（notarization）** 后，用户下载 DMG 双击安装、
双击启动即可，不再有任何拦截。

### 前置条件

- 加入 [Apple Developer Program](https://developer.apple.com/programs/)（99 美元/年）；
- 申请 **Developer ID Application** 证书并导入钥匙串（用于在 App Store
  之外分发的签名证书），导入后可用 `security find-identity -v -p codesigning`
  查到证书名；
- 用 App 专用密码（在 [account.apple.com](https://account.apple.com) 生成）
  或 App Store Connect API key，通过 `xcrun notarytool store-credentials`
  把公证凭据存入钥匙串，得到一个 keychain profile 名（凭据只存在钥匙串里，
  不会出现在任何脚本或命令历史中）。

详细步骤（含完整命令）：直接运行 `bash scripts/sign-and-notarize.sh`
（不带参数），脚本会打印一份前置准备指南。

### 脚本用法

环境自检（无需证书，随时可跑，不做任何签名动作）：

```bash
bash scripts/sign-and-notarize.sh --check
```

会依次检查：Xcode 命令行工具、钥匙串中可用的签名证书、`notarytool`
是否可用、`dist/RedInk.app` 是否存在。

正式签名 + 公证（需先完成前置条件）：

```bash
SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
NOTARY_PROFILE="redink-notary" \
bash scripts/sign-and-notarize.sh
```

脚本会依次：签名 `.app`（hardened runtime + 时间戳）→ 验证签名 →
用已签名的 app 重新生成 DMG → 签名 DMG → 提交 Apple 公证并等待结果 →
为 DMG 和 `.app` 装订公证票据（staple）→ `spctl --assess` 验收。
任何一步失败都会给出具体的排查建议。

### 签名后的用户体验变化

- 下载 DMG 后双击挂载、拖入应用程序、双击启动，全程无拦截弹窗；
- 不再需要右键打开、系统设置放行或 `xattr` 移除隔离属性；
- 因为公证票据已装订进产物，离线环境下 Gatekeeper 也能通过验证。

## 首次运行

- 首次双击启动时，应用会自动把示例配置拷贝到
  `~/Library/Application Support/RedInk/`；
- 需要先填入 API key 才能真实生成内容：在应用内打开「系统设置」页面配置，
  或直接编辑该目录下的 `text_providers.yaml` / `image_providers.yaml`；
- 首次启动可能需要数秒（解包资源 + 等待后端健康检查通过），请耐心等待
  窗口出现。

## 桌面特性

### 原生通知

图片生成全部完成或出现失败时，应用会发送 macOS 系统通知（右上角横幅）。
通知通过 `osascript` 的脚本事件（Script Editor 来源）发送，无需额外的通知权限
配置；首次触发时系统可能弹出授权提示，允许即可。浏览器模式（`start.sh` /
Docker）下没有该桥接，通知自动降级为无操作，不影响使用。

### 窗口大小记忆

关闭窗口时会记住当前窗口的尺寸和位置，下次启动自动恢复。状态存储在：

```text
~/Library/Application Support/RedInk/window_state.json
```

删除该文件即可恢复默认窗口大小（1440x900、系统默认位置）。文件损坏或数值
异常时会自动回退到默认值，不影响启动。

## 配置文件与数据目录

首次运行时，应用会把示例配置拷贝到可写目录：

```text
~/Library/Application Support/RedInk/
├── text_providers.yaml    # 文本模型服务商配置（API key、模型等）
├── image_providers.yaml   # 图片模型服务商配置
├── history/               # 生成历史
└── images/                # 生成的图片
```

修改 API key / 模型有两种方式：

- 直接编辑 `~/Library/Application Support/RedInk/` 下的两个 yaml 文件，然后重启应用；
- 在应用内打开「系统设置」页面进行配置。

## 清理数据

如需彻底重置（会删除所有配置、历史与生成的图片）：

```bash
rm -rf ~/Library/Application\ Support/RedInk
```

下次启动时会重新生成示例配置。

## 运行原理（简述）

- 入口为项目根的 `desktop.py`：启动时清理代理环境变量（保证国内直连），调用
  `backend.paths.seed_user_data()` 初始化可写目录，然后在守护线程中把 Flask
  后端跑在 `127.0.0.1:12398`（端口被占用时自动改用系统分配的空闲端口）；
- 等待 `/api/health` 返回 200 后，用 pywebview 打开原生窗口加载
  `http://127.0.0.1:<port>`，前端由 Flask 静态托管 `frontend/dist`；
- 关闭窗口即退出整个应用。
- 打包配置见 `redink.spec`：`frontend/dist`、`backend/prompts`、两个
  `*.yaml.example` 会作为只读资源打进 app，运行时通过
  `backend.paths.resource_path()` 读取。

## 发版流程

发版由 tag 驱动，推送 `v*` tag 后 `.github/workflows/release.yml` 会自动
构建 DMG 并创建 GitHub Release（changelog 由 [git-cliff](https://git-cliff.org/)
按 conventional commits 自动生成，分组规则见仓库根目录 `cliff.toml`）。

步骤：

1. **bump 版本号（三处，必须一致）**：
   - `pyproject.toml` 的 `[project] version`；
   - `frontend/package.json` 的 `version`；
   - `redink.spec` 的 `CFBundleShortVersionString`。

   本地自查（三处不一致会非零退出）：

   ```bash
   uv run python scripts/check-version.py
   ```

2. **提交** 版本号变更到 `main`；

3. **打 tag 并推送**（tag 必须是 `v` + 版本号，例如版本 `0.2.0` 对应 `v0.2.0`）：

   ```bash
   git tag v0.2.0
   git push origin v0.2.0
   ```

4. **CI 自动完成剩余工作**：校验 tag 与三处版本号一致（不一致直接失败）
   → macOS runner 上跑 `scripts/build-macos-app.sh` + `scripts/make-dmg.sh`
   → 生成 changelog → 创建 GitHub Release 并附上
   `RedInk-v<版本>.dmg`。同时既有的 `docker-publish.yml` 也会被同一 tag
   触发，发布对应版本的 Docker 镜像。

注意：

- CI 产出的 DMG 与本地构建一致，仅有 **ad-hoc 签名**，未做 Developer ID
  签名与公证（证书与公证凭据只在本地钥匙串中）。如需分发签名公证版本，
  仍需在本地对 CI 产物或本地构建产物执行
  `bash scripts/sign-and-notarize.sh`（见上文[「代码签名与公证」](#代码签名与公证可选)），
  再手动替换 Release 附件；
- `backend/app.py` 中另有一处硬编码版本号，`check-version.py` 会核对并在
  不一致时打印警告（不阻断），发版前请顺手确认。

## Windows 构建

打包链路（pywebview + PyInstaller）已做跨平台适配：`redink.spec` 按
`sys.platform` 条件化（Windows 分支产出 windowed `RedInk.exe`），
`backend/paths.py` 与 `desktop.py` 的平台相关逻辑均已分支处理。
**以下流程在 macOS 上编写，未经 Windows 真机验证**，见文末清单。

### 前置要求

| 工具 | 用途 | 安装 |
| --- | --- | --- |
| [uv](https://docs.astral.sh/uv/) | Python 依赖与运行 | `winget install astral-sh.uv` 或官网脚本 |
| [pnpm](https://pnpm.io/) | 前端构建 | `winget install pnpm.pnpm` 或 `npm i -g pnpm` |
| [WebView2 Runtime](https://developer.microsoft.com/microsoft-edge/webview2/) | pywebview 的 EdgeChromium 后端（运行时必需） | Win11 已内置；Win10 需手动安装 Evergreen Runtime |

Python 侧的 Windows 专属依赖（`pythonnet` / `clr-loader`）已通过
pywebview 的平台 marker 声明在锁文件中，`uv sync` 会在 Windows 上自动安装。

### 构建命令

```powershell
powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
```

脚本依次：前端构建（`pnpm install && pnpm run build`）→ `uv sync` →
`uv run pyinstaller redink.spec --noconfirm`。产物为目录形式：

```text
dist\RedInk\RedInk.exe
```

数据与配置目录为 `%APPDATA%\RedInk\`（首次运行自动初始化示例配置）。

### 应用图标（可选）

仓库当前没有 `.ico` 图标文件。`redink.spec` 的 Windows 分支只在
`build/icon.ico` 存在时才为 EXE 设置图标，否则使用 PyInstaller 默认图标，
不影响构建。如需图标，可参照 `scripts/make_icns.py` 编写姊妹脚本
`scripts/make_ico.py`：复用其从 `images/logo.png` 合成 1024x1024 图标图像
的逻辑，最后用 Pillow 直接导出多尺寸 `.ico`
（`img.save('build/icon.ico', sizes=[(16,16),(32,32),(48,48),(256,256)])`），
无需 macOS 专属的 `iconutil`。

### 系统通知

Windows 下 `DesktopApi.notify()` 通过 PowerShell 调用 WinRT
`ToastNotificationManager` 发送 Toast 通知，失败时静默返回 False，
不影响主流程。

### 已知未验证项清单

以下内容因缺少 Windows 真机，仅做了代码层面的适配与 macOS 侧回归，
首次在 Windows 构建/运行时请重点确认：

- [ ] `scripts/build-windows.ps1` 的 PowerShell 语法与执行流程；
- [ ] PyInstaller Windows 分支 hiddenimports（`clr` / `clr_loader` /
      `pythonnet`）是否足够——若启动报
      `Failed to resolve Python.Runtime`，参考 pywebview issue #1316/#1638
      （常见原因：`Python.Runtime.dll` 被 Windows 安全机制 Block，
      需 `Unblock-File`；或 pythonnet 非预编译 wheel）；
- [ ] WebView2 Runtime 缺失时 pywebview 的报错表现；
- [ ] Toast 通知在打包后（windowed、无控制台）能否正常弹出；
- [ ] 端口探测：Windows 分支不设置 `SO_REUSEADDR`（避免误报端口空闲），
      逻辑上正确但未实测端口冲突场景；
- [ ] 首次运行时 `%APPDATA%\RedInk\` 的种子配置拷贝。
