#!/usr/bin/env bash
# =============================================================================
# smoke-docker-persistence.sh —— Docker 单卷持久化冒烟测试（Wave 0 / G1 验收证据）
#
# 验收目标：
#   容器删除重建（docker compose down → up，不带 -v）后，REDINK_DATA_DIR=/app/data
#   单卷内的用户数据零丢失 —— 对数据资产注册表（backend/data_catalog.py）中的
#   多个资产逐文件 sha256 比对，全部一致才判 PASS。
#
# 用法：
#   bash scripts/smoke-docker-persistence.sh [--keep]
#
#   --keep    结束后保留现场（临时工作区、容器、临时镜像）便于人工排查，
#             并打印手工清理命令；默认无论成败都在 EXIT trap 里自动清理。
#
# 前提：
#   本机 Docker（Docker Desktop 或 dockerd）正在运行，宿主 12398 端口空闲
#   （沿用仓库 compose 的宿主回环端口映射 127.0.0.1:12398:12398）。
#
# 隔离性（保证不污染仓库根目录的 ./data）：
#   - 工作区建在 /tmp 下（macOS Docker Desktop 默认文件共享白名单覆盖 /tmp）；
#   - docker compose 用 --project-directory 指向临时目录：基座 compose 里的
#     相对路径 ./data 会解析到 <临时目录>/data，而不是仓库根目录；
#   - 同时生成临时 override，以绝对路径显式改写数据卷（compose 对 volumes 按
#     容器内目标路径合并，/app/data 这一项被 override 替换），双保险；
#   - 容器起来后还会 docker inspect 实际挂载，断言卷源确实落在临时目录，
#     不满足立即中止。
#
# 流程：
#   1) 预检 docker / compose / curl / sha256 工具与 12398 端口
#   2) docker build 本仓库 Dockerfile → 临时 tag（不拉取 histonemax/redink:latest）
#   3) compose up，轮询无鉴权健康检查端点 GET /api/health（backend/routes/
#      image_routes.py 定义、app.py 令牌鉴权豁免、Dockerfile HEALTHCHECK 同款），
#      120 秒未就绪判 FAIL
#   4) 写标记数据：history/ idea_library/ clips/ custom_prompts/ 各写一个标记
#      文件（docker exec 以容器用户 uid 10001 写入 /app/data，宿主侧断言文件
#      同步出现在临时卷目录 —— 兼顾 Linux 上目录属主为 10001 时宿主直写会被
#      权限拒绝的问题，也反向验证了卷挂载的对应关系）；publish_accounts.json
#      经 POST /api/publish/accounts 由应用进程写入标记账号（验证
#      应用 → REDINK_DATA_DIR → 卷 的完整写链路）
#   5) 记录各文件 sha256 → compose down（删除容器，不带 -v）→ up 重建 →
#      逐文件比对 sha256
#   6) 附加断言：容器内 REDINK_DATA_DIR=/app/data 生效；容器内看到的各文件与
#      宿主卷逐字节一致（docker exec 内计算 sha256 对比）；重启后 API 能读回
#      标记账号
#   7) EXIT trap 无论成败都清理：down --volumes、删临时镜像 tag、删临时目录
#      （--keep 时跳过并打印手工清理命令）
#
# 退出码：0 = PASS；1 = FAIL（含预检失败/就绪超时）；2 = 参数错误。
# 兼容 macOS 自带 bash 3.2（不使用关联数组 / mapfile 等 bash4+ 特性）。
# =============================================================================
set -euo pipefail

# ---------- 常量与全局状态 ----------
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
COMPOSE_FILE="$ROOT_DIR/docker-compose.yml"

HOST_PORT=12398                                  # 沿用仓库 compose 的宿主回环端口
BASE_URL="http://127.0.0.1:${HOST_PORT}"
HEALTH_URL="${BASE_URL}/api/health"              # 无鉴权健康检查端点
HEALTH_TIMEOUT=120                               # 就绪轮询超时（秒），超时判 FAIL

SUFFIX="$(date +%Y%m%d%H%M%S)-$$"                # 本次运行唯一后缀
IMAGE_TAG="redink-smoke:${SUFFIX}"               # 本地构建的临时镜像 tag
CONTAINER_NAME="redink-smoke-${SUFFIX}"          # 避免与正式 redink 容器重名
PROJECT_NAME="redink-smoke-${SUFFIX}"            # 独立 compose 项目名

KEEP=0
COMPOSE_CMD=""                                   # "docker compose" 或 "docker-compose"
WORK_DIR=""                                      # 临时工作区（数据卷落在这里）
OVERRIDE_FILE=""
IMAGE_BUILT=0
COMPOSE_STARTED=0
CHECKS_TOTAL=0
FAILURES=()

usage() {
    cat <<'EOF'
用法: bash scripts/smoke-docker-persistence.sh [--keep]

  --keep      测试结束后保留现场（临时目录、容器、临时镜像）便于人工排查
  -h, --help  显示本帮助
EOF
}

while [ $# -gt 0 ]; do
    case "$1" in
        --keep) KEEP=1 ;;
        -h|--help) usage; exit 0 ;;
        *) echo "未知参数: $1" >&2; usage >&2; exit 2 ;;
    esac
    shift
done

# ---------- 通用辅助函数 ----------
log() { printf '[%s] %s\n' "$(date +%H:%M:%S)" "$*"; }

check_pass() { CHECKS_TOTAL=$((CHECKS_TOTAL + 1)); printf '[PASS] %s\n' "$*"; }
check_fail() { CHECKS_TOTAL=$((CHECKS_TOTAL + 1)); printf '[FAIL] %s\n' "$*"; FAILURES+=("$*"); }

# compose 包装：始终带上 基座文件 + 临时 override + 临时项目目录 + 独立项目名
# （COMPOSE_CMD 取值固定为 "docker compose" / "docker-compose"，依赖单词拆分，不加引号）
compose() {
    $COMPOSE_CMD -f "$COMPOSE_FILE" -f "$OVERRIDE_FILE" \
        --project-directory "$WORK_DIR" -p "$PROJECT_NAME" "$@"
}

dump_logs() {
    if [ "$COMPOSE_STARTED" -eq 1 ]; then
        echo "---------- 容器日志（最近 100 行，便于排查） ----------"
        compose logs --tail=100 2>&1 || true
        echo "-------------------------------------------------------"
    fi
}

# 硬失败：打印原因（附容器日志）并以 FAIL 退出，清理交给 EXIT trap
die() {
    printf '[FAIL] %s\n' "$*" >&2
    dump_logs
    echo "RESULT: FAIL"
    exit 1
}

# 宿主侧 sha256（macOS 用 shasum -a 256，Linux 用 sha256sum，预检保证至少其一可用）
hash_file() {
    if command -v sha256sum >/dev/null 2>&1; then
        sha256sum "$1" | awk '{print $1}'
    else
        shasum -a 256 "$1" | awk '{print $1}'
    fi
}

# 容器内 sha256：用基础镜像自带的 python3 计算，不依赖容器内是否装有 coreutils
container_hash() {
    docker exec "$CONTAINER_NAME" python3 -c \
        'import hashlib,sys;print(hashlib.sha256(open(sys.argv[1],"rb").read()).hexdigest())' "$1"
}

gen_uuid() {
    if command -v uuidgen >/dev/null 2>&1; then
        uuidgen
    else
        printf '%s-%s-%s\n' "$(date +%s)" "$$" "$RANDOM"
    fi
}

# 轮询健康检查端点直至就绪；超时返回 1
wait_ready() {
    local label="$1"
    local start elapsed
    start=$SECONDS
    while :; do
        if curl -fsS -m 5 -o /dev/null "$HEALTH_URL" 2>/dev/null; then
            elapsed=$((SECONDS - start))
            log "${label}: 服务就绪（耗时 ${elapsed}s，GET ${HEALTH_URL} 返回 200）"
            return 0
        fi
        elapsed=$((SECONDS - start))
        if [ "$elapsed" -ge "$HEALTH_TIMEOUT" ]; then
            return 1
        fi
        sleep 2
    done
}

# 断言 override 确实生效：容器存在、镜像是本地临时 tag、数据卷源落在临时目录
assert_container() {
    local img mounts
    img="$(docker inspect -f '{{.Config.Image}}' "$CONTAINER_NAME" 2>/dev/null)" \
        || die "找不到容器 ${CONTAINER_NAME}（override 未生效？）"
    [ "$img" = "$IMAGE_TAG" ] \
        || die "容器镜像不是本地临时镜像（实际: ${img}，期望: ${IMAGE_TAG}），拒绝继续"
    mounts="$(docker inspect -f '{{range .Mounts}}{{.Source}} => {{.Destination}}{{"\n"}}{{end}}' "$CONTAINER_NAME")"
    # macOS 上 /tmp 是 /private/tmp 的符号链接，Docker 记录的挂载源两种写法都认可
    if ! printf '%s' "$mounts" | grep -Fq \
        -e "${WORK_DIR}/data => /app/data" \
        -e "/private${WORK_DIR}/data => /app/data"; then
        echo "实际挂载:"
        printf '%s\n' "$mounts"
        die "数据卷未落在临时目录（应为 ${WORK_DIR}/data => /app/data），中止以免污染仓库 ./data"
    fi
    log "挂载断言通过: ${WORK_DIR}/data => /app/data（镜像 ${IMAGE_TAG}）"
}

# ---------- 收尾清理（无论成败都执行；--keep 时保留现场） ----------
cleanup() {
    if [ "$KEEP" -eq 1 ]; then
        echo ""
        echo "[--keep] 已保留现场，排查完请手动清理："
        echo "  临时工作区 : ${WORK_DIR:-（未创建）}"
        echo "  临时镜像   : ${IMAGE_TAG}（已构建: ${IMAGE_BUILT}）"
        echo "  容器/项目  : ${CONTAINER_NAME} / ${PROJECT_NAME}"
        if [ -n "$WORK_DIR" ] && [ -n "$COMPOSE_CMD" ]; then
            echo "  清理命令   :"
            echo "    ${COMPOSE_CMD} -f \"${COMPOSE_FILE}\" -f \"${OVERRIDE_FILE}\" --project-directory \"${WORK_DIR}\" -p \"${PROJECT_NAME}\" down --volumes --remove-orphans"
            echo "    docker rmi -f \"${IMAGE_TAG}\""
            echo "    rm -rf \"${WORK_DIR}\""
        fi
        return 0
    fi
    # 先停删容器（--volumes 针对临时项目；绑定挂载的目录本体随后 rm -rf 删除），
    # 再删临时镜像与临时工作区。清理全程容错，不影响脚本最终退出码。
    if [ -n "$COMPOSE_CMD" ] && [ -n "$OVERRIDE_FILE" ] && [ -f "$OVERRIDE_FILE" ]; then
        compose down --volumes --remove-orphans >/dev/null 2>&1 || true
    fi
    if [ "$IMAGE_BUILT" -eq 1 ]; then
        docker rmi -f "$IMAGE_TAG" >/dev/null 2>&1 || true
    fi
    if [ -n "$WORK_DIR" ] && [ -d "$WORK_DIR" ]; then
        rm -rf "$WORK_DIR" || true
    fi
}
trap cleanup EXIT
trap 'exit 130' INT TERM

# =============================================================================
# 1) 预检
# =============================================================================
log "=== RedInk Docker 单卷持久化冒烟测试（G1）==="
log "仓库: $ROOT_DIR"

[ -f "$ROOT_DIR/Dockerfile" ] || die "未找到 ${ROOT_DIR}/Dockerfile"
[ -f "$COMPOSE_FILE" ] || die "未找到 ${COMPOSE_FILE}"

command -v docker >/dev/null 2>&1 \
    || die "未检测到 docker CLI。请先安装并启动 Docker（Docker Desktop / dockerd）后重试"
docker info >/dev/null 2>&1 \
    || die "Docker 守护进程不可用（Docker Desktop 未启动？）。请启动 Docker 后重试"

if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    die "未检测到 docker compose（v2 插件）或 docker-compose（v1）"
fi
log "预检通过: docker 可用，compose 命令为 '${COMPOSE_CMD}'"

command -v curl >/dev/null 2>&1 || die "未检测到 curl"
command -v sha256sum >/dev/null 2>&1 || command -v shasum >/dev/null 2>&1 \
    || die "未检测到 sha256sum / shasum，无法做哈希比对"

# 端口预检：仓库 compose 固定映射宿主 127.0.0.1:12398。常见占用者是本机正在
# 运行的正式 redink 容器或开发后端 —— 提前给出清晰报错，避免 compose 起一半失败。
if (exec 3<>"/dev/tcp/127.0.0.1/${HOST_PORT}") 2>/dev/null; then
    exec 3>&- 3<&- || true
    die "宿主端口 127.0.0.1:${HOST_PORT} 已被占用（本机可能正跑着 RedInk？），请先释放端口再执行"
fi

# =============================================================================
# 2) 隔离工作区 + 临时 override
# =============================================================================
# 工作区放 /tmp：macOS 的 \$TMPDIR 在 /var/folders 下，可能不在 Docker Desktop
# 文件共享白名单内导致绑定挂载被拒；/tmp（实为 /private/tmp）默认在白名单里。
WORK_DIR="$(mktemp -d /tmp/redink-smoke.XXXXXX)"
mkdir -p "$WORK_DIR/data"
# 容器以非特权 uid 10001 运行；Linux 宿主上放开临时数据目录权限让容器可写
# （macOS Docker Desktop 有 uid 透明映射，此行无副作用）。只动临时目录，不碰仓库。
chmod 777 "$WORK_DIR/data"

OVERRIDE_FILE="$WORK_DIR/override.yml"
# 临时 override 说明：
# - image / container_name / restart 为标量，直接替换基座值：用本地构建的临时
#   镜像（绝不拉取 histonemax/redink:latest）、专属容器名（避免撞正式容器）、
#   restart=no（临时容器不要带 unless-stopped 自启策略）；
# - volumes 按容器内目标路径 /app/data 合并，本条以绝对路径替换基座的 ./data，
#   与 --project-directory 双保险，确保数据卷落在临时目录。
cat >"$OVERRIDE_FILE" <<EOF
services:
  redink:
    image: ${IMAGE_TAG}
    container_name: ${CONTAINER_NAME}
    restart: "no"
    volumes:
      - "${WORK_DIR}/data:/app/data"
EOF
log "隔离工作区: ${WORK_DIR}（数据卷 = ${WORK_DIR}/data，不触碰仓库 ./data）"

# =============================================================================
# 3) 本地构建镜像
# =============================================================================
BUILD_LOG="$WORK_DIR/build.log"
log "开始本地构建镜像 ${IMAGE_TAG}（前端 pnpm build + 后端依赖安装，可能需要几分钟）…"
if ! docker build -t "$IMAGE_TAG" "$ROOT_DIR" >"$BUILD_LOG" 2>&1; then
    echo "---------- 构建日志（最后 60 行） ----------"
    tail -n 60 "$BUILD_LOG" || true
    echo "--------------------------------------------"
    die "docker build 失败（完整日志在 ${BUILD_LOG}，随临时目录清理；加 --keep 可保留现场复查）"
fi
IMAGE_BUILT=1
log "镜像构建完成: ${IMAGE_TAG}"

# =============================================================================
# 4) 首次启动 + 就绪轮询
# =============================================================================
COMPOSE_STARTED=1
log "首次启动容器（compose up -d）…"
compose up -d || die "docker compose up 失败"
assert_container
wait_ready "首次启动" || die "首次启动 ${HEALTH_TIMEOUT}s 内未就绪（GET ${HEALTH_URL}）"

# =============================================================================
# 5) 写入标记数据（覆盖注册表中的 5 个资产）并记录 sha256
# =============================================================================
RUN_UUID="$(gen_uuid)"
log "写入标记数据（run=${SUFFIX} uuid=${RUN_UUID}）…"

# 5.1 容器内写标记文件：注册表中 4 个 core_data 目录各写一个唯一内容的标记文件。
#     用 docker exec（以镜像默认用户 uid 10001 运行）写 /app/data，规避 Linux 上
#     子目录属主为 10001 时宿主直写被拒的问题；随后断言文件同步出现在宿主临时卷，
#     反向验证卷挂载对应关系。umask 022 保证 644 权限，宿主侧可读可哈希。
for d in history idea_library clips custom_prompts; do
    docker exec "$CONTAINER_NAME" sh -c "umask 022 && mkdir -p '/app/data/${d}' && printf '%s\n' \
        'redink docker persistence smoke marker' \
        'asset=${d}' 'run=${SUFFIX}' 'uuid=${RUN_UUID}' \
        >'/app/data/${d}/SMOKE_MARKER_${d}.txt'" \
        || die "容器内写入标记文件失败: ${d}/"
    [ -f "$WORK_DIR/data/$d/SMOKE_MARKER_${d}.txt" ] \
        || die "标记文件未同步出现在宿主卷: ${d}/SMOKE_MARKER_${d}.txt（卷挂载对应关系异常）"
done
log "4 个目录资产的标记文件已写入并同步到宿主卷"

# 5.2 经应用 API 写 publish_accounts.json（platform 取后端白名单值 xiaohongshu），
#     验证 应用进程 → REDINK_DATA_DIR=/app/data → 宿主卷 的完整写链路
MARKER_NICK="SMOKE-${SUFFIX}"
RESP="$(curl -sS -m 10 -X POST -H 'Content-Type: application/json' \
    -d "{\"platform\":\"xiaohongshu\",\"nickname\":\"${MARKER_NICK}\",\"notes\":\"smoke-docker-persistence 标记账号\"}" \
    "${BASE_URL}/api/publish/accounts")" || die "POST /api/publish/accounts 请求失败"
printf '%s' "$RESP" | grep -Eq '"success"[[:space:]]*:[[:space:]]*true' \
    || { echo "API 响应: $RESP"; die "写入标记账号失败（API 未返回 success:true）"; }
# 应用用 mkstemp 原子写，落盘权限为 600（属主 uid 10001）：Linux 宿主读不了会导致
# 哈希失败。这里放开到 644 —— 只动临时工作区里的副本，不影响内容与哈希值。
docker exec "$CONTAINER_NAME" chmod 644 /app/data/publish_accounts.json \
    || die "调整 publish_accounts.json 权限失败"
[ -f "$WORK_DIR/data/publish_accounts.json" ] \
    || die "publish_accounts.json 未出现在宿主卷内（REDINK_DATA_DIR 或卷挂载未生效）"
grep -Fq "$MARKER_NICK" "$WORK_DIR/data/publish_accounts.json" \
    || die "宿主卷内 publish_accounts.json 不含标记账号 ${MARKER_NICK}"
log "标记账号已通过 API 写入并落盘到宿主卷: publish_accounts.json"

# 5.3 记录重建前各标记文件的 sha256（与 MARKER_RELS 同序存入 BEFORE_HASHES）
MARKER_RELS=(
    "history/SMOKE_MARKER_history.txt"
    "idea_library/SMOKE_MARKER_idea_library.txt"
    "clips/SMOKE_MARKER_clips.txt"
    "custom_prompts/SMOKE_MARKER_custom_prompts.txt"
    "publish_accounts.json"
)
BEFORE_HASHES=()
log "记录重建前各标记文件的 sha256："
for rel in "${MARKER_RELS[@]}"; do
    h="$(hash_file "$WORK_DIR/data/$rel")"
    BEFORE_HASHES+=("$h")
    log "  ${h}  ${rel}"
done

# =============================================================================
# 6) 容器删除重建（down 不带 -v → up）
# =============================================================================
log "删除容器（compose down，不带 -v，保留数据卷）…"
compose down || die "docker compose down 失败"
if docker container inspect "$CONTAINER_NAME" >/dev/null 2>&1; then
    die "down 之后容器仍存在，未达成「容器删除」前提"
fi
log "容器已删除。重新创建并启动（compose up -d）…"
compose up -d || die "重建 docker compose up 失败"
assert_container
wait_ready "重建启动" || die "重建后 ${HEALTH_TIMEOUT}s 内未就绪（GET ${HEALTH_URL}）"

# =============================================================================
# 7) 校验：数据零丢失 + REDINK_DATA_DIR 生效
# =============================================================================
echo ""
log "开始校验（容器删除重建后数据零丢失 + REDINK_DATA_DIR=/app/data 生效）："

# 7.1 宿主卷逐文件 sha256 比对
i=0
n=${#MARKER_RELS[@]}
while [ "$i" -lt "$n" ]; do
    rel="${MARKER_RELS[$i]}"
    want="${BEFORE_HASHES[$i]}"
    path="$WORK_DIR/data/$rel"
    if [ ! -f "$path" ]; then
        check_fail "宿主卷文件丢失: ${rel}"
    elif got="$(hash_file "$path" 2>/dev/null)" && [ "$got" = "$want" ]; then
        check_pass "宿主卷 sha256 一致: ${rel}"
    else
        check_fail "宿主卷 sha256 不一致: ${rel}（重建前 ${want} / 重建后 ${got:-<读取失败>}）"
    fi
    i=$((i + 1))
done

# 7.2 重建后的应用能通过 API 读回标记账号（端到端读链路）
if RESP2="$(curl -sS -m 10 "${BASE_URL}/api/publish/accounts" 2>/dev/null)" \
    && printf '%s' "$RESP2" | grep -Fq "$MARKER_NICK"; then
    check_pass "重建后 GET /api/publish/accounts 读回标记账号 ${MARKER_NICK}"
else
    check_fail "重建后 API 未读回标记账号 ${MARKER_NICK}"
fi

# 7.3 容器内 REDINK_DATA_DIR=/app/data 生效
if env_val="$(docker exec "$CONTAINER_NAME" sh -c 'printf "%s" "$REDINK_DATA_DIR"' 2>/dev/null)" \
    && [ "$env_val" = "/app/data" ]; then
    check_pass "容器内环境变量 REDINK_DATA_DIR=/app/data"
else
    check_fail "容器内 REDINK_DATA_DIR 异常（实际: '${env_val:-<读取失败>}'）"
fi

# 7.4 容器内目录内容与宿主卷一致：docker exec 在容器内算 sha256，与重建前比对
i=0
while [ "$i" -lt "$n" ]; do
    rel="${MARKER_RELS[$i]}"
    want="${BEFORE_HASHES[$i]}"
    if ch="$(container_hash "/app/data/$rel" 2>/dev/null)" && [ "$ch" = "$want" ]; then
        check_pass "容器内 /app/data/${rel} sha256 与宿主一致"
    else
        check_fail "容器内 /app/data/${rel} 不可读或 sha256 不一致（容器内: '${ch:-<失败>}'，期望: ${want}）"
    fi
    i=$((i + 1))
done

# =============================================================================
# 8) 汇总
# =============================================================================
echo ""
echo "======================================================="
if [ "${#FAILURES[@]}" -eq 0 ]; then
    echo "RESULT: PASS （${CHECKS_TOTAL}/${CHECKS_TOTAL} 项校验全部通过）"
    echo "结论: 容器删除重建后数据零丢失，REDINK_DATA_DIR=/app/data 单卷持久化生效。"
    exit 0
else
    echo "未通过项（${#FAILURES[@]}/${CHECKS_TOTAL}）："
    for f in "${FAILURES[@]}"; do
        echo "  - ${f}"
    done
    dump_logs
    echo "RESULT: FAIL"
    exit 1
fi
