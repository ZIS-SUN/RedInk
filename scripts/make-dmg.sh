#!/usr/bin/env bash
# 将已构建的 dist/RedInk.app 打包为可分发的压缩 DMG（dist/RedInk.dmg）
# 前置：先执行 bash scripts/build-macos-app.sh 生成 dist/RedInk.app

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

APP_PATH="${PROJECT_ROOT}/dist/RedInk.app"
DMG_PATH="${PROJECT_ROOT}/dist/RedInk.dmg"
VOL_NAME="红墨 RedInk"
ICON_PATH="${PROJECT_ROOT}/build/icon.icns"

if [ ! -d "${APP_PATH}" ]; then
  echo "错误：未找到 ${APP_PATH}" >&2
  echo "请先执行 bash scripts/build-macos-app.sh 构建应用" >&2
  exit 1
fi

STAGING_DIR="$(mktemp -d -t redink-dmg)"
RW_DMG="$(mktemp -u -t redink-rw).dmg"
cleanup() {
  rm -rf "${STAGING_DIR}" "${RW_DMG}"
}
trap cleanup EXIT

echo "==> [1/3] 准备 DMG 内容（RedInk.app + 应用程序 软链）"
ditto "${APP_PATH}" "${STAGING_DIR}/RedInk.app"
ln -s /Applications "${STAGING_DIR}/应用程序"

echo "==> [2/3] 生成临时可写镜像并设置卷图标（可选，失败不影响打包）"
hdiutil create -srcfolder "${STAGING_DIR}" -volname "${VOL_NAME}" \
  -fs HFS+ -format UDRW -ov "${RW_DMG}" >/dev/null

# 卷图标为可选加分项：任何一步失败都不终止脚本
set_volume_icon() {
  [ -f "${ICON_PATH}" ] || { echo "    跳过卷图标：未找到 ${ICON_PATH}"; return 0; }
  command -v SetFile >/dev/null 2>&1 || { echo "    跳过卷图标：未安装 SetFile（Xcode 命令行工具）"; return 0; }
  local mount_point="" device=""
  device="$(hdiutil attach "${RW_DMG}" -readwrite -noverify -noautoopen \
    | awk -F '\t' '/\/Volumes\// {print $1; exit}' | xargs)" || return 0
  mount_point="$(hdiutil info | grep "^${device}" | awk -F '\t' '{print $3; exit}')" || true
  [ -n "${mount_point}" ] || mount_point="/Volumes/${VOL_NAME}"
  if [ -d "${mount_point}" ]; then
    cp "${ICON_PATH}" "${mount_point}/.VolumeIcon.icns" \
      && SetFile -a C "${mount_point}" \
      && echo "    卷图标已设置"
  fi
  hdiutil detach "${device}" -quiet || hdiutil detach "${device}" -force -quiet || true
}
set_volume_icon || echo "    卷图标设置失败，忽略并继续"

echo "==> [3/3] 压缩为 UDZO 并输出 ${DMG_PATH}"
rm -f "${DMG_PATH}"
hdiutil convert "${RW_DMG}" -format UDZO -imagekey zlib-level=9 \
  -o "${DMG_PATH}" >/dev/null

echo ""
echo "DMG 制作完成！"
echo "产物：${DMG_PATH}"
echo "大小：$(du -h "${DMG_PATH}" | cut -f1 | xargs)"
