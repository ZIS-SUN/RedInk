"""
API 路由模块

本模块将 API 路由按功能拆分为多个子模块：
- outline_routes: 大纲生成相关 API
- image_routes: 图片生成/获取相关 API
- history_routes: 历史记录 CRUD API
- config_routes: 配置管理 API
- content_routes: 内容生成相关 API（标题、文案、标签）

所有路由都注册到统一的 /api 前缀下
"""

from flask import Blueprint


def create_api_blueprint():
    """
    创建并配置主 API 蓝图

    每次调用都会创建新的蓝图实例，支持多次 create_app() 调用（如测试环境）

    Returns:
        配置好的 api Blueprint
    """
    from .outline_routes import create_outline_blueprint
    from .image_routes import create_image_blueprint
    from .history_routes import create_history_blueprint
    from .config_routes import create_config_blueprint
    from .content_routes import create_content_blueprint
    from .rewrite_routes import create_rewrite_blueprint
    from .title_routes import create_title_blueprint
    from .brand_routes import create_brand_blueprint
    from .link_routes import create_link_blueprint
    from .topic_routes import create_topic_blueprint
    from .calendar_routes import create_calendar_blueprint
    from .cover_routes import create_cover_blueprint
    from .analytics_routes import create_analytics_blueprint
    from .benchmark_routes import create_benchmark_blueprint
    from .reply_routes import create_reply_blueprint
    from .checklist_routes import create_checklist_blueprint
    from .script_routes import create_script_blueprint
    from .insight_routes import create_insight_blueprint
    from .hotspot_routes import create_hotspot_blueprint

    # 创建主 API 蓝图
    api_bp = Blueprint('api', __name__, url_prefix='/api')

    # 将子蓝图注册到主蓝图（不带额外前缀）
    api_bp.register_blueprint(create_outline_blueprint())
    api_bp.register_blueprint(create_image_blueprint())
    api_bp.register_blueprint(create_history_blueprint())
    api_bp.register_blueprint(create_config_blueprint())
    api_bp.register_blueprint(create_content_blueprint())
    # 自媒体工具（第二阶段新增）
    api_bp.register_blueprint(create_rewrite_blueprint())
    api_bp.register_blueprint(create_title_blueprint())
    api_bp.register_blueprint(create_brand_blueprint())
    api_bp.register_blueprint(create_link_blueprint())
    api_bp.register_blueprint(create_topic_blueprint())
    api_bp.register_blueprint(create_calendar_blueprint())
    api_bp.register_blueprint(create_cover_blueprint())
    api_bp.register_blueprint(create_analytics_blueprint())
    api_bp.register_blueprint(create_benchmark_blueprint())
    api_bp.register_blueprint(create_reply_blueprint())
    api_bp.register_blueprint(create_checklist_blueprint())
    # 自媒体工具（第三阶段新增）
    api_bp.register_blueprint(create_script_blueprint())
    api_bp.register_blueprint(create_insight_blueprint())
    api_bp.register_blueprint(create_hotspot_blueprint())

    return api_bp


def register_routes(app):
    """
    注册所有 API 路由到 Flask 应用

    Args:
        app: Flask 应用实例
    """
    api_bp = create_api_blueprint()
    app.register_blueprint(api_bp)


__all__ = ['register_routes', 'create_api_blueprint']
