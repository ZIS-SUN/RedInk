#!/usr/bin/env bash
# 一键构建 macOS 桌面版 RedInk.app
# 依赖：uv（Python 环境）、pnpm（前端构建）

set -e

cd "$(dirname "$0")/.."

echo "==> [1/3] 构建前端 (frontend/dist)"
cd frontend && pnpm install && pnpm run build && cd ..

echo "==> [2/3] 应用图标 (build/icon.icns)"
if [ ! -f build/icon.icns ]; then
  uv run python scripts/make_icns.py
else
  echo "build/icon.icns 已存在，跳过（如需重新生成请先删除它）"
fi

echo "==> [3/3] PyInstaller 打包"
uv run pyinstaller redink.spec --noconfirm

echo ""
echo "构建完成！"
echo "产物：$(pwd)/dist/RedInk.app"
echo "运行：双击 dist/RedInk.app，或执行 open dist/RedInk.app"
echo "配置与数据目录：~/Library/Application Support/RedInk/"
echo "如需分发，运行 bash scripts/make-dmg.sh 生成 dist/RedInk.dmg"
