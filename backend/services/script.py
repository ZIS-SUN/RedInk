"""
口播视频脚本生成服务

把图文内容（正文/大纲/主题）转成短视频口播/分镜脚本：
整体信息（片名/钩子/BGM 情绪）+ 时间轴分镜列表 + 结尾 CTA
"""

import logging
from typing import Any, Dict, List, Optional

from backend.services.rewrite import build_brand_constraint
from backend.utils.llm_utils import (
    classify_llm_error,
    generate_and_parse_json,
    get_text_client,
    load_prompt_template,
    load_text_config,
    parse_llm_json,
    resolve_generation_params,
)

logger = logging.getLogger(__name__)

# 支持的时长档位代号 -> 中文名
SUPPORTED_DURATIONS = {
    '30s': '30 秒',
    '60s': '60 秒',
    '3min': '3 分钟',
}

# 支持的场景类型代号 -> 中文名
SUPPORTED_SCENES = {
    'talking_head': '口播出镜',
    'voiceover': '图文配音',
    'drama': '情景剧情',
}

# 未指定时的默认档位
DEFAULT_DURATION = '60s'
DEFAULT_SCENE = 'talking_head'


def _clean_text(value: Any) -> str:
    """把任意值收敛为去首尾空白的字符串（None/非字符串安全）"""
    if value is None:
        return ""
    return str(value).strip()


def normalize_segments(raw_segments: Any) -> List[Dict[str, str]]:
    """
    归一化 AI 返回的分镜列表：
    - 跳过非字典项
    - 每段收敛为 time_range/visual/voiceover/subtitle_notes 四个字符串字段
    - 台词为空的段落视为无效，直接丢弃
    """
    if not isinstance(raw_segments, list):
        return []

    segments: List[Dict[str, str]] = []
    for item in raw_segments:
        if not isinstance(item, dict):
            continue
        voiceover = _clean_text(item.get('voiceover'))
        if not voiceover:
            continue
        segments.append({
            "time_range": _clean_text(item.get('time_range')),
            "visual": _clean_text(item.get('visual')),
            "voiceover": voiceover,
            "subtitle_notes": _clean_text(item.get('subtitle_notes')),
        })
    return segments


class ScriptService:
    """口播视频脚本生成服务"""

    def __init__(self):
        logger.debug("初始化 ScriptService...")
        self.text_config = self._load_text_config()
        self.client = self._get_client()
        self.prompt_template = self._load_prompt_template()
        logger.info(f"ScriptService 初始化完成，使用服务商: {self.text_config.get('active_provider')}")

    def _load_text_config(self) -> dict:
        """加载文本生成配置"""
        return load_text_config()

    def _get_client(self):
        """根据配置获取客户端"""
        return get_text_client(self.text_config)

    def _load_prompt_template(self) -> str:
        """加载提示词模板"""
        return load_prompt_template('backend/prompts/script_prompt.txt')

    def _parse_json_response(self, response_text: str) -> Dict[str, Any]:
        """解析 AI 返回的 JSON 响应"""
        return parse_llm_json(response_text)

    def generate_script(
        self,
        content: str,
        duration: str = DEFAULT_DURATION,
        scene: str = DEFAULT_SCENE,
        brand: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """
        把图文内容转成口播视频脚本

        参数：
            content: 图文内容（正文/大纲）或主题
            duration: 时长档位代号（30s/60s/3min）
            scene: 场景类型代号（talking_head/voiceover/drama）
            brand: 品牌档案字典（可选），提供时会把品牌人设约束注入 prompt

        返回：
            包含 script 的字典：title/hook/bgm_mood/duration/scene/segments/cta
        """
        try:
            logger.info(f"开始生成口播脚本: duration={duration}, scene={scene}, 长度={len(content)}")

            duration_label = SUPPORTED_DURATIONS.get(duration, SUPPORTED_DURATIONS[DEFAULT_DURATION])
            scene_label = SUPPORTED_SCENES.get(scene, SUPPORTED_SCENES[DEFAULT_SCENE])

            # 构建提示词
            prompt = self.prompt_template.format(
                content=content,
                duration_label=duration_label,
                scene_label=scene_label
            )

            # 品牌人设约束以字符串追加方式融入，避免破坏模板占位符
            brand_constraint = build_brand_constraint(brand)
            if brand_constraint:
                logger.info(f"注入品牌人设约束: brand={brand.get('name', '')}")
                prompt += brand_constraint

            # 从配置中获取模型参数
            model, temperature, max_output_tokens = resolve_generation_params(
                self.text_config, default_max_output_tokens=8000
            )

            logger.info(f"调用文本生成 API: model={model}, temperature={temperature}")
            # 生成 + 解析 JSON（json_mode 约束输出格式；解析失败自动带纠正提示重试一次）
            script_data = generate_and_parse_json(
                lambda prompt_suffix: self.client.generate_text(
                    prompt=prompt + prompt_suffix,
                    model=model,
                    temperature=temperature,
                    max_output_tokens=max_output_tokens,
                    json_mode=True
                )
            )

            segments = normalize_segments(script_data.get('segments'))
            if not segments:
                raise ValueError("AI 返回结果中缺少有效的 segments 分镜列表")

            script = {
                "title": _clean_text(script_data.get('title')),
                "hook": _clean_text(script_data.get('hook')),
                "bgm_mood": _clean_text(script_data.get('bgm_mood')),
                "duration": duration,
                "scene": scene,
                "segments": segments,
                "cta": _clean_text(script_data.get('cta')),
            }

            logger.info(f"口播脚本生成完成: 共 {len(segments)} 段分镜")

            return {
                "success": True,
                "script": script
            }

        except Exception as e:
            logger.error(f"口播脚本生成失败: {e}")
            return {
                "success": False,
                "error": classify_llm_error(e, task_label="口播脚本生成失败")
            }


def get_script_service() -> ScriptService:
    """
    获取口播脚本生成服务实例
    每次调用都创建新实例以确保配置是最新的
    """
    return ScriptService()
