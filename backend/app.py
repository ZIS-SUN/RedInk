import hmac
import logging
import os
import sys
from logging.handlers import RotatingFileHandler
from flask import Flask, request, send_from_directory
from flask_cors import CORS
from backend.config import Config
from backend.paths import get_data_root, resource_path
from backend.routes import register_routes


def setup_logging():
    """配置日志系统"""
    # 创建根日志器
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)

    # 清除已有的处理器（先 close 释放文件句柄，兼容测试中多次 create_app）
    for handler in root_logger.handlers:
        try:
            handler.close()
        except Exception:
            pass
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

    # 文件处理器：写入 data_root/logs/redink.log（5MB × 3 份轮转）。
    # 桌面版（console=False）没有 stdout，文件日志是用户报障时唯一的现场；
    # 日志内容不含 API Key（启动日志只打印配置状态，见 _validate_config_on_startup）。
    try:
        log_dir = get_data_root() / 'logs'
        log_dir.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            log_dir / 'redink.log',
            maxBytes=5 * 1024 * 1024,
            backupCount=3,
            encoding='utf-8',
        )
        file_handler.setLevel(logging.INFO)
        file_handler.setFormatter(logging.Formatter(
            '\n%(asctime)s | %(levelname)-8s | %(name)s\n'
            '  └─ %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        ))
        root_logger.addHandler(file_handler)
    except OSError as e:
        # 日志目录不可写（只读盘/权限问题）时降级为仅控制台，不阻断启动
        root_logger.warning(f"⚠️  文件日志初始化失败，仅使用控制台日志: {e}")

    # 设置各模块的日志级别
    logging.getLogger('backend').setLevel(logging.DEBUG)
    logging.getLogger('werkzeug').setLevel(logging.INFO)
    logging.getLogger('urllib3').setLevel(logging.WARNING)

    return root_logger


def create_app():
    # 设置日志
    logger = setup_logging()
    logger.info("🚀 正在启动 红墨 AI图文生成器...")

    # 检查是否存在前端构建产物（Docker / 桌面打包环境）
    frontend_dist = resource_path('frontend/dist')
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

    # 请求体大小上限（50MB），防止超大请求耗尽内存
    app.config['MAX_CONTENT_LENGTH'] = 50 * 1024 * 1024

    # 数据备份导入接口单独放宽到 500MB（备份 zip 含全部历史图片，可能远超 50MB）
    @app.before_request
    def _bump_import_size_limit():
        if request.path == '/api/data/import':
            from backend.services.data_admin import MAX_IMPORT_SIZE
            request.max_content_length = MAX_IMPORT_SIZE

    CORS(app, resources={
        # 剪藏收件箱端点单独放行浏览器插件来源（chrome-extension://<id> /
        # moz-extension://<id>）。安全边界：服务默认仅监听本机（127.0.0.1），
        # 且该规则只覆盖 /api/clips* 这一收件箱端点——其余 /api/* 路径仍走
        # 下面的原白名单；flask-cors 按路径规则从最长（最具体）开始匹配。
        r"/api/clips*": {
            "origins": Config.CORS_ORIGINS + [
                r"^chrome-extension://.*$",
                r"^moz-extension://.*$",
            ],
            "methods": ["GET", "POST", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"],
        },
        r"/api/*": {
            "origins": Config.CORS_ORIGINS,
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            # 允许携带访问令牌相关请求头（启用 REDINK_ACCESS_TOKEN 鉴权时需要）
            "allow_headers": ["Content-Type", "Authorization", "X-Access-Token"],
        }
    })

    # 可选的部署级访问令牌鉴权（未设置 REDINK_ACCESS_TOKEN 时不启用，本地开箱即用）
    _register_access_token_auth(app, logger)

    # Host 头校验（防 DNS rebinding；启用令牌鉴权或显式暴露部署时不启用）
    _register_host_guard(app, logger)

    # 注册所有 API 路由
    register_routes(app)
    from backend.routes.review_routes import create_review_blueprint; app.register_blueprint(create_review_blueprint(), url_prefix='/api')
    from backend.routes.publish_routes import create_publish_blueprint; app.register_blueprint(create_publish_blueprint(), url_prefix='/api')

    # 启动时验证配置
    _validate_config_on_startup(logger)

    # 404 处理：无论是否托管前端静态资源，API 路径的 404 都返回统一的
    # 结构化 JSON（避免开发模式下前端拿到 HTML 调试页当作 API 响应解析失败）
    @app.errorhandler(404)
    def fallback(e):
        if request.path.startswith('/api/'):
            from backend.errors import AppError
            from backend.routes.utils import api_error_response
            return api_error_response(AppError(
                code="NOT_FOUND",
                title="接口不存在",
                detail=f"未找到接口: {request.path}",
                suggestion="请检查请求路径和方法是否正确。",
                status=404,
                retryable=False,
            ))
        # 打包模式：非 API 404 回退到前端页面（Vue Router HTML5 History 模式）
        if frontend_dist.exists():
            return send_from_directory(app.static_folder, 'index.html')
        return e

    # 根据是否有前端构建产物决定根路由行为
    if frontend_dist.exists():
        @app.route('/')
        def serve_index():
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


def _register_host_guard(app, logger):
    """注册 Host 头校验，防御 DNS rebinding 攻击。

    仅在本机默认部署形态下启用：恶意网页可让受害者浏览器把攻击者域名
    解析到 127.0.0.1，从而绕过同源策略访问本地 API。校验 Host 头的
    hostname 在白名单内（127.0.0.1 / localhost / ::1，可通过环境变量
    REDINK_ALLOWED_HOSTS 逗号分隔扩展），不合法返回 403 JSON。

    以下场景不启用校验，避免挡住正常部署：
    - 已设置 REDINK_ACCESS_TOKEN（令牌鉴权本身可防 rebinding 页面调用 API）
    - 未配置 REDINK_ALLOWED_HOSTS 且监听地址为非环回地址
      （如 Docker 的 FLASK_HOST=0.0.0.0，访问域名无法预知）
    """
    if os.getenv('REDINK_ACCESS_TOKEN', '').strip():
        return

    loopback_hosts = {'127.0.0.1', 'localhost', '::1'}
    allowed_hosts = set(loopback_hosts)

    extra_hosts = os.getenv('REDINK_ALLOWED_HOSTS', '').strip()
    if extra_hosts:
        allowed_hosts |= {
            host.strip().lower()
            for host in extra_hosts.split(',')
            if host.strip()
        }
    elif Config.HOST not in loopback_hosts:
        # 显式监听非环回地址（如 Docker 0.0.0.0）且未配置白名单/令牌：
        # 无法预知合法访问域名，跳过校验（公网部署请配置 REDINK_ACCESS_TOKEN）
        logger.info("ℹ️  监听非环回地址且未配置 REDINK_ALLOWED_HOSTS，跳过 Host 头校验")
        return

    from urllib.parse import urlsplit
    from backend.errors import AppError
    from backend.routes.utils import api_error_response

    logger.info(f"🛡️  已启用 Host 头校验，白名单: {sorted(allowed_hosts)}")

    @app.before_request
    def _check_host_header():
        # 提取 hostname 部分（去掉端口，兼容 IPv6 字面量如 [::1]:12398）
        try:
            hostname = (urlsplit(f'//{request.host}').hostname or '').lower()
        except ValueError:
            hostname = ''

        if hostname in allowed_hosts:
            return None

        return api_error_response(AppError(
            code="FORBIDDEN_HOST",
            title="Host 头校验失败",
            detail=f"不允许的 Host: {request.host}",
            suggestion="请通过 127.0.0.1 或 localhost 访问；如需自定义域名，"
                       "请设置环境变量 REDINK_ALLOWED_HOSTS 或 REDINK_ACCESS_TOKEN。",
            status=403,
            retryable=False,
        ))


def _validate_config_on_startup(logger):
    """启动时验证配置"""
    import yaml

    logger.info("📋 检查配置文件...")

    # 检查 text_providers.yaml
    text_config_path = get_data_root() / 'text_providers.yaml'
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
    image_config_path = get_data_root() / 'image_providers.yaml'
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
    # 生产环境建议改用 WSGI 服务器，且必须保持单进程多线程，例如：
    #   uv run gunicorn -w 1 --threads 4 --timeout 0 -b 0.0.0.0:12398 "backend.app:create_app()"
    # 说明：
    # - 必须 -w 1：历史索引、图片限流器、任务状态都依赖进程内锁/内存，
    #   多 worker 进程会互相覆盖历史索引（丢记录）、限流失效；
    #   如需多进程，需先引入跨进程锁或把历史/任务状态迁移到数据库
    # - --timeout 0：图片生成 SSE 流可持续数分钟，默认 30 秒会杀掉 worker
    app.run(
        host=Config.HOST,
        port=Config.PORT,
        debug=Config.DEBUG
    )
