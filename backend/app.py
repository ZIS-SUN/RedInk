import hmac
import logging
import os
import sys
from pathlib import Path
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from backend.config import Config
from backend.routes import register_routes


def setup_logging():
    """配置日志系统"""
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除已有的处理器
    root_logger.handlers.clear()

    # 控制台处理器 - 详细格式
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(logging.DEBUG)
    console_format = logging.Formatter(
        '\n%(asctime)s | %(levelname)-8s | %(name)s\n'
        '  └─ %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_format)
    root_logger.addHandler(console_handler)

    # 设置各模块的日志级别
    logging.getLogger('backend').setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return root_logger


def create_app():
    # 设置日志
    logger = setup_logging()
    logger.info("🚀 正在启动 红墨 AI图文生成器...")

    # 检查是否存在前端构建产物（Docker 环境）
    frontend_dist = Path(__file__).parent.parent / 'frontend' / 'dist'
    if frontend_dist.exists():
        logger.info("📦 检测到前端构建产物，启用静态文件托管模式")
        app = Flask(
            __name__,
            static_folder=str(frontend_dist),
            static_url_path=''
        )
    else:
        logger.info("🔧 开发模式，前端请单独启动")
        app = Flask(__name__)

    app.config.from_object(Config)

    CORS(app, resources={
        r"/api/*": {
            "origins": Config.CORS_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            # 允许携带访问令牌相关请求头（启用 REDINK_ACCESS_TOKEN 鉴权时需要）
            "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"],
        }
    })

    # 可选的部署级访问令牌鉴权（未设置 REDINK_ACCESS_TOKEN 时不启用，本地开箱即用）
    _register_access_token_auth(app, logger)

    # 注册所有 API 路由
    register_routes(app)

    # 启动时验证配置
    _validate_config_on_startup(logger)

    # 根据是否有前端构建产物决定根路由行为
    if frontend_dist.exists():
        @app.route('/')
        def serve_index():
            return send_from_directory(app.static_folder, 'index.html')

        # 处理 Vue Router 的 HTML5 History 模式
        @app.errorhandler(404)
        def fallback(e):
            return send_from_directory(app.static_folder, 'index.html')
    else:
        @app.route('/')
        def index():
            return {
                "message": "红墨 AI图文生成器 API",
                "version": "0.1.0",
                "endpoints": {
                    "health": "/api/health",
                    "outline": "POST /api/outline",
                    "generate": "POST /api/generate",
                    "images": "GET /api/images/<filename>"
                }
            }

    return app


def _register_access_token_auth(app, logger):
    """注册可选的部署级访问令牌鉴权。

    设置环境变量 REDINK_ACCESS_TOKEN 后启用：所有 /api/* 请求（健康检查除外）
    必须携带 `Authorization: Bearer <token>` 或 `X-Access-Token: <token>` 请求头，
    否则返回 401。未设置该环境变量时完全不启用，保持本地开箱即用。
    """
    access_token = os.getenv('REDINK_ACCESS_TOKEN', '').strip()
    if not access_token:
        return

    from backend.errors import AppError
    from backend.routes.utils import api_error_response

    logger.info("🔒 已启用访问令牌鉴权（REDINK_ACCESS_TOKEN）")

    @app.before_request
    def _check_access_token():
        # 放行 CORS 预检请求，避免破坏跨域
        if request.method == 'OPTIONS':
            return None

        # 只保护 API 接口；静态资源（前端页面）与健康检查直接放行
        path = request.path
        if not path.startswith('/api/') or path == '/api/health':
            return None

        supplied = ''
        auth_header = request.headers.get('Authorization', '')
        if auth_header.startswith('Bearer '):
            supplied = auth_header[len('Bearer '):].strip()
        if not supplied:
            supplied = request.headers.get('X-Access-Token', '').strip()

        if supplied and hmac.compare_digest(supplied, access_token):
            return None

        return api_error_response(AppError(
            code="UNAUTHORIZED",
            title="访问未授权",
            detail="缺少或无效的访问令牌",
            suggestion="请在请求头携带 Authorization: Bearer <token> 或 X-Access-Token: <token>",
            status=401,
            retryable=False,
        ))


def _validate_config_on_startup(logger):
    """启动时验证配置"""
    from pathlib import Path
    import yaml

    logger.info("📋 检查配置文件...")

    # 检查 text_providers.yaml
    text_config_path = Path(__file__).parent.parent / 'text_providers.yaml'
    if text_config_path.exists():
        try:
            with open(text_config_path, 'r', encoding='utf-8') as f:
                text_config = yaml.safe_load(f) or {}
            active = text_config.get('active_provider', '未设置')
            providers = list(text_config.get('providers', {}).keys())
            logger.info(f"✅ 文本生成配置: 激活={active}, 可用服务商={providers}")

            # 检查激活的服务商是否有 API Key
            if active in text_config.get('providers', {}):
                provider = text_config['providers'][active]
                if not provider.get('api_key'):
                    logger.warning(f"⚠️  文本服务商 [{active}] 未配置 API Key")
                else:
                    logger.info(f"✅ 文本服务商 [{active}] API Key 已配置")
        except Exception as e:
            logger.error(f"❌ 读取 text_providers.yaml 失败: {e}")
    else:
        logger.warning("⚠️  text_providers.yaml 不存在，将使用默认配置")

    # 检查 image_providers.yaml
    image_config_path = Path(__file__).parent.parent / 'image_providers.yaml'
    if image_config_path.exists():
        try:
            with open(image_config_path, 'r', encoding='utf-8') as f:
                image_config = yaml.safe_load(f) or {}
            active = image_config.get('active_provider', '未设置')
            providers = list(image_config.get('providers', {}).keys())
            logger.info(f"✅ 图片生成配置: 激活={active}, 可用服务商={providers}")

            # 检查激活的服务商是否有 API Key
            if active in image_config.get('providers', {}):
                provider = image_config['providers'][active]
                if not provider.get('api_key'):
                    logger.warning(f"⚠️  图片服务商 [{active}] 未配置 API Key")
                else:
                    logger.info(f"✅ 图片服务商 [{active}] API Key 已配置")
        except Exception as e:
            logger.error(f"❌ 读取 image_providers.yaml 失败: {e}")
    else:
        logger.warning("⚠️  image_providers.yaml 不存在，将使用默认配置")

    logger.info("✅ 配置检查完成")


if __name__ == '__main__':
    app = create_app()
    # 注意：app.run() 使用 Flask 内置开发服务器，仅适合本地开发/自用部署。
    # 生产环境建议改用 WSGI 服务器，例如：
    #   uv run gunicorn -w 2 -b 0.0.0.0:12398 "backend.app:create_app()"
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
