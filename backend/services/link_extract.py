"""
链接/长文转图文大纲服务

功能：
- 校验用户提供的 URL（防 SSRF），抓取网页正文文本
- 或直接接收用户粘贴的长文本
- 调用文本生成 AI，把正文提炼成与现有生成流程兼容的图文大纲
  （输出 topic + pages，pages 字段结构与 OutlineService 保持一致：index/type/content）
"""

import ipaddress
import logging
import os
import re
import socket
import yaml
from html.parser import HTMLParser
from pathlib import Path
from typing import Any, Dict, List, Optional
from urllib.parse import urljoin, urlparse

import requests

from backend.utils.text_client import get_text_chat_client

logger = logging.getLogger(__name__)

# 抓取限制
FETCH_TIMEOUT = 10          # 秒
MAX_RESPONSE_BYTES = 2 * 1024 * 1024  # 2MB
MAX_REDIRECTS = 3
# 送入 AI 的正文长度上限（字符），避免超长文章撑爆上下文
MAX_ARTICLE_CHARS = 20000
# 直接粘贴长文时的最小有效长度
MIN_TEXT_CHARS = 20


# 禁止访问的地址段（SSRF 防护）。
# 与 config_routes 的做法一致：不用 ip.is_private 一刀切，
# 避免 Fake-IP 代理环境（198.18.0.0/15）误杀全部合法域名。
_FORBIDDEN_NETWORKS = [
    ipaddress.ip_network('127.0.0.0/8'),      # 环回
    ipaddress.ip_network('10.0.0.0/8'),       # 私网 A
    ipaddress.ip_network('172.16.0.0/12'),    # 私网 B
    ipaddress.ip_network('192.168.0.0/16'),   # 私网 C
    ipaddress.ip_network('169.254.0.0/16'),   # 链路本地（含云元数据 169.254.169.254）
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


def validate_url(url: Optional[str]) -> Optional[str]:
    """
    校验用户提供的抓取 URL 是否安全（防 SSRF）。

    仅允许 http/https 协议；主机名为 IP 字面量时直接校验，
    为域名时解析所有 A/AAAA 记录逐个校验，任一命中私网/环回/保留地址即拒绝。

    Returns:
        Optional[str]: 不合法时返回错误描述，合法返回 None
    """
    if not url or not str(url).strip():
        return "链接不能为空"

    try:
        parsed = urlparse(str(url).strip())
    except ValueError:
        return "链接格式不正确"

    if parsed.scheme not in ('http', 'https'):
        return "仅支持 http/https 链接"

    hostname = parsed.hostname
    if not hostname:
        return "链接缺少有效的主机名"

    # 主机名本身就是 IP 字面量
    try:
        ip = ipaddress.ip_address(hostname.split('%')[0])
    except ValueError:
        ip = None

    if ip is not None:
        if _is_forbidden_ip(ip):
            return "不允许抓取私网、环回或保留地址"
        return None

    # 域名：解析为 IP 后逐个校验。
    # 与配置校验不同，这里解析失败直接拒绝——抓取场景下无法解析的域名必然抓取失败，
    # 提前拒绝可以给出更明确的错误提示。
    try:
        addr_infos = socket.getaddrinfo(hostname, None)
    except socket.gaierror:
        return "无法解析该域名，请检查链接是否正确"

    for info in addr_infos:
        try:
            resolved_ip = ipaddress.ip_address(str(info[4][0]).split('%')[0])
        except ValueError:
            return "域名解析结果异常"
        if _is_forbidden_ip(resolved_ip):
            return "该链接解析到私网、环回或保留地址，已拒绝抓取"

    return None


class _TextExtractor(HTMLParser):
    """基于标准库 html.parser 的正文文本提取器：剥离标签，跳过脚本/样式等非正文内容"""

    _SKIP_TAGS = {'script', 'style', 'noscript', 'template', 'svg', 'head',
                  'nav', 'footer', 'iframe', 'form', 'button'}
    _BLOCK_TAGS = {'p', 'div', 'br', 'li', 'tr', 'section', 'article',
                   'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'blockquote', 'pre'}

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self._chunks: List[str] = []
        self._skip_depth = 0
        self.title = ''
        self._in_title = False

    def handle_starttag(self, tag, attrs):
        if tag in self._SKIP_TAGS:
            self._skip_depth += 1
        if tag == 'title':
            self._in_title = True
        if tag in self._BLOCK_TAGS:
            self._chunks.append('\n')

    def handle_endtag(self, tag):
        if tag in self._SKIP_TAGS and self._skip_depth > 0:
            self._skip_depth -= 1
        if tag == 'title':
            self._in_title = False
        if tag in self._BLOCK_TAGS:
            self._chunks.append('\n')

    def handle_data(self, data):
        if self._in_title and not self.title:
            self.title = data.strip()
        if self._skip_depth == 0 and data.strip():
            self._chunks.append(data)

    def get_text(self) -> str:
        text = ''.join(self._chunks)
        # 压缩空白：行内多余空格、连续空行
        text = re.sub(r'[ \t\u3000]+', ' ', text)
        text = re.sub(r'\n\s*\n+', '\n\n', text)
        return text.strip()


class LinkExtractService:
    """链接/长文 → 图文大纲服务"""

    def __init__(self):
        logger.debug("初始化 LinkExtractService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"LinkExtractService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    # ==================== 配置与客户端（与 OutlineService 保持一致的模式） ====================

    def _load_text_config(self) -> dict:
        config_path = Path(__file__).parent.parent.parent / 'text_providers.yaml'
        if config_path.exists():
            try:
                with open(config_path, 'r', encoding='utf-8') as f:
                    return yaml.safe_load(f) or {}
            except yaml.YAMLError as e:
                logger.error(f"文本配置 YAML 解析失败: {e}")
                raise ValueError(
                    f"文本配置文件格式错误: text_providers.yaml\n"
                    f"YAML 解析错误: {e}\n"
                    "解决方案：检查 YAML 缩进和语法"
                )

        logger.warning("text_providers.yaml 不存在，使用默认配置")
        return {
            'active_provider': 'google_gemini',
            'providers': {
                'google_gemini': {
                    'type': 'google_gemini',
                    'model': 'gemini-2.0-flash-exp',
                    'temperature': 1.0,
                    'max_output_tokens': 8000
                }
            }
        }

    def _get_client(self):
        active_provider = self.text_config.get('active_provider', 'google_gemini')
        providers = self.text_config.get('providers', {})

        if not providers:
            raise ValueError(
                "未找到任何文本生成服务商配置。\n"
                "解决方案：\n"
                "1. 在系统设置页面添加文本生成服务商\n"
                "2. 或手动编辑 text_providers.yaml 文件"
            )

        if active_provider not in providers:
            available = ', '.join(providers.keys())
            raise ValueError(
                f"未找到文本生成服务商配置: {active_provider}\n"
                f"可用的服务商: {available}\n"
                "解决方案：在系统设置中选择一个可用的服务商"
            )

        provider_config = providers.get(active_provider, {})
        if not provider_config.get('api_key'):
            raise ValueError(
                f"文本服务商 {active_provider} 未配置 API Key\n"
                "解决方案：在系统设置页面编辑该服务商，填写 API Key"
            )

        return get_text_chat_client(provider_config)

    def _load_prompt_template(self) -> str:
        prompt_path = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "prompts",
            "link_prompt.txt"
        )
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    # ==================== 网页抓取 ====================

    def fetch_article_text(self, url: str) -> str:
        """
        抓取网页并提取正文文本。

        安全措施：
        - 抓取前 validate_url 校验（协议白名单 + 私网/环回/保留地址拒绝）
        - 禁用自动重定向，手动跟随并对每一跳重新校验（防重定向绕过）
        - 超时 10s、响应体上限 2MB（流式读取截断）
        - 只返回剥离标签后的正文文本，不回显上游原始响应体

        Raises:
            ValueError: URL 不合法或抓取/解析失败（错误信息可安全展示给用户）
        """
        current_url = url.strip()

        for _ in range(MAX_REDIRECTS + 1):
            error = validate_url(current_url)
            if error:
                raise ValueError(error)

            try:
                response = requests.get(
                    current_url,
                    timeout=FETCH_TIMEOUT,
                    allow_redirects=False,
                    stream=True,
                    headers={
                        'User-Agent': (
                            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) '
                            'AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0 Safari/537.36'
                        ),
                        'Accept': 'text/html,application/xhtml+xml;q=0.9,*/*;q=0.5',
                    },
                )
            except requests.Timeout:
                raise ValueError("抓取网页超时，请稍后重试或直接粘贴文章内容")
            except requests.RequestException as e:
                logger.warning(f"抓取网页失败: {current_url}, {e}")
                raise ValueError("无法访问该链接，请检查链接是否正确，或直接粘贴文章内容")

            try:
                # 手动跟随重定向，每一跳都重新做 SSRF 校验
                if response.status_code in (301, 302, 303, 307, 308):
                    location = response.headers.get('Location')
                    if not location:
                        raise ValueError("链接重定向异常，请直接粘贴文章内容")
                    current_url = urljoin(current_url, location)
                    continue

                if response.status_code != 200:
                    logger.warning(f"抓取网页返回 HTTP {response.status_code}: {current_url}")
                    raise ValueError(f"网页返回错误状态（HTTP {response.status_code}），请检查链接或直接粘贴文章内容")

                content_type = (response.headers.get('Content-Type') or '').lower()
                if content_type and ('html' not in content_type and 'text' not in content_type):
                    raise ValueError("该链接不是网页内容（如图片/文件），请提供文章页面链接")

                # 流式读取并限制大小
                raw = b''
                for chunk in response.iter_content(chunk_size=64 * 1024):
                    raw += chunk
                    if len(raw) > MAX_RESPONSE_BYTES:
                        logger.info(f"网页超过大小上限，截断读取: {current_url}")
                        break
            finally:
                response.close()

            html = raw.decode(response.encoding or 'utf-8', errors='replace')
            return self._extract_text_from_html(html)

        raise ValueError("链接重定向次数过多，已停止抓取")

    def _extract_text_from_html(self, html: str) -> str:
        """从 HTML 中提取正文文本（标准库解析，剥离脚本/样式/导航等）"""
        extractor = _TextExtractor()
        try:
            extractor.feed(html)
            extractor.close()
        except Exception as e:
            logger.warning(f"HTML 解析异常，退化为正则剥离标签: {e}")
            # 兜底：正则粗剥标签
            text = re.sub(r'<(script|style)[\s\S]*?</\1>', ' ', html, flags=re.IGNORECASE)
            text = re.sub(r'<[^>]+>', ' ', text)
            text = re.sub(r'\s+', ' ', text)
            return text.strip()

        text = extractor.get_text()
        if extractor.title:
            text = f"{extractor.title}\n\n{text}"
        return text

    # ==================== 大纲提炼 ====================

    def _parse_outline(self, outline_text: str) -> List[Dict[str, Any]]:
        """把 AI 输出解析为 pages（与 OutlineService._parse_outline 结构一致）"""
        if '<page>' in outline_text:
            pages_raw = re.split(r'<page>', outline_text, flags=re.IGNORECASE)
        else:
            pages_raw = outline_text.split("---")

        pages = []
        for index, page_text in enumerate(pages_raw):
            page_text = page_text.strip()
            if not page_text:
                continue

            page_type = "content"
            type_match = re.match(r"\[(\S+)\]", page_text)
            if type_match:
                type_mapping = {
                    "封面": "cover",
                    "内容": "content",
                    "总结": "summary",
                }
                page_type = type_mapping.get(type_match.group(1), "content")

            pages.append({
                "index": index,
                "type": page_type,
                "content": page_text
            })

        # 重新编号，保证 index 连续（过滤空页后可能有空洞）
        for idx, page in enumerate(pages):
            page["index"] = idx

        return pages

    def _split_topic_and_outline(self, response_text: str) -> tuple:
        """
        从 AI 输出中拆出「主题：xxx」行与大纲正文。

        Returns:
            (topic, outline_text)
        """
        text = response_text.strip()
        topic = ''

        match = re.search(r'^\s*主题[:：]\s*(.+?)\s*$', text, flags=re.MULTILINE)
        if match:
            topic = match.group(1).strip()
            # 去掉主题行，保留其后的大纲正文
            text = (text[:match.start()] + text[match.end():]).strip()

        if not topic:
            # 兜底：取封面页第一行标题作为主题
            first_line = next((line.strip() for line in text.splitlines()
                               if line.strip() and not line.strip().startswith('[')), '')
            topic = re.sub(r'^标题[:：]\s*', '', first_line)[:50] or '图文卡片'

        return topic, text

    def extract_outline(
        self,
        url: Optional[str] = None,
        raw_text: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        链接或长文 → 图文大纲。

        参数：
            url: 网页链接（与 raw_text 二选一，优先 url）
            raw_text: 用户直接粘贴的长文本

        返回：
            成功: {"success": True, "topic": str, "outline": str, "pages": [{index,type,content}]}
            失败: {"success": False, "error": str}
        """
        try:
            if url:
                logger.info(f"开始抓取链接: {url[:100]}")
                article_text = self.fetch_article_text(url)
            elif raw_text and raw_text.strip():
                article_text = raw_text.strip()
            else:
                raise ValueError("请提供网页链接或文章内容")

            if len(article_text) < MIN_TEXT_CHARS:
                raise ValueError("提取到的正文内容太少，无法生成大纲，请直接粘贴文章内容")

            if len(article_text) > MAX_ARTICLE_CHARS:
                logger.info(f"正文过长（{len(article_text)} 字符），截断至 {MAX_ARTICLE_CHARS}")
                article_text = article_text[:MAX_ARTICLE_CHARS]

            prompt = self.prompt_template.format(article_text=article_text)

            active_provider = self.text_config.get('active_provider', 'google_gemini')
            provider_config = self.text_config.get('providers', {}).get(active_provider, {})
            model = provider_config.get('model', 'gemini-2.0-flash-exp')
            temperature = provider_config.get('temperature', 1.0)
            max_output_tokens = provider_config.get('max_output_tokens', 8000)

            logger.info(f"调用文本生成 API 提炼大纲: model={model}, 正文长度={len(article_text)}")
            response_text = self.client.generate_text(
                prompt=prompt,
                model=model,
                temperature=temperature,
                max_output_tokens=max_output_tokens
            )

            topic, outline_text = self._split_topic_and_outline(response_text)
            pages = self._parse_outline(outline_text)

            if not pages:
                raise ValueError("AI 未能生成有效的大纲，请重试")

            logger.info(f"链接/长文大纲生成完成: topic={topic[:30]}, 共 {len(pages)} 页")
            return {
                "success": True,
                "topic": topic,
                "outline": outline_text,
                "pages": pages
            }

        except ValueError as e:
            # 业务校验类错误，信息可直接展示给用户
            logger.warning(f"链接/长文大纲生成失败: {e}")
            return {"success": False, "error": str(e)}
        except Exception as e:
            error_msg = str(e)
            logger.error(f"链接/长文大纲生成失败: {error_msg}")
            return {
                "success": False,
                "error": (
                    f"大纲生成失败。\n"
                    f"错误详情: {error_msg}\n"
                    "可能原因：\n"
                    "1. Text API 配置错误或密钥无效\n"
                    "2. 网络连接问题\n"
                    "建议：检查配置文件 text_providers.yaml"
                )
            }


def get_link_extract_service() -> LinkExtractService:
    """
    获取链接提取服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return LinkExtractService()
