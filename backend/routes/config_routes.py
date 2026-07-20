"""
配置管理相关 API 路由

包含功能：
- 获取当前配置
- 更新配置
- 测试服务商连接
"""

import ipaddress
import logging
import os
import socket
import string
import tempfile
import threading
from pathlib import Path
from typing import NamedTuple, Optional
from urllib.parse import urlparse
import yaml
from flask import Blueprint, request, jsonify
from backend.paths import get_data_root, resource_path
from .utils import (
    api_error_response,
    prepare_providers_for_response,
    validation_error,
)

logger = logging.getLogger(__name__)


class LlmSmokeResult(NamedTuple):
    text: str
    source: str
    finish_reason: str

# 配置文件路径（统一放在可写数据根目录下）
CONFIG_DIR = get_data_root()
IMAGE_CONFIG_PATH = CONFIG_DIR / 'image_providers.yaml'
TEXT_CONFIG_PATH = CONFIG_DIR / 'text_providers.yaml'

# 配置文件写入锁：串行化「读-改-写」，防止并发保存互相覆盖或写坏 YAML
# （RLock：_update_provider_config 持锁期间还会调用 _write_config）
_CONFIG_WRITE_LOCK = threading.RLock()

# 图片 Prompt 模板占位符（PUT 时必须包含 REQUIRED 中的占位符）
IMAGE_PROMPT_PLACEHOLDERS = ("page_content", "page_type", "user_topic", "full_outline")
IMAGE_PROMPT_REQUIRED_PLACEHOLDERS = ("page_content", "page_type")


# 禁止访问的地址段（SSRF 防护）。
# 注意：不使用 ip.is_private 一刀切，因为 Fake-IP 代理环境下
# 所有域名会解析到 198.18.0.0/15（属 is_private），会误杀全部合法域名。
_FORBIDDEN_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # 环回
    ipaddress.ip_network('10.0.0.0/8'),       # 私网 A
    ipaddress.ip_network('172.16.0.0/12'),    # 私网 B
    ipaddress.ip_network('192.168.0.0/16'),   # 私网 C
    ipaddress.ip_network('169.254.0.0/16'),   # 链路本地
    ipaddress.ip_network('100.64.0.0/10'),    # CGNAT
    ipaddress.ip_network('::1/128'),          # IPv6 环回
    ipaddress.ip_network('fe80::/10'),        # IPv6 链路本地
    ipaddress.ip_network('fc00::/7'),         # IPv6 唯一本地
]


def _is_forbidden_ip(ip) -> bool:
    """判断 IP 是否属于私网/环回/链路本地等禁止访问的地址段"""
    if ip.is_loopback or ip.is_link_local or ip.is_multicast or ip.is_unspecified:
        return True
    return any(ip in network for network in _FORBIDDEN_NETWORKS)


def _validate_base_url(url: Optional[str]) -> Optional[str]:
    """
    校验 base_url 是否安全（防 SSRF）

    仅允许 http/https 协议，拒绝指向私网/环回/链路本地地址的主机
    （域名会先解析为 IP 再校验）。

    Args:
        url: 待校验的 base_url（空值视为使用默认地址，直接通过）

    Returns:
        Optional[str]: 不合法时返回错误描述，合法返回 None
    """
    if not url:
        return None

    try:
        parsed = urlparse(str(url))
    except ValueError:
        return "base_url 格式不正确"

    if parsed.scheme not in ('http', 'https'):
        return "base_url 仅支持 http/https 协议"

    hostname = parsed.hostname
    if not hostname:
        return "base_url 缺少有效的主机名"

    # 主机名本身就是 IP 的情况
    try:
        ip = ipaddress.ip_address(hostname.split('%')[0])
    except ValueError:
        ip = None

    if ip is not None:
        if _is_forbidden_ip(ip):
            return "base_url 不允许指向私网、环回或保留地址"
        return None

    # 域名：解析为 IP 后逐个校验
    # 解析失败时放行——此处不做可达性判断，后续真正的连接请求会以相同的解析器再次尝试并
    # 自然失败；在此硬拒会误杀无网/自定义 DNS 环境下的合法域名。SSRF 的核心防护（IP 字面量
    # 与可解析到内网的域名）仍然生效。
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return None

    for info in addr_infos:
        try:
            resolved_ip = ipaddress.ip_address(str(info[4][0]).split('%')[0])
        except ValueError:
            return "base_url 解析结果异常"
        if _is_forbidden_ip(resolved_ip):
            return "base_url 解析到私网、环回或保留地址，已拒绝"

    return None


def create_config_blueprint():
    """创建配置路由蓝图（工厂函数，支持多次调用）"""
    config_bp = Blueprint('config', __name__)

    # ==================== 配置读写 ====================

    @config_bp.route('/config', methods=['GET'])
    def get_config():
        """
        获取当前配置

        返回：
        - success: 是否成功
        - config: 配置对象
          - text_generation: 文本生成配置
          - image_generation: 图片生成配置
        """
        try:
            # 读取图片生成配置
            image_config = _read_config(IMAGE_CONFIG_PATH, {
                'active_provider': 'google_genai',
                'providers': {}
            })

            # 读取文本生成配置
            text_config = _read_config(TEXT_CONFIG_PATH, {
                'active_provider': 'google_gemini',
                'providers': {}
            })

            return jsonify({
                "success": True,
                "config": {
                    "text_generation": {
                        "active_provider": text_config.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            text_config.get('providers', {})
                        )
                    },
                    "image_generation": {
                        "active_provider": image_config.get('active_provider', ''),
                        "providers": prepare_providers_for_response(
                            image_config.get('providers', {})
                        )
                    }
                }
            })

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/config"})

    @config_bp.route('/config', methods=['POST'])
    def update_config():
        """
        更新配置

        请求体：
        - image_generation: 图片生成配置（可选）
        - text_generation: 文本生成配置（可选）

        返回：
        - success: 是否成功
        - message: 结果消息
        """
        try:
            data = request.get_json(silent=True) or {}

            # 保存前校验所有 base_url，防止写入 SSRF 地址
            for section in ('image_generation', 'text_generation'):
                providers = (data.get(section) or {}).get('providers') or {}
                for name, provider_config in providers.items():
                    if not isinstance(provider_config, dict):
                        continue
                    error_msg = _validate_base_url(provider_config.get('base_url'))
                    if error_msg:
                        return api_error_response(
                            validation_error(error_msg, "请填写合法的公网服务地址。"),
                            context={"endpoint": "/api/config", "provider": name},
                        )

            # 更新图片生成配置
            if 'image_generation' in data:
                _update_provider_config(
                    IMAGE_CONFIG_PATH,
                    data['image_generation']
                )

            # 更新文本生成配置
            if 'text_generation' in data:
                _update_provider_config(
                    TEXT_CONFIG_PATH,
                    data['text_generation']
                )

            # 清除配置缓存，确保下次使用时读取新配置
            _clear_config_cache()

            return jsonify({
                "success": True,
                "message": "配置已保存"
            })

        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/config"})

    # ==================== 图片 Prompt 模板 ====================

    @config_bp.route('/config/image-prompt', methods=['GET'])
    def get_image_prompt():
        """
        获取当前生效的图片生成 Prompt 模板

        返回：
        - success: 是否成功
        - template: 当前生效模板全文（自定义优先，否则包内默认）
        - is_custom: 是否为用户自定义模板
        - placeholders: 模板支持的占位符列表
        """
        try:
            custom_template = _read_custom_image_prompt()
            if custom_template is not None:
                template = custom_template
                is_custom = True
            else:
                template = _read_default_image_prompt()
                is_custom = False

            return jsonify({
                "success": True,
                "template": template,
                "is_custom": is_custom,
                "placeholders": list(IMAGE_PROMPT_PLACEHOLDERS),
            })
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/config/image-prompt"})

    @config_bp.route('/config/image-prompt', methods=['PUT'])
    def save_image_prompt():
        """
        保存自定义图片生成 Prompt 模板

        请求体：
        - template: 模板全文（必须包含 {page_content} 和 {page_type} 占位符）
        """
        try:
            data = request.get_json(silent=True) or {}
            template = data.get('template')

            if not isinstance(template, str) or not template.strip():
                return api_error_response(
                    validation_error("template 不能为空", "请填写模板内容后再保存。")
                )

            missing = [
                f"{{{name}}}" for name in IMAGE_PROMPT_REQUIRED_PLACEHOLDERS
                if f"{{{name}}}" not in template
            ]
            if missing:
                return api_error_response(
                    validation_error(
                        f"模板缺少必需占位符: {'、'.join(missing)}",
                        "模板必须包含 {page_content} 和 {page_type} 两个占位符。",
                    )
                )

            render_error = _validate_image_prompt_template(template)
            if render_error:
                return api_error_response(validation_error(*render_error))

            custom_path = _custom_image_prompt_path()
            custom_path.parent.mkdir(parents=True, exist_ok=True)
            _atomic_write_text(custom_path, template)

            _reset_image_service_safely()

            return jsonify({
                "success": True,
                "message": "图片 Prompt 模板已保存"
            })
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/config/image-prompt"})

    @config_bp.route('/config/image-prompt', methods=['DELETE'])
    def reset_image_prompt():
        """删除自定义图片生成 Prompt 模板，恢复包内默认"""
        try:
            custom_path = _custom_image_prompt_path()
            if custom_path.exists():
                custom_path.unlink()

            _reset_image_service_safely()

            return jsonify({
                "success": True,
                "message": "已恢复默认图片 Prompt 模板"
            })
        except Exception as e:
            return api_error_response(e, context={"endpoint": "/api/config/image-prompt"})

    # ==================== 连接测试 ====================

    @config_bp.route('/config/test', methods=['POST'])
    def test_connection():
        """
        测试服务商连接

        请求体：
        - type: 服务商类型（google_genai/google_gemini/openai_compatible/image_api）
        - provider_name: 服务商名称（用于从配置读取 API Key）
        - api_key: API Key（可选，若不提供则从配置读取）
        - base_url: Base URL（可选）
        - model: 模型名称（可选）

        返回：
        - success: 是否成功
        - message: 测试结果消息
        """
        data = {}
        config = {}
        try:
            data = request.get_json(silent=True) or {}
            provider_type = data.get('type')
            provider_name = data.get('provider_name')

            if not provider_type:
                return api_error_response(
                    validation_error("缺少 type 参数", "请选择服务商类型后再测试连接。")
                )
            if provider_type not in ['google_genai', 'google_gemini', 'openai_compatible', 'image_api']:
                return api_error_response(
                    validation_error(f"不支持的类型: {provider_type}", "请选择正确的服务商类型后再测试连接。")
                )

            # 构建配置
            config = {
                'api_key': data.get('api_key'),
                'base_url': data.get('base_url'),
                'model': data.get('model'),
                'endpoint_type': data.get('endpoint_type')
            }

            # 如果没有提供 api_key，从配置文件读取
            if not config['api_key'] and provider_name:
                config = _load_provider_config(provider_type, provider_name, config)
                # 安全约束（与 _update_provider_config 对齐）：请求的 base_url 与已保存值
                # 不一致且未显式提供 api_key 时，拒绝回填已存密钥，
                # 避免把已保存的真实 Key 外发到攻击者可控地址
                if config.pop('_api_key_withheld', False) and not config['api_key']:
                    return api_error_response(
                        validation_error(
                            "base_url 与已保存配置不一致，已拒绝使用已保存的 API Key",
                            "修改 Base URL 后请重新输入 API Key 再测试连接。",
                        ),
                        context=_error_context(provider_type, provider_name, config),
                    )

            if not config['api_key']:
                return api_error_response(
                    validation_error("API Key 未配置", "请先填写并保存该服务商的 API Key。"),
                    context=_error_context(provider_type, provider_name, config),
                )

            # 测试连接前校验 base_url，防止 SSRF
            base_url_error = _validate_base_url(config.get('base_url'))
            if base_url_error:
                return api_error_response(
                    validation_error(base_url_error, "请填写合法的公网服务地址。"),
                    context=_error_context(provider_type, provider_name, config),
                )

            # 根据类型执行测试
            result = _test_provider_connection(provider_type, config)
            return jsonify(result), 200 if result['success'] else 400

        except Exception as e:
            return api_error_response(
                e,
                context=_error_context(
                    data.get('type') if data else None,
                    data.get('provider_name') if data else None,
                    config or data,
                ),
            )

    return config_bp


# ==================== 辅助函数 ====================

def _validate_image_prompt_template(template: str):
    """
    用 string.Formatter 预解析模板，拦截未知占位符与未配对的大括号，
    避免保存后在实际渲染（str.format）时才抛错导致图片生成失败。

    Returns:
        Optional[tuple]: 不合法时返回 (detail, suggestion)，合法返回 None
    """
    allowed = set(IMAGE_PROMPT_PLACEHOLDERS)
    try:
        field_names = [
            field_name
            for _, field_name, _, _ in string.Formatter().parse(template)
            if field_name is not None
        ]
    except ValueError:
        return (
            "模板包含未配对的大括号",
            "模板存在裸大括号或大括号未配对；如需输出大括号本身请写 {{ }}。",
        )

    unknown = [name for name in field_names if name not in allowed]
    if unknown:
        shown = "、".join(f"{{{name}}}" for name in dict.fromkeys(unknown))
        return (
            f"模板包含无法识别的占位符: {shown}",
            "仅支持 {page_content}、{page_type}、{user_topic}、{full_outline} 四个占位符；"
            "如需输出大括号本身请写 {{ }}。",
        )
    return None


def _atomic_write_text(path: Path, content: str):
    """临时文件 + os.replace 原子写入，避免进程中断留下半截文件"""
    tmp_path = path.with_name(path.name + '.tmp')
    tmp_path.write_text(content, encoding='utf-8')
    os.replace(tmp_path, path)


def _custom_image_prompt_path() -> Path:
    """自定义图片 Prompt 模板路径（每次调用取最新数据根目录，便于测试隔离）"""
    return get_data_root() / 'custom_prompts' / 'image_prompt.txt'


def _read_custom_image_prompt() -> Optional[str]:
    """读取自定义模板；不存在或为空时返回 None"""
    custom_path = _custom_image_prompt_path()
    if custom_path.exists():
        content = custom_path.read_text(encoding='utf-8')
        if content.strip():
            return content
    return None


def _read_default_image_prompt() -> str:
    """读取包内默认图片 Prompt 模板"""
    default_path = resource_path('backend/prompts/image_prompt.txt')
    if not default_path.exists():
        return ""
    return default_path.read_text(encoding='utf-8')


def _reset_image_service_safely():
    """重置图片服务实例，使新模板/配置在下次请求时生效"""
    try:
        from backend.services.image import reset_image_service
        reset_image_service()
    except Exception:
        pass


def _read_config(path: Path, default: dict) -> dict:
    """读取配置文件"""
    if path.exists():
        with open(path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f) or default
    return default


def _write_config(path: Path, config: dict):
    """
    写入配置文件（原子写：先写同目录临时文件，再 os.replace() 覆盖）

    直写目标文件时若进程中途被杀或并发写入，会留下半截 YAML，
    导致 Config.load 抛错、全部生成功能瘫痪。
    """
    with _CONFIG_WRITE_LOCK:
        fd, tmp_path = tempfile.mkstemp(
            prefix=".tmp_", suffix=".yaml", dir=str(path.parent)
        )
        try:
            with os.fdopen(fd, 'w', encoding='utf-8') as f:
                yaml.dump(config, f, allow_unicode=True, default_flow_style=False)
            os.replace(tmp_path, path)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise


def _update_provider_config(config_path: Path, new_data: dict):
    """
    更新服务商配置

    Args:
        config_path: 配置文件路径
        new_data: 新的配置数据
    """
    # 整个「读-改-写」持锁，避免并发保存时后写者基于旧配置覆盖先写者的更新
    with _CONFIG_WRITE_LOCK:
        _update_provider_config_locked(config_path, new_data)


def _update_provider_config_locked(config_path: Path, new_data: dict):
    """_update_provider_config 的持锁实现（调用方须已持有 _CONFIG_WRITE_LOCK）"""
    # 读取现有配置
    existing_config = _read_config(config_path, {'providers': {}})

    # 更新 active_provider
    if 'active_provider' in new_data:
        existing_config['active_provider'] = new_data['active_provider']

    # 更新 providers
    if 'providers' in new_data:
        existing_providers = existing_config.get('providers', {})
        new_providers = new_data['providers']

        for name, new_provider_config in new_providers.items():
            # 如果新配置的 api_key 是空的，保留原有的
            if new_provider_config.get('api_key') in [True, False, '', None]:
                existing_provider = existing_providers.get(name, {})
                old_base_url = existing_provider.get('base_url')
                new_base_url = new_provider_config.get('base_url')
                # 安全约束：修改 base_url 却未提供新 api_key 时，
                # 不回填旧密钥，避免把已存密钥转发到新地址（密钥外发链）
                base_url_changed = (
                    'base_url' in new_provider_config
                    and (new_base_url or None) != (old_base_url or None)
                )
                if not base_url_changed and existing_provider.get('api_key'):
                    new_provider_config['api_key'] = existing_provider['api_key']
                else:
                    new_provider_config.pop('api_key', None)

            # 移除不需要保存的字段
            new_provider_config.pop('api_key_env', None)
            new_provider_config.pop('api_key_masked', None)

        existing_config['providers'] = new_providers

    # 保存配置
    _write_config(config_path, existing_config)


def _clear_config_cache():
    """清除配置缓存（图片 + 文本），确保下次使用时读取新配置"""
    try:
        from backend.config import Config
        Config.reload_config()
    except Exception:
        pass

    try:
        from backend.services.image import reset_image_service
        reset_image_service()
    except Exception:
        pass


def _load_provider_config(provider_type: str, provider_name: str, config: dict) -> dict:
    """
    从配置文件加载服务商配置

    Args:
        provider_type: 服务商类型
        provider_name: 服务商名称
        config: 当前配置（会被合并）

    Returns:
        dict: 合并后的配置
    """
    # 确定配置文件路径
    if provider_type in ['openai_compatible', 'google_gemini']:
        config_path = TEXT_CONFIG_PATH
    else:
        config_path = IMAGE_CONFIG_PATH

    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            yaml_config = yaml.safe_load(f) or {}
            providers = yaml_config.get('providers', {})

            if provider_name in providers:
                saved = providers[provider_name]

                # 仅当请求的 base_url 与已保存值一致（或未提供）时才回填已存密钥；
                # 不一致时打标记，由调用方返回校验错误（防止密钥外发到新地址）
                requested_base_url = config.get('base_url')
                base_url_changed = (
                    bool(requested_base_url)
                    and (requested_base_url or None) != (saved.get('base_url') or None)
                )
                if base_url_changed:
                    config['_api_key_withheld'] = True
                else:
                    config['api_key'] = saved.get('api_key')

                if not config['base_url']:
                    config['base_url'] = saved.get('base_url')
                if not config['model']:
                    config['model'] = saved.get('model')
                if not config.get('endpoint_type'):
                    config['endpoint_type'] = saved.get('endpoint_type')

    return config


def _test_provider_connection(provider_type: str, config: dict) -> dict:
    """
    测试服务商连接

    Args:
        provider_type: 服务商类型
        config: 服务商配置

    Returns:
        dict: 测试结果
    """
    test_prompt = "请只回复：红墨连接测试成功"

    if provider_type == 'google_genai':
        return _test_google_genai(config)

    elif provider_type == 'google_gemini':
        return _test_google_gemini(config, test_prompt)

    elif provider_type == 'openai_compatible':
        return _test_openai_compatible(config, test_prompt)

    elif provider_type == 'image_api':
        return _test_image_api(config)

    else:
        raise ValueError(f"不支持的类型: {provider_type}")


def _error_context(provider_type: str = None, provider_name: str = None, config: dict = None) -> dict:
    config = config or {}
    base_url = config.get('base_url')
    endpoint_type = config.get('endpoint_type')
    return {
        "provider_type": provider_type,
        "provider": provider_name,
        "base_url": base_url,
        "model": config.get('model'),
        "endpoint": endpoint_type,
    }


def _test_google_genai(config: dict) -> dict:
    """测试 Google GenAI 图片生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
        # 测试列出模型
        try:
            list(client.models.list())
            return {
                "success": True,
                "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
            }
        except Exception as e:
            raise Exception(f"连接测试失败: {str(e)}")
    else:
        return {
            "success": True,
            "message": "Vertex AI 无法通过 API Key 测试连接（需要 OAuth2 认证）。请在实际生成图片时验证配置是否正确。"
        }


def _test_google_gemini(config: dict, test_prompt: str) -> dict:
    """测试 Google Gemini 文本生成服务"""
    from google import genai

    if config.get('base_url'):
        client = genai.Client(
            api_key=config['api_key'],
            http_options={
                'base_url': config['base_url'],
                'api_version': 'v1beta'
            },
            vertexai=False
        )
    else:
        # 与实际生成路径保持一致：API Key 用户走非 Vertex AI 通道
        client = genai.Client(
            api_key=config['api_key'],
            vertexai=False
        )

    model = config.get('model') or 'gemini-2.0-flash-exp'
    response = client.models.generate_content(
        model=model,
        contents=test_prompt
    )
    result_text = response.text if hasattr(response, 'text') else str(response)

    return _check_response(result_text)


def _test_openai_compatible(config: dict, test_prompt: str) -> dict:
    """测试 OpenAI 兼容接口"""
    result = _test_openai_chat_completion(config, test_prompt)
    return _check_response(result)


def _test_image_api(config: dict) -> dict:
    """测试图片 API 连接"""
    import requests

    base_url = config['base_url'].rstrip('/') if config.get('base_url') else 'https://api.openai.com'
    if base_url.endswith('/v1'):
        base_url = base_url[:-3]

    endpoint_type = config.get('endpoint_type', '')

    # 如果端点是 chat/completions 类型，用真实 LLM 请求来测试
    if endpoint_type and ('chat' in endpoint_type or 'completions' in endpoint_type):
        result = _test_openai_chat_completion(
            config,
            "请只回复：红墨连接测试成功",
        )
        return _llm_smoke_response_payload(result)

    # 标准 images API，尝试 /v1/models
    url = f"{base_url}/v1/models"
    response = requests.get(
        url,
        headers={'Authorization': f"Bearer {config['api_key']}"},
        timeout=30
    )

    if response.status_code == 200:
        return {
            "success": True,
            "message": "连接成功！仅代表连接稳定，不确定是否可以稳定支持图片生成"
        }
    else:
        # 不回显上游原始响应体，仅记录到服务端日志
        logger.warning(f"图片 API 测试失败: HTTP {response.status_code}, 响应: {response.text[:200]}")
        raise Exception(f"HTTP {response.status_code}: 连接测试失败，请检查 Base URL 和 API Key 配置。")


def _test_openai_chat_completion(config: dict, test_prompt: str) -> LlmSmokeResult:
    """用当前配置发送一次真实 OpenAI-compatible LLM 请求。"""
    import requests

    base_url = _normalize_base_url(config.get('base_url') or 'https://api.openai.com')
    endpoint = _normalize_endpoint(config.get('endpoint_type') or '/v1/chat/completions')
    url = f"{base_url}{endpoint}"

    payload = {
        "model": config.get('model') or 'gpt-3.5-turbo',
        "messages": [{"role": "user", "content": test_prompt}],
        "max_tokens": 256,
        "stream": False
    }
    headers = {
        'Authorization': f"Bearer {config['api_key']}",
        'Content-Type': 'application/json',
        'Accept': 'application/json'
    }

    response = requests.post(
        url,
        headers=headers,
        json=payload,
        timeout=30
    )
    if _should_retry_with_max_completion_tokens(response):
        retry_payload = dict(payload)
        retry_payload["max_completion_tokens"] = retry_payload.pop("max_tokens")
        response = requests.post(
            url,
            headers=headers,
            json=retry_payload,
            timeout=30
        )

    if response.status_code != 200:
        # 不回显上游原始响应体，仅记录到服务端日志
        logger.warning(f"LLM 测试请求失败: HTTP {response.status_code}, 响应: {response.text[:500]}")
        raise Exception(f"HTTP {response.status_code}: 上游服务返回错误，请检查 Base URL、模型名称和 API Key 配置。")

    try:
        result = response.json()
    except Exception as exc:
        logger.warning(f"LLM 响应不是合法 JSON: {response.text[:500]}")
        raise Exception("LLM 响应不是合法 JSON，请检查 Base URL 和 endpoint_type 配置。") from exc

    smoke_result = _extract_chat_completion_text(result)
    if not smoke_result.text.strip() and smoke_result.source not in ["reasoning_tokens"]:
        logger.warning(f"LLM 响应为空，响应数据: {str(result)[:500]}")
        raise Exception("LLM 响应为空，请检查模型配置后重试。")
    return smoke_result


def _extract_chat_completion_text(result: dict) -> LlmSmokeResult:
    choices = result.get('choices')
    if not isinstance(choices, list) or not choices:
        logger.warning(f"LLM 响应格式异常（未找到 choices），响应数据: {str(result)[:500]}")
        raise Exception("LLM 响应格式异常：未找到 choices，请检查服务商是否兼容 OpenAI 接口。")

    choice = choices[0] if isinstance(choices[0], dict) else {}
    finish_reason = choice.get('finish_reason') or ""
    message = choice.get('message', {}) if isinstance(choice, dict) else {}
    content = message.get('content')
    if isinstance(content, str) and content.strip():
        return LlmSmokeResult(content.strip(), "content", finish_reason)
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict):
                text = item.get('text') or item.get('content')
                if isinstance(text, str):
                    parts.append(text)
        joined = "\n".join(parts).strip()
        if joined:
            return LlmSmokeResult(joined, "content", finish_reason)

    reasoning_content = message.get('reasoning_content') or message.get('reasoning')
    if isinstance(reasoning_content, str) and reasoning_content.strip():
        return LlmSmokeResult(reasoning_content.strip(), "reasoning_content", finish_reason)

    if finish_reason == "length" and _extract_reasoning_token_count(result) > 0:
        return LlmSmokeResult("", "reasoning_tokens", finish_reason)

    logger.warning(f"LLM 响应格式异常（未找到 message.content），响应数据: {str(result)[:500]}")
    raise Exception("LLM 响应格式异常：未找到 message.content 或 reasoning_content，请检查模型配置。")


def _extract_reasoning_token_count(result: dict) -> int:
    usage = result.get("usage") if isinstance(result, dict) else {}
    if not isinstance(usage, dict):
        return 0
    for details_key in ["completion_tokens_details", "output_tokens_details"]:
        details = usage.get(details_key)
        if isinstance(details, dict):
            value = details.get("reasoning_tokens")
            if isinstance(value, int):
                return value
    return 0


def _should_retry_with_max_completion_tokens(response) -> bool:
    if response.status_code not in [400, 422]:
        return False
    text = (response.text or "").lower()
    return (
        "max_tokens" in text
        and (
            "max_completion_tokens" in text
            or "not compatible" in text
            or "unsupported" in text
            or "不支持" in text
        )
    )


def _normalize_base_url(base_url: str) -> str:
    base_url = base_url.rstrip('/')
    if base_url.endswith('/v1'):
        return base_url[:-3]
    return base_url


def _normalize_endpoint(endpoint: str) -> str:
    if endpoint == 'chat':
        endpoint = '/v1/chat/completions'
    elif endpoint == 'images':
        endpoint = '/v1/images/generations'
    if not endpoint.startswith('/'):
        endpoint = '/' + endpoint
    return endpoint


def _format_llm_success_message(result: LlmSmokeResult) -> str:
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        suffix = "，输出预算已耗尽" if result.finish_reason == "length" else ""
        return f"LLM 请求成功！模型返回了推理过程但没有最终文本{suffix}。如果正式生成也出现空内容，请提高输出上限或关闭思考模式后重试。"
    return f"LLM 请求成功！响应: {result.text[:100]}"


def _llm_smoke_response_payload(result: LlmSmokeResult) -> dict:
    payload = {
        "success": True,
        "message": _format_llm_success_message(result),
    }
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        payload["warning"] = True
        payload["status"] = "warning"
    return payload


def _check_response(result: LlmSmokeResult) -> dict:
    """检查响应是否符合预期"""
    if result.source in ["reasoning_content", "reasoning_tokens"]:
        return _llm_smoke_response_payload(result)

    if "红墨" in result.text:
        return _llm_smoke_response_payload(result)
    else:
        return {
            "success": True,
            "message": f"LLM 请求成功，但响应内容不符合预期: {result.text[:100]}"
        }
