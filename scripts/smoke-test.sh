#!/usr/bin/env bash
# =============================================================================
# smoke-test.sh —— 全接口存活冒烟测试
#
# 用法：
#   bash scripts/smoke-test.sh
#
# 作用：
#   用 .venv 的 python 在随机空闲端口启动 Flask 后端（backend.app.create_app），
#   依次 curl 检查所有只读 GET 端点（断言 HTTP 200 且响应为 JSON；首页 / 仅断言 200），
#   输出 PASS/FAIL 表格。适合构建/发版前 30 秒内确认后端只读端点没被改挂。
#
#   - 只做 GET 请求，不调用任何 LLM/图片生成端点，不产生任何写操作与费用。
#   - 有任何 FAIL 时退出码为 1（失败会全部收集完再退出）。
#   - 后端启动失败（如并行开发导致的偶发 import 错误）会等 30 秒自动重试一次。
# =============================================================================
set -uo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PYTHON="$ROOT_DIR/.venv/bin/python"
BACKEND_PID=""
BACKEND_LOG="$(mktemp -t redink-smoke-backend)"

cleanup() {
    if [[ -n "$BACKEND_PID" ]] && kill -0 "$BACKEND_PID" 2>/dev/null; then
        kill "$BACKEND_PID" 2>/dev/null
        wait "$BACKEND_PID" 2>/dev/null
    fi
    rm -f "$BACKEND_LOG"
}
trap cleanup EXIT INT TERM

if [[ ! -x "$PYTHON" ]]; then
    echo "ERROR: 找不到 .venv 的 python：$PYTHON" >&2
    exit 1
fi

# ---------- 找随机空闲端口（避开 12398） ----------
pick_port() {
    "$PYTHON" - <<'EOF'
import socket
while True:
    s = socket.socket()
    s.bind(("127.0.0.1", 0))
    port = s.getsockname()[1]
    s.close()
    if port != 12398:
        print(port)
        break
EOF
}

# ---------- 启动后端并轮询 /api/health（最多 20s） ----------
start_backend() {
    PORT="$(pick_port)"
    BASE_URL="http://127.0.0.1:$PORT"
    (
        cd "$ROOT_DIR" || exit 1
        exec "$PYTHON" -c "from backend.app import create_app; create_app().run(port=$PORT)"
    ) >"$BACKEND_LOG" 2>&1 &
    BACKEND_PID=$!

    local waited=0
    while (( waited < 20 )); do
        if curl -sf -o /dev/null "$BASE_URL/api/health"; then
            return 0
        fi
        if ! kill -0 "$BACKEND_PID" 2>/dev/null; then
            return 1  # 进程已退出（多半是 import 失败）
        fi
        sleep 1
        (( waited++ ))
    done
    return 1
}

echo "==> 启动后端..."
if ! start_backend; then
    echo "WARN: 后端启动失败（可能是并行修改导致的偶发 import 失败），30 秒后重试一次..." >&2
    tail -5 "$BACKEND_LOG" >&2
    cleanup_pid="$BACKEND_PID"
    [[ -n "$cleanup_pid" ]] && kill "$cleanup_pid" 2>/dev/null
    BACKEND_PID=""
    sleep 30
    if ! start_backend; then
        echo "ERROR: 后端二次启动仍失败，放弃。最后日志：" >&2
        tail -20 "$BACKEND_LOG" >&2
        exit 1
    fi
fi
echo "==> 后端已就绪：$BASE_URL (pid=$BACKEND_PID)"
echo ""

# ---------- 端点清单（均为只读 GET，不花钱、不写数据） ----------
# 格式：路径|是否要求 JSON（json/any）
ENDPOINTS=(
    "/|any"
    "/api/health|json"
    "/api/config|json"
    "/api/config/image-prompt|json"
    "/api/history|json"
    "/api/history/search?keyword=smoke|json"
    "/api/history/stats|json"
    "/api/analytics/records|json"
    "/api/analytics/stats|json"
    "/api/plans|json"
    "/api/plans/stats|json"
    "/api/brands|json"
    "/api/brands/active|json"
)

pass=0
fail=0
results=()

for entry in "${ENDPOINTS[@]}"; do
    path="${entry%%|*}"
    kind="${entry##*|}"

    body_file="$(mktemp -t redink-smoke-body)"
    http_code="$(curl -s -o "$body_file" -w '%{http_code}' --max-time 10 "$BASE_URL$path")"

    status="PASS"
    detail="HTTP $http_code"
    if [[ "$http_code" != "200" ]]; then
        status="FAIL"
    elif [[ "$kind" == "json" ]]; then
        if ! "$PYTHON" -c "import json,sys; json.load(open(sys.argv[1]))" "$body_file" 2>/dev/null; then
            status="FAIL"
            detail="HTTP $http_code (非 JSON 响应)"
        fi
    fi
    rm -f "$body_file"

    if [[ "$status" == "PASS" ]]; then
        (( pass++ ))
    else
        (( fail++ ))
    fi
    results+=("$status|$path|$detail")
done

# ---------- 输出对齐表格 ----------
printf '%-6s %-42s %s\n' "RESULT" "ENDPOINT" "DETAIL"
printf '%-6s %-42s %s\n' "------" "------------------------------------------" "----------------"
for r in "${results[@]}"; do
    IFS='|' read -r st ep dt <<<"$r"
    printf '%-6s %-42s %s\n' "$st" "$ep" "$dt"
done
echo ""
echo "总结: $pass passed, $fail failed (共 ${#ENDPOINTS[@]} 个端点)"

if (( fail > 0 )); then
    exit 1
fi
exit 0
