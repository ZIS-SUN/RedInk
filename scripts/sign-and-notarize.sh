#!/usr/bin/env bash
# 对 dist/RedInk.app 做 Developer ID 代码签名 + 公证（notarization）+ 装订（staple）
#
# 用法：
#   环境自检（无需证书，随时可跑）：
#     bash scripts/sign-and-notarize.sh --check
#   正式签名 + 公证（需要 Apple Developer 账号）：
#     SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
#     NOTARY_PROFILE="redink-notary" \
#     bash scripts/sign-and-notarize.sh
#
# 安全约定：本脚本不接受、不存储任何 Apple ID / 密码 / API key。
# 公证凭据必须事先通过 `xcrun notarytool store-credentials` 存入钥匙串，
# 脚本只引用 keychain profile 名字（NOTARY_PROFILE）。

set -euo pipefail

cd "$(dirname "$0")/.."
PROJECT_ROOT="$(pwd)"

APP_PATH="${PROJECT_ROOT}/dist/RedInk.app"
DMG_PATH="${PROJECT_ROOT}/dist/RedInk.dmg"

SIGN_IDENTITY="${SIGN_IDENTITY:-}"
NOTARY_PROFILE="${NOTARY_PROFILE:-}"

# ---------------------------------------------------------------------------
# 前置准备指南（无证书时打印）
# ---------------------------------------------------------------------------
print_prereq_guide() {
  cat <<'GUIDE'
缺少 SIGN_IDENTITY 和/或 NOTARY_PROFILE，无法执行签名与公证。

════════════════ 前置准备指南 ════════════════

1. 加入 Apple Developer Program（99 美元/年）
   https://developer.apple.com/programs/enroll/

2. 申请「Developer ID Application」证书
   - 打开 https://developer.apple.com/account/resources/certificates/add
   - 类型选择 Developer ID Application（用于在 Mac App Store 之外分发）
   - 按提示用「钥匙串访问 → 证书助理 → 从证书颁发机构请求证书」生成 CSR，
     上传后下载 .cer 双击导入钥匙串
   - 导入成功后可用下面命令看到证书名：
       security find-identity -v -p codesigning
     形如：Developer ID Application: Your Name (TEAMID)

3. 为 notarytool 存储公证凭据（存入钥匙串，只需一次）
   方式 A：App 专用密码（在 https://account.apple.com 生成）
       xcrun notarytool store-credentials "redink-notary" \
         --apple-id "you@example.com" \
         --team-id "TEAMID" \
         --password "app专用密码"
   方式 B：App Store Connect API key
       xcrun notarytool store-credentials "redink-notary" \
         --key "/path/to/AuthKey_XXXX.p8" \
         --key-id "XXXX" --issuer "issuer-uuid"

4. 之后即可执行：
       SIGN_IDENTITY="Developer ID Application: Your Name (TEAMID)" \
       NOTARY_PROFILE="redink-notary" \
       bash scripts/sign-and-notarize.sh

提示：可先运行 `bash scripts/sign-and-notarize.sh --check` 做环境自检。
═══════════════════════════════════════════════
GUIDE
}

# ---------------------------------------------------------------------------
# --check 模式：只做环境自检，不做任何签名动作
# ---------------------------------------------------------------------------
run_check() {
  echo "==> 环境自检（不执行任何签名/公证动作）"
  echo ""

  echo "[1/4] Xcode 命令行工具"
  if xcode-select -p >/dev/null 2>&1; then
    echo "    OK：$(xcode-select -p)"
  else
    echo "    缺失：请执行 xcode-select --install 安装"
  fi
  echo ""

  echo "[2/4] 可用的代码签名证书（security find-identity）"
  local identities
  identities="$(security find-identity -v -p codesigning 2>/dev/null || true)"
  echo "${identities}" | sed 's/^/    /'
  if echo "${identities}" | grep -q "Developer ID Application"; then
    echo "    OK：找到 Developer ID Application 证书，可用于分发签名"
  else
    echo "    注意：没有 Developer ID Application 证书（分发签名必需），"
    echo "          申请方法见：bash scripts/sign-and-notarize.sh（不带参数运行）"
  fi
  echo ""

  echo "[3/4] notarytool 是否可用"
  if xcrun notarytool --version >/dev/null 2>&1; then
    echo "    OK：$(xcrun notarytool --version 2>&1 | head -n 1)"
  else
    echo "    缺失：notarytool 不可用（需 Xcode 13+ 或较新的命令行工具）"
  fi
  echo ""

  echo "[4/4] 待签名产物"
  if [ -d "${APP_PATH}" ]; then
    echo "    OK：${APP_PATH} 存在"
  else
    echo "    缺失：${APP_PATH} 不存在，请先 bash scripts/build-macos-app.sh"
  fi
  if [ -f "${DMG_PATH}" ]; then
    echo "    参考：${DMG_PATH} 已存在（签名流程中会重新生成）"
  fi
  echo ""
  echo "自检完成。"
}

if [ "${1:-}" = "--check" ]; then
  run_check
  exit 0
fi

if [ -z "${SIGN_IDENTITY}" ] || [ -z "${NOTARY_PROFILE}" ]; then
  print_prereq_guide
  exit 1
fi

fail() {
  echo "" >&2
  echo "失败：$1" >&2
  echo "排查建议：$2" >&2
  exit 1
}

# ---------------------------------------------------------------------------
# [1/7] 检查产物
# ---------------------------------------------------------------------------
echo "==> [1/7] 检查 dist/RedInk.app"
if [ ! -d "${APP_PATH}" ]; then
  fail "未找到 ${APP_PATH}" \
       "请先执行 bash scripts/build-macos-app.sh 构建应用"
fi

# ---------------------------------------------------------------------------
# [2/7] 签名 .app
#
# 关于 --deep 的说明：
#   PyInstaller 产物内嵌大量 dylib / framework / 可执行文件，签名必须
#   「由内向外」——先签最内层的二进制，最后签外层 bundle。--deep 会递归
#   签名嵌套内容，对多数 PyInstaller 应用够用，但它有已知局限（Apple 已
#   不推荐用于生产）：
#     - 对所有嵌套项套用同一套 entitlements / flags，无法按需区分；
#     - 遍历顺序不保证严格由内向外，个别深层嵌套（如 framework 里的
#       helper 可执行文件）可能漏签或签序不对；
#     - 不会处理 bundle 结构不规范的位置（如 Resources 里的 .so）。
#   更稳的逐层签名做法（若 --deep 后 verify/公证失败，改用这个）：
#     find "dist/RedInk.app/Contents" \( -name "*.dylib" -o -name "*.so" \) \
#       -exec codesign --force --options runtime --timestamp -s "$SIGN_IDENTITY" {} \;
#     然后对 Contents/Frameworks 下每个 .framework、每个嵌套可执行文件
#     逐一 codesign，最后不带 --deep 签整个 .app。
# ---------------------------------------------------------------------------
echo "==> [2/7] 代码签名 RedInk.app（identity: ${SIGN_IDENTITY}）"
codesign --force --deep --options runtime --timestamp \
  -s "${SIGN_IDENTITY}" "${APP_PATH}" \
  || fail "codesign 签名 .app 失败" \
          "确认证书名与 security find-identity -v -p codesigning 输出完全一致；若为嵌套二进制报错，参考脚本内注释改用逐层签名"

# ---------------------------------------------------------------------------
# [3/7] 验证签名
# ---------------------------------------------------------------------------
echo "==> [3/7] 验证签名（codesign --verify --deep --strict）"
codesign --verify --deep --strict --verbose=2 "${APP_PATH}" \
  || fail "签名验证未通过" \
          "常见原因：有嵌套二进制漏签或签名顺序不对。参考脚本 [2/7] 注释里的逐层签名方案重签"

# ---------------------------------------------------------------------------
# [4/7] 重新生成 DMG（必须在签名后重做，否则 DMG 里仍是未签名的 app）
# ---------------------------------------------------------------------------
echo "==> [4/7] 用已签名的 app 重新生成 DMG"
bash "${PROJECT_ROOT}/scripts/make-dmg.sh" \
  || fail "make-dmg.sh 执行失败" \
          "单独运行 bash scripts/make-dmg.sh 查看具体报错"

# ---------------------------------------------------------------------------
# [5/7] 签名 DMG
# ---------------------------------------------------------------------------
echo "==> [5/7] 代码签名 RedInk.dmg"
codesign --force --timestamp -s "${SIGN_IDENTITY}" "${DMG_PATH}" \
  || fail "codesign 签名 DMG 失败" \
          "确认 ${DMG_PATH} 存在且证书可用"

# ---------------------------------------------------------------------------
# [6/7] 提交公证并装订
#   公证 DMG 会连带公证其中的 .app；通过后对 DMG 和本地 .app 各 staple
#   一次，这样离线环境下 Gatekeeper 也能验证。
# ---------------------------------------------------------------------------
echo "==> [6/7] 提交公证（notarytool submit --wait，可能需要几分钟）"
xcrun notarytool submit "${DMG_PATH}" \
  --keychain-profile "${NOTARY_PROFILE}" --wait \
  || fail "公证未通过或提交失败" \
          "用 xcrun notarytool history --keychain-profile \"${NOTARY_PROFILE}\" 找到 submission id，再用 xcrun notarytool log <id> --keychain-profile \"${NOTARY_PROFILE}\" 查看具体被拒原因"

echo "    装订公证票据（stapler staple）"
xcrun stapler staple "${DMG_PATH}" \
  || fail "为 DMG 装订票据失败" \
          "确认公证状态为 Accepted 后重试；网络问题时稍后再跑 xcrun stapler staple"
xcrun stapler staple "${APP_PATH}" \
  || fail "为 .app 装订票据失败" \
          "确认公证状态为 Accepted 后重试；网络问题时稍后再跑 xcrun stapler staple"

# ---------------------------------------------------------------------------
# [7/7] Gatekeeper 验收
# ---------------------------------------------------------------------------
echo "==> [7/7] Gatekeeper 验收（spctl --assess）"
spctl --assess --type exec --verbose=2 "${APP_PATH}" \
  || fail ".app 未通过 Gatekeeper 评估" \
          "检查上面 spctl 输出；若提示 rejected，多为签名或公证未完全生效"
spctl --assess --type open --context context:primary-signature --verbose=2 "${DMG_PATH}" \
  || fail "DMG 未通过 Gatekeeper 评估" \
          "检查上面 spctl 输出；确认 DMG 已签名且已 staple"

echo ""
echo "签名与公证全部完成！"
echo "产物：${APP_PATH}"
echo "     ${DMG_PATH}"
echo "用户现在可以直接双击打开，不会再被 Gatekeeper 拦截。"
