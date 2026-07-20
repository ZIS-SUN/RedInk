# 一键构建 Windows 桌面版 RedInk（与 scripts/build-macos-app.sh 对等）
# 依赖：uv（Python 环境）、pnpm（前端构建）、WebView2 Runtime（运行时需要）
#
# 用法（PowerShell）：
#   powershell -ExecutionPolicy Bypass -File scripts\build-windows.ps1
#
# 注意：本脚本在 macOS 上编写、未经 Windows 真机验证，
# 语法尽量保守（仅用基础 cmdlet 与 $LASTEXITCODE 检查）。

$ErrorActionPreference = "Stop"

# 切到仓库根目录（脚本位于 scripts/ 下）
Set-Location (Join-Path $PSScriptRoot "..")

Write-Host "==> [1/3] 构建前端 (frontend/dist)"
Push-Location frontend
pnpm install
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
pnpm run build
if ($LASTEXITCODE -ne 0) { Pop-Location; exit 1 }
Pop-Location

Write-Host "==> [2/3] 同步 Python 依赖 (uv sync)"
uv sync
if ($LASTEXITCODE -ne 0) { exit 1 }

# 应用图标（可选）：build/icon.ico 不存在时跳过，产物使用默认图标。
# 生成方式见 BUILD_DESKTOP.md「Windows 构建」一节。
if (-not (Test-Path "build\icon.ico")) {
    Write-Host "提示：build\icon.ico 不存在，将使用默认图标（可选步骤，见 BUILD_DESKTOP.md）"
}

Write-Host "==> [3/3] PyInstaller 打包"
uv run pyinstaller redink.spec --noconfirm
if ($LASTEXITCODE -ne 0) { exit 1 }

Write-Host ""
Write-Host "构建完成！"
Write-Host "产物目录：dist\RedInk\（入口 dist\RedInk\RedInk.exe）"
Write-Host "运行前置：系统需已安装 Microsoft Edge WebView2 Runtime"
Write-Host "配置与数据目录：%APPDATA%\RedInk\"
