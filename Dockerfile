# ============================================
# 红墨 AI图文生成器 - Docker 镜像
# ============================================

# 阶段1: 构建前端
FROM node:22-slim AS frontend-builder

WORKDIR /app/frontend

# 安装 pnpm
RUN npm install -g pnpm@10.19.0

# 复制前端依赖文件
COPY frontend/package.json frontend/pnpm-lock.yaml ./

# 安装依赖
RUN pnpm install --frozen-lockfile

# 复制前端源码
COPY frontend/ ./

# 构建前端
RUN pnpm build

# ============================================
# 阶段2: 最终镜像
FROM python:3.11-slim

WORKDIR /app

# 安装系统依赖
RUN apt-get update && apt-get install -y --no-install-recommends \
    && rm -rf /var/lib/apt/lists/*

# 安装 uv
RUN pip install --no-cache-dir uv

# 复制 Python 项目配置
COPY pyproject.toml uv.lock* ./

# 安装 Python 依赖
RUN uv sync --no-dev

# 复制后端代码
COPY backend/ ./backend/

# 复制空白配置文件模板（不包含任何 API Key）
COPY docker/text_providers.yaml ./
COPY docker/image_providers.yaml ./

# 从构建阶段复制前端产物
COPY --from=frontend-builder /app/frontend/dist ./frontend/dist

# 创建数据目录：/app/data 为统一数据根（挂载单卷即可持久化全部用户数据），
# 并放入空白配置模板；output/history 为旧版遗留路径，保留以兼容仍挂载旧目录的用户
RUN mkdir -p data output history \
    && cp text_providers.yaml image_providers.yaml data/

# 创建非特权用户并降权运行（安全加固）
RUN useradd -m -u 10001 appuser && chown -R appuser:appuser /app
USER appuser

# 设置环境变量
# FLASK_HOST=0.0.0.0 仅在容器内对外监听，实际暴露范围由 compose 端口映射控制，
# 公网部署必须设置 REDINK_ACCESS_TOKEN 启用访问鉴权（否则应用会拒绝启动，
# 除非显式设置 REDINK_ALLOW_INSECURE=1）
# REDINK_DATA_DIR=/app/data：全部用户数据（history、brand_kits、content_calendar、
# analytics_data、idea_library、clips、custom_prompts、publish_accounts.json、
# providers yaml 等）统一落在该目录，挂载一个卷即可完整持久化
ENV FLASK_DEBUG=False
ENV FLASK_HOST=0.0.0.0
ENV FLASK_PORT=12398
ENV REDINK_DATA_DIR=/app/data

# 暴露端口
EXPOSE 12398

# 健康检查
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:12398/api/health')" || exit 1

# 启动命令
CMD ["uv", "run", "python", "-m", "backend.app"]
