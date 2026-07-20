"""
LLM 调用共享工具

集中收敛各文本服务（outline/content/title/topic/reply/cover/rewrite/
benchmark/link_extract/analytics）原先各自复制的公共逻辑：

- load_text_config: 加载 text_providers.yaml 配置
- get_text_client: 根据配置构建文本生成客户端
- resolve_generation_params: 从配置解析 model/temperature/max_output_tokens
- load_prompt_template: 加载提示词模板文件
- parse_llm_json: 解析 LLM 返回的 JSON（含 ```json 代码块剥壳与大括号截取降级）
- classify_llm_error: 把底层异常归一化为面向用户的详细错误文案

注意：所有错误消息文本与原各服务实现逐字一致，不要随意改动措辞。
"""

import json
import logging
import re
from typing import Any, Dict, Tuple, Union

import yaml

from backend.paths import get_data_root, resource_path

logger = logging.getLogger(__name__)

DEFAULT_PROVIDER = 'google_gemini'
DEFAULT_MODEL = 'gemini-2.0-flash-exp'


def load_text_config(*, default_providers: bool = True) -> dict:
    """
    加载文本生成配置（text_providers.yaml）。

    Args:
        default_providers: 配置文件不存在时，默认配置是否包含内置的
            google_gemini 服务商条目。analytics 服务历史上使用空 providers
            默认值（缺配置时走"未找到任何文本生成服务商配置"错误路径），
            其余服务使用带 google_gemini 条目的默认值。

    Raises:
        ValueError: 配置文件存在但 YAML 解析失败时抛出
    """
    config_path = get_data_root() / 'text_providers.yaml'
    logger.debug(f"加载文本配置: {config_path}")

    if config_path.exists():
        try:
            with open(config_path, 'r', encoding='utf-8') as f:
                config = yaml.safe_load(f) or {}
            logger.debug(f"文本配置加载成功: active={config.get('active_provider')}")
            return config
        except yaml.YAMLError as e:
            logger.error(f"文本配置 YAML 解析失败: {e}")
            raise ValueError(
                f"文本配置文件格式错误: text_providers.yaml\n"
                f"YAML 解析错误: {e}\n"
                "解决方案：检查 YAML 缩进和语法"
            )

    logger.warning("text_providers.yaml 不存在，使用默认配置")
    if not default_providers:
        return {
            'active_provider': DEFAULT_PROVIDER,
            'providers': {},
        }
    return {
        'active_provider': DEFAULT_PROVIDER,
        'providers': {
            'google_gemini': {
                'type': 'google_gemini',
                'model': DEFAULT_MODEL,
                'temperature': 1.0,
                'max_output_tokens': 8000
            }
        }
    }


def get_text_client(text_config: dict):
    """
    根据配置构建文本生成客户端。

    惰性导入 text_client，避免不需要 LLM 的调用路径（如 analytics 的
    CRUD 接口）在导入期依赖 requests 等三方库环境。

    Raises:
        ValueError: 无服务商配置 / 激活服务商不存在 / 未配置 API Key 时抛出
    """
    from backend.utils.text_client import get_text_chat_client

    active_provider = text_config.get('active_provider', DEFAULT_PROVIDER)
    providers = text_config.get('providers', {})

    if not providers:
        logger.error("未找到任何文本生成服务商配置")
        raise ValueError(
            "未找到任何文本生成服务商配置。\n"
            "解决方案：\n"
            "1. 在系统设置页面添加文本生成服务商\n"
            "2. 或手动编辑 text_providers.yaml 文件"
        )

    if active_provider not in providers:
        available = ', '.join(providers.keys())
        logger.error(f"文本服务商 [{active_provider}] 不存在，可用: {available}")
        raise ValueError(
            f"未找到文本生成服务商配置: {active_provider}\n"
            f"可用的服务商: {available}\n"
            "解决方案：在系统设置中选择一个可用的服务商"
        )

    provider_config = providers.get(active_provider, {})

    if not provider_config.get('api_key'):
        logger.error(f"文本服务商 [{active_provider}] 未配置 API Key")
        raise ValueError(
            f"文本服务商 {active_provider} 未配置 API Key\n"
            "解决方案：在系统设置页面编辑该服务商，填写 API Key"
        )

    logger.info(f"使用文本服务商: {active_provider} (type={provider_config.get('type')})")
    return get_text_chat_client(provider_config)


def resolve_generation_params(
    text_config: dict,
    *,
    default_max_output_tokens: int = 8000
) -> Tuple[str, float, int]:
    """
    从配置中解析当前激活服务商的模型调用参数。

    Returns:
        (model, temperature, max_output_tokens)
    """
    active_provider = text_config.get('active_provider', DEFAULT_PROVIDER)
    providers = text_config.get('providers', {})
    provider_config = providers.get(active_provider, {})

    model = provider_config.get('model', DEFAULT_MODEL)
    temperature = provider_config.get('temperature', 1.0)
    max_output_tokens = provider_config.get('max_output_tokens', default_max_output_tokens)
    return model, temperature, max_output_tokens


def load_prompt_template(relative_path: str) -> str:
    """加载提示词模板文件（如 'backend/prompts/topic_prompt.txt'）"""
    prompt_path = resource_path(relative_path)
    with open(prompt_path, "r", encoding="utf-8") as f:
        return f.read()


def parse_llm_json(response_text: str) -> Dict[str, Any]:
    """
    解析 LLM 返回的 JSON 响应（多级降级策略）：

    1. 直接 json.loads
    2. 从 ```json ... ``` / ``` ... ``` 代码块中提取
    3. 截取首个 '{' 到最后一个 '}' 之间的内容

    Raises:
        ValueError: 所有策略均失败时抛出（消息与原各服务实现一致）
    """
    # 尝试直接解析
    try:
        return json.loads(response_text)
    except json.JSONDecodeError:
        pass

    # 尝试从 markdown 代码块中提取
    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
    if json_match:
        try:
            return json.loads(json_match.group(1).strip())
        except json.JSONDecodeError:
            pass

    # 尝试找到 JSON 对象的开始和结束
    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        try:
            return json.loads(response_text[start_idx:end_idx + 1])
        except json.JSONDecodeError:
            pass

    logger.error(f"无法解析 JSON 响应: {response_text[:200]}...")
    raise ValueError("AI 返回的内容格式不正确，无法解析")


def classify_llm_error(error: Union[Exception, str], *, task_label: str) -> str:
    """
    把 LLM 调用异常归一化为面向用户的详细错误文案。

    分类顺序与各服务原实现一致：认证 → 模型 → 网络 → 配额 → 兜底。

    Args:
        error: 原始异常或错误消息字符串
        task_label: 兜底分支的首行标题（如 "选题灵感生成失败"），
            与各服务原有错误文本逐字对应

    Returns:
        多行详细错误文案（与原各服务 detailed_error 逐字一致）
    """
    error_msg = str(error)

    if "api_key" in error_msg.lower() or "unauthorized" in error_msg.lower() or "401" in error_msg:
        return (
            f"API 认证失败。\n"
            f"错误详情: {error_msg}\n"
            "可能原因：API Key 无效或已过期\n"
            "解决方案：在系统设置页面检查并更新 API Key"
        )
    if "model" in error_msg.lower() or "404" in error_msg:
        return (
            f"模型访问失败。\n"
            f"错误详情: {error_msg}\n"
            "解决方案：在系统设置页面检查模型名称配置"
        )
    if "timeout" in error_msg.lower() or "连接" in error_msg:
        return (
            f"网络连接失败。\n"
            f"错误详情: {error_msg}\n"
            "解决方案：检查网络连接，稍后重试"
        )
    if "rate" in error_msg.lower() or "429" in error_msg or "quota" in error_msg.lower():
        return (
            f"API 配额限制。\n"
            f"错误详情: {error_msg}\n"
            "解决方案：等待配额重置，或升级 API 套餐"
        )
    return (
        f"{task_label}。\n"
        f"错误详情: {error_msg}\n"
        "建议：检查配置文件 text_providers.yaml"
    )
