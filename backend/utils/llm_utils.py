"""
LLM 调用共享工具

集中收敛各文本服务（outline/content/title/topic/reply/cover/rewrite/
benchmark/link_extract/analytics）原先各自复制的公共逻辑：

- load_text_config: 加载 text_providers.yaml 配置
- get_text_client: 根据配置构建文本生成客户端
- resolve_generation_params: 从配置解析 model/temperature/max_output_tokens
- load_prompt_template: 加载提示词模板文件
- parse_llm_json: 解析 LLM 返回的 JSON（含 ```json 代码块剥壳、保守 JSON 修复
  与大括号截取降级）
- generate_and_parse_json: 调用 LLM 并解析 JSON，解析失败自动带纠正提示重试一次
- classify_llm_error: 把底层异常归一化为面向用户的详细错误文案

注意：所有错误消息文本与原各服务实现逐字一致，不要随意改动措辞。
"""

import json
import logging
import re
from typing import Any, Callable, Dict, Iterator, List, Tuple, Union

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


def _repair_json_candidate(text: str, *, complete_truncated: bool = False) -> str:
    """
    对疑似 JSON 的文本做保守修复，返回修复后的字符串（不保证合法，
    由调用方 json.loads 验证）。只处理几类模型高频输出的机械性错误：

    - 字符串内的裸换行/回车/制表符/其他控制字符 → 转义
    - 单引号包裹的键/值 → 双引号（仅在语法上期望字符串出现的位置）
    - 尾逗号（`,}` / `,]`）→ 删除
    - complete_truncated=True 时：输出被截断的 JSON 补齐未闭合的
      字符串与括号（会丢弃末尾不完整的键值对，属最后手段）

    任何修复都不改写字符串内容本身；修复结果解析失败时调用方继续降级。
    """
    out: List[str] = []
    stack: List[str] = []
    in_string = False
    quote_char = '"'
    i = 0
    length = len(text)

    def _strip_trailing_comma():
        j = len(out) - 1
        while j >= 0 and out[j] in (' ', '\t', '\n', '\r'):
            j -= 1
        if j >= 0 and out[j] == ',':
            del out[j]

    def _prev_significant() -> str:
        for ch in reversed(out):
            if ch not in (' ', '\t', '\n', '\r'):
                return ch
        return ''

    while i < length:
        ch = text[i]
        if in_string:
            if ch == '\\':
                nxt = text[i + 1] if i + 1 < length else ''
                if quote_char == "'" and nxt == "'":
                    # 单引号字符串里的 \' 在 JSON 中不合法，还原为裸单引号
                    out.append("'")
                    i += 2
                    continue
                out.append(ch)
                if nxt:
                    out.append(nxt)
                    i += 2
                    continue
            elif ch == quote_char:
                in_string = False
                out.append('"')
            elif ch == '"':
                # 单引号字符串内部的双引号需转义
                out.append('\\"')
            elif ch == '\n':
                out.append('\\n')
            elif ch == '\r':
                out.append('\\r')
            elif ch == '\t':
                out.append('\\t')
            elif ord(ch) < 0x20:
                out.append('\\u%04x' % ord(ch))
            else:
                out.append(ch)
        else:
            if ch == '"':
                in_string = True
                quote_char = '"'
                out.append('"')
            elif ch == "'" and _prev_significant() in ('{', '[', ',', ':', ''):
                # 仅在语法上期望字符串的位置把单引号视为字符串定界符
                in_string = True
                quote_char = "'"
                out.append('"')
            elif ch in '{[':
                stack.append(ch)
                out.append(ch)
            elif ch in '}]':
                _strip_trailing_comma()
                if stack:
                    stack.pop()
                out.append(ch)
            else:
                out.append(ch)
        i += 1

    if complete_truncated and (in_string or stack):
        if in_string:
            # 截断可能落在转义序列中间，去掉孤立的结尾反斜杠
            if out and out[-1] == '\\':
                out.pop()
            out.append('"')
        # 丢弃末尾不完整的语法单元（如悬空的 `"key":` 或逗号）
        j = len(out) - 1
        while j >= 0 and out[j] in (' ', '\t', '\n', '\r'):
            j -= 1
        if j >= 0 and out[j] == ':':
            # 悬空键：连同键名一起回退
            del out[j:]
            k = len(out) - 1
            while k >= 0 and out[k] in (' ', '\t', '\n', '\r'):
                k -= 1
            if k >= 0 and out[k] == '"':
                # 回退整个 "key" 字符串
                k -= 1
                while k >= 0 and out[k] != '"':
                    k -= 1
                if k >= 0:
                    del out[k:]
        _strip_trailing_comma()
        for opener in reversed(stack):
            out.append('}' if opener == '{' else ']')

    return ''.join(out)


def _iter_json_candidates(response_text: str) -> Iterator[str]:
    """依次产出候选 JSON 文本：原文 → 代码块内容 → 大括号截取"""
    yield response_text

    json_match = re.search(r'```(?:json)?\s*\n?([\s\S]*?)\n?```', response_text)
    if json_match:
        yield json_match.group(1).strip()

    start_idx = response_text.find('{')
    end_idx = response_text.rfind('}')
    if start_idx != -1 and end_idx != -1:
        yield response_text[start_idx:end_idx + 1]


def parse_llm_json(response_text: str) -> Dict[str, Any]:
    """
    解析 LLM 返回的 JSON 响应（多级降级策略）：

    1. 直接 json.loads
    2. 从 ```json ... ``` / ``` ... ``` 代码块中提取
    3. 截取首个 '{' 到最后一个 '}' 之间的内容

    每级降级都先尝试直接解析，失败后再对该候选做保守 JSON 修复
    （尾逗号/单引号/字符串内裸换行等）；全部失败后最后尝试对截断
    输出做括号补全。修复结果必须能通过 json.loads，否则继续降级，
    绝不产出语义被改的结果。

    Raises:
        ValueError: 所有策略均失败时抛出（消息与原各服务实现一致）
    """
    candidates = list(_iter_json_candidates(response_text))

    for candidate in candidates:
        # 逐级：先直接解析，再尝试保守修复
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            pass
        try:
            repaired = _repair_json_candidate(candidate)
            if repaired != candidate:
                return json.loads(repaired)
        except json.JSONDecodeError:
            pass

    # 最后手段：按截断输出处理，补齐未闭合的字符串与括号
    for candidate in candidates:
        try:
            return json.loads(
                _repair_json_candidate(candidate, complete_truncated=True)
            )
        except json.JSONDecodeError:
            pass

    logger.error(f"无法解析 JSON 响应: {response_text[:200]}...")
    raise ValueError("AI 返回的内容格式不正确，无法解析")


# 解析失败重试时追加到 prompt 末尾的纠正提示
JSON_RETRY_PROMPT_SUFFIX = (
    "\n\n【格式纠正】你上次的输出不是合法 JSON，无法被程序解析。"
    "请重新生成，并且只输出一个合法的 JSON 对象："
    "不要输出任何解释文字或 Markdown 代码块，"
    "字符串内的换行必须写成 \\n，不要使用单引号，不要出现尾逗号。"
)


def generate_and_parse_json(call_fn: Callable[[str], str]) -> Dict[str, Any]:
    """
    调用 LLM 生成文本并解析为 JSON；解析失败时带纠正提示自动重试一次。

    Args:
        call_fn: 接收一个 prompt 追加后缀（首次调用为空串，重试时为
            JSON_RETRY_PROMPT_SUFFIX）并返回 LLM 输出文本的函数。
            由调用方闭包持有 prompt / model 等参数与错误分类行为。

    Returns:
        解析后的 JSON 数据

    Raises:
        ValueError: 两次输出均无法解析时抛出（消息与 parse_llm_json 一致，
            保持各服务既有错误分类行为不变）
    """
    response_text = call_fn("")
    logger.debug(f"API 返回文本长度: {len(response_text)} 字符")
    try:
        return parse_llm_json(response_text)
    except ValueError:
        logger.warning("LLM 输出 JSON 解析失败，追加格式纠正提示重试一次")

    retry_text = call_fn(JSON_RETRY_PROMPT_SUFFIX)
    logger.debug(f"重试后 API 返回文本长度: {len(retry_text)} 字符")
    return parse_llm_json(retry_text)


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
