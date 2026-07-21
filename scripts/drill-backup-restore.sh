#!/usr/bin/env bash
# 通过真实 HTTP API 演练 RedInk manifest v2 备份与恢复。
# 设计为在隔离的源码、Docker、桌面打包环境中复用。
set -euo pipefail

BASE_URL="${1:-http://127.0.0.1:12398}"
BASE_URL="${BASE_URL%/}"
RUN_ID="$(date +%s)-$$"
SOURCE_NICK="G1-SOURCE-${RUN_ID}"
STALE_NICK="G1-STALE-${RUN_ID}"
WORK_DIR="$(mktemp -d "${TMPDIR:-/tmp}/redink-backup-drill.XXXXXX")"
BACKUP_ZIP="${WORK_DIR}/backup.zip"
SOURCE_ID=""
STALE_ID=""

log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }
pass() { printf '[PASS] %s\n' "$*"; }
die() { printf '[FAIL] %s\nRESULT: FAIL\n' "$*" >&2; exit 1; }
api_curl() {
    # --noproxy '*'：避免本机演练被 HTTP_PROXY / 系统代理劫持到外网导致假超时
    if [ -n "${REDINK_ACCESS_TOKEN:-}" ]; then
        curl -fsS --noproxy '*' --max-time 20 \
            -H "X-Access-Token: ${REDINK_ACCESS_TOKEN}" "$@"
    else
        curl -fsS --noproxy '*' --max-time 20 "$@"
    fi
}

cleanup() {
    # 演练账号无论成功失败都尽量删除，避免污染被测环境。
    if [ -n "$SOURCE_ID" ]; then
        api_curl -X DELETE "${BASE_URL}/api/publish/accounts/${SOURCE_ID}" \
            >/dev/null 2>&1 || true
    fi
    if [ -n "$STALE_ID" ]; then
        api_curl -X DELETE "${BASE_URL}/api/publish/accounts/${STALE_ID}" \
            >/dev/null 2>&1 || true
    fi
    rm -rf "$WORK_DIR"
}
trap cleanup EXIT

command -v curl >/dev/null 2>&1 || die "未检测到 curl"
command -v python3 >/dev/null 2>&1 || die "未检测到 python3"

log "等待被测服务就绪: ${BASE_URL}"
ready=0
for _ in $(seq 1 60); do
    if api_curl "${BASE_URL}/api/health" >/dev/null 2>&1; then
        ready=1
        break
    fi
    sleep 1
done
[ "$ready" -eq 1 ] || die "60 秒内未等到 /api/health"
pass "服务健康检查通过"

SOURCE_PAYLOAD="$(python3 - "$SOURCE_NICK" <<'PY'
import json
import sys
print(json.dumps({
    "platform": "douyin",
    "nickname": sys.argv[1],
    "notes": "backup restore drill source marker",
}, ensure_ascii=False))
PY
)"
api_curl \
    -H 'Content-Type: application/json' \
    --data-binary "$SOURCE_PAYLOAD" \
    "${BASE_URL}/api/publish/accounts" >"${WORK_DIR}/source.json"
SOURCE_ID="$(python3 - "${WORK_DIR}/source.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    payload = json.load(f)
assert payload.get("success") is True, payload
print(payload["account"]["id"])
PY
)"
pass "源标记账号已写入"

EXPORT_BODY='{"local_storage":{"generator-state":"{\"topic\":\"g1-backup-drill\"}","redink_custom_styles":"[{\"id\":\"g1-style\"}]"}}'
api_curl \
    -H 'Content-Type: application/json' \
    --data-binary "$EXPORT_BODY" \
    "${BASE_URL}/api/data/export" >"$BACKUP_ZIP"

python3 - "$BACKUP_ZIP" <<'PY'
import hashlib
import json
import sys
import zipfile

with zipfile.ZipFile(sys.argv[1]) as zf:
    manifest = json.loads(zf.read("manifest.json"))
    assert manifest["app"] == "RedInk", manifest
    assert manifest["format"] == 2, manifest
    records = {item["path"]: item for item in manifest["files"]}
    assert "publish_accounts.json" in records, records
    assert "frontend/local_storage.json" in records, records
    for path, record in records.items():
        raw = zf.read(path)
        assert len(raw) == record["size"], path
        assert hashlib.sha256(raw).hexdigest() == record["sha256"], path
print("[PASS] manifest v2 文件清单、大小与 sha256 全部一致")
PY

api_curl \
    -X DELETE "${BASE_URL}/api/publish/accounts/${SOURCE_ID}" \
    >"${WORK_DIR}/delete-source.json"

STALE_PAYLOAD="$(python3 - "$STALE_NICK" <<'PY'
import json
import sys
print(json.dumps({
    "platform": "xiaohongshu",
    "nickname": sys.argv[1],
    "notes": "backup restore drill stale marker",
}, ensure_ascii=False))
PY
)"
api_curl \
    -H 'Content-Type: application/json' \
    --data-binary "$STALE_PAYLOAD" \
    "${BASE_URL}/api/publish/accounts" >"${WORK_DIR}/stale.json"
STALE_ID="$(python3 - "${WORK_DIR}/stale.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    payload = json.load(f)
assert payload.get("success") is True, payload
print(payload["account"]["id"])
PY
)"
pass "目标端差异数据已构造（源标记删除、过期标记新增）"

api_curl \
    -X POST -F "file=@${BACKUP_ZIP};type=application/zip" \
    "${BASE_URL}/api/data/import" >"${WORK_DIR}/import.json"

python3 - "${WORK_DIR}/import.json" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    payload = json.load(f)
assert payload.get("success") is True, payload
assert payload["manifest"]["version"], payload
assert payload["pre_import_backup"], payload
local = payload.get("local_storage")
assert local == {
    "generator-state": '{"topic":"g1-backup-drill"}',
    "redink_custom_styles": '[{"id":"g1-style"}]',
}, local
print("[PASS] localStorage 两项资产原样往返，导入前快照已创建")
PY

api_curl \
    "${BASE_URL}/api/publish/accounts" >"${WORK_DIR}/accounts.json"
python3 - "${WORK_DIR}/accounts.json" "$SOURCE_NICK" "$STALE_NICK" <<'PY'
import json
import sys
with open(sys.argv[1], encoding="utf-8") as f:
    payload = json.load(f)
assert payload.get("success") is True, payload
names = {item.get("nickname") for item in payload["accounts"]}
assert sys.argv[2] in names, (sys.argv[2], names)
assert sys.argv[3] not in names, (sys.argv[3], names)
print("[PASS] 核心数据恢复成功，目标端过期数据按全量替换语义清除")
PY

echo "RESULT: PASS"
