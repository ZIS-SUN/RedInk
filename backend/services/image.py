"""图片生成服务"""
import logging
import os
import tempfile
import threading
import uuid
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Dict, Any, Generator, List, Optional, Tuple
from backend.config import Config
from backend.paths import get_data_root, resource_path
from backend.generators.factory import ImageGeneratorFactory
from backend.generators.image_provider_policy import ImageProviderPolicy
from backend.services.history import get_history_service, validate_safe_id
from backend.services.history_image_merger import HistoryImageMerger
from backend.services.image_rate_limiter import ImageRateLimiter
from backend.utils.image_compressor import compress_image

logger = logging.getLogger(__name__)


class ImageService:
    """图片生成服务类"""

    # 并发配置
    AUTO_RETRY_COUNT = 1  # 不自动重试，超时后让用户手动重试

    def __init__(self, provider_name: str = None):
        """
        初始化图片生成服务

        Args:
            provider_name: 服务商名称，如果为None则使用配置文件中的激活服务商
        """
        logger.debug("初始化 ImageService...")

        # 获取服务商配置
        if provider_name is None:
            provider_name = Config.get_active_image_provider()

        logger.info(f"使用图片服务商: {provider_name}")
        provider_config = Config.get_image_provider_config(provider_name)

        # 创建生成器实例
        provider_type = provider_config.get('type', provider_name)
        logger.debug(f"创建生成器: type={provider_type}")
        self.generator = ImageGeneratorFactory.create(provider_type, provider_config)

        # 保存配置信息
        self.provider_name = provider_name
        self.provider_config = provider_config
        self.policy = ImageProviderPolicy.from_config(
            provider_config,
            default_model=provider_config.get('model', 'default-model'),
        )
        self.worker_count = self.policy.worker_count
        self.rate_limiter = ImageRateLimiter(
            max_concurrent=self.worker_count,
            interval_seconds=self.policy.request_interval_seconds,
        )
        self.history_service = get_history_service()

        # 检查是否启用短 prompt 模式
        self.use_short_prompt = provider_config.get('short_prompt', False)

        # 加载提示词模板
        self.prompt_template = self._load_prompt_template()
        self.prompt_template_short = self._load_prompt_template(short=True)

        # 历史记录根目录（可写数据目录下）
        self.history_root_dir = str(get_data_root() / "history")
        os.makedirs(self.history_root_dir, exist_ok=True)

        # 兼容保留：旧代码/测试可能设置此属性作为任务目录回退。
        # 生产路径不再读写它（任务目录由 task_id 显式推导，避免并发串目录）。
        self.current_task_dir = None

        # 存储任务状态（用于重试），带容量上限防止无限增长
        self._task_states: Dict[str, Dict] = {}

        logger.info(f"ImageService 初始化完成: provider={provider_name}, type={provider_type}")

    # 任务状态最多保留的条目数（超出后按插入顺序淘汰最旧的）
    _TASK_STATE_CAPACITY = 32

    @property
    def _task_states_lock(self) -> "threading.Lock":
        """任务状态字典的锁（惰性创建，兼容通过 __new__ 构造的实例）。"""
        lock = self.__dict__.get("_task_states_lock_obj")
        if lock is None:
            lock = threading.Lock()
            self.__dict__["_task_states_lock_obj"] = lock
        return lock

    def _get_task_dir(self, task_id: str) -> str:
        """
        根据 task_id 推导任务目录（不依赖共享实例属性，避免并发任务串目录）。

        仅当实例未配置 history_root_dir 时（旧用法/测试通过 __new__ 构造），
        才回退到 current_task_dir。
        """
        root = getattr(self, "history_root_dir", None)
        if root:
            return os.path.join(root, task_id)
        fallback = getattr(self, "current_task_dir", None)
        if fallback:
            return fallback
        raise ValueError("任务目录未设置")

    def _set_task_state(self, task_id: str, state: Dict) -> None:
        """写入任务状态，并在超出容量时淘汰最旧的条目。"""
        with self._task_states_lock:
            self._task_states[task_id] = state
            if len(self._task_states) > self._TASK_STATE_CAPACITY:
                # 按插入顺序淘汰最旧的（dict 保序）
                excess = len(self._task_states) - self._TASK_STATE_CAPACITY
                for old_task_id in list(self._task_states.keys())[:excess]:
                    if old_task_id != task_id:
                        self._task_states.pop(old_task_id, None)

    def _release_task_heavy_data(self, task_id: str) -> None:
        """
        释放任务状态中的大对象（封面图、用户参考图），保留轻量元数据供
        任务状态查询和重试使用。重试时封面图会从磁盘按需加载。
        """
        with self._task_states_lock:
            state = self._task_states.get(task_id)
            if state:
                state["cover_image"] = None
                state["user_images"] = None

    @staticmethod
    def _validate_page(page: Any) -> Optional[str]:
        """
        校验页面结构，返回错误消息；合法时返回 None。

        合法页面必须是 dict 且包含 int 型非负 index、type、content 字段。
        """
        if not isinstance(page, dict):
            return "页面数据格式错误：不是有效的对象"
        index = page.get("index")
        if not isinstance(index, int) or isinstance(index, bool) or index < 0:
            return "页面数据缺少有效的 index 字段"
        if page.get("type") is None:
            return "页面数据缺少 type 字段"
        if page.get("content") is None:
            return "页面数据缺少 content 字段"
        return None

    @staticmethod
    def _page_index(page: Any, default: int = -1) -> int:
        """安全获取页面 index（缺失或非法时返回 default）。"""
        if isinstance(page, dict):
            index = page.get("index")
            if isinstance(index, int) and not isinstance(index, bool):
                return index
        return default

    @staticmethod
    def _count_generated(generated_images: List[str]) -> int:
        return sum(1 for filename in generated_images if filename)

    @staticmethod
    def _remember_generated(generated_images: List[str], index: int, filename: str, total: int):
        target_len = max(len(generated_images), total, index + 1)
        while len(generated_images) < target_len:
            generated_images.append("")
        generated_images[index] = filename

    # 风格块的分节标题（注入与末尾重申引用同一名称，方便模型回指）
    _STYLE_SECTION_TITLE = "【视觉风格规范 · 最高优先级】"

    # 末尾重申：图像模型对 prompt 结尾更敏感，把关键要求在最末端重复一次
    _STYLE_REINFORCEMENT = (
        "\n\n再次强调：画面必须严格遵循上方【视觉风格规范 · 最高优先级】中的每一条要求，"
        "全套图片风格保持统一；如与其他描述或模型默认审美冲突，一律以该规范为准。"
    )

    # 单张重试时追加的质量反馈提示（轻量变异，提高重试成功率）
    _RETRY_QUALITY_HINT = (
        "\n\n补充要求（本次为重新生成）：上一次生成的图片在文字准确性或排版上不达标。"
        "本次请特别注意：画面中的所有文字必须与给定文案逐字一致（不错字、不漏字、不自造字），"
        "排版必须工整、对齐、留白合理。"
    )

    @staticmethod
    def _apply_style_prompt(prompt: str, style_prompt: str) -> str:
        """
        在已构建好的 prompt 末尾以强调框架注入风格描述块。

        用字符串拼接而非模板占位符，避免给模板新增占位符导致
        其他 .format 调用点 KeyError。style_prompt 为空时原样返回。

        注入结构：分隔线 + 分节标题 + 优先级声明 + 风格正文，
        配合 _compose_prompt 在 prompt 最末端追加的重申句形成
        「结构化注入 + 结尾重复」的双重强调。
        """
        style = (style_prompt or "").strip()
        if not style:
            return prompt
        return (
            f"{prompt}\n\n"
            "========================================\n"
            f"{ImageService._STYLE_SECTION_TITLE}\n"
            "以下视觉风格要求优先级最高，覆盖上文所有描述与模型默认审美，"
            "全套图片（封面与内容页）必须统一遵守：\n"
            f"{style}\n"
            "========================================"
        )

    def _compose_prompt(
        self, prompt: str, style_prompt: str = "", retry_hint: bool = False
    ) -> str:
        """
        统一的 prompt 组装出口，按固定顺序拼装各追加段落：

        1. 模板渲染结果（page_content/page_type/full_outline/user_topic）
        2. 风格块（强调框架注入，见 _apply_style_prompt；为空时跳过）
        3. 品牌视觉约束（见 _apply_brand_visual_prompt；无品牌时跳过）
        4. 风格重申句（仅在有风格块时追加，利用模型对结尾的敏感度）
        5. 重试质量提示（仅单张重试路径追加）
        """
        prompt = self._apply_style_prompt(prompt, style_prompt)
        prompt = self._apply_brand_visual_prompt(prompt)
        if (style_prompt or "").strip():
            prompt += self._STYLE_REINFORCEMENT
        if retry_hint:
            prompt += self._RETRY_QUALITY_HINT
        return prompt

    @staticmethod
    def _apply_brand_visual_prompt(prompt: str) -> str:
        """
        在已构建好的 prompt 末尾追加当前启用品牌的视觉约束段落
        （与 _apply_style_prompt 相同的运行时字符串拼接模式）。

        软失败：无启用品牌 / 品牌未设置视觉字段（如主色调）/ 读取异常时
        一律原样返回 prompt，绝不因品牌数据问题中断图片生成。
        """
        try:
            # 惰性导入：避免图片服务在 brand 环境异常时初始化失败
            from backend.services.brand import resolve_brand_for_prompt
            from backend.services.rewrite import build_brand_visual_constraint
            visual = build_brand_visual_constraint(resolve_brand_for_prompt())
        except Exception as e:
            logger.warning(f"读取品牌视觉约束失败，忽略: {e}")
            return prompt
        if not visual:
            return prompt
        return prompt + visual

    def _load_prompt_template(self, short: bool = False) -> str:
        """
        加载 Prompt 模板

        优先读取可写数据目录下的自定义模板（custom_prompts/<filename>），
        存在且非空时生效；否则回退包内默认模板。
        """
        filename = "image_prompt_short.txt" if short else "image_prompt.txt"

        try:
            custom_path = get_data_root() / "custom_prompts" / filename
            if custom_path.exists():
                content = custom_path.read_text(encoding="utf-8")
                if content.strip():
                    logger.debug(f"使用自定义 Prompt 模板: {custom_path}")
                    return content
        except OSError as e:
            logger.warning(f"读取自定义 Prompt 模板失败（{filename}），回退默认模板: {e}")

        prompt_path = resource_path(f'backend/prompts/{filename}')
        if not os.path.exists(prompt_path):
            # 如果短模板不存在，返回空字符串
            return ""
        with open(prompt_path, "r", encoding="utf-8") as f:
            return f.read()

    def _save_image(self, image_data: bytes, filename: str, task_dir: str = None) -> str:
        """
        保存图片到本地，同时生成缩略图

        Args:
            image_data: 图片二进制数据
            filename: 文件名
            task_dir: 任务目录（调用方应显式传入本任务的目录）

        Returns:
            保存的文件路径
        """
        if task_dir is None:
            # 兼容旧调用方式的回退（生产路径总是显式传入）
            task_dir = getattr(self, "current_task_dir", None)

        if task_dir is None:
            raise ValueError("任务目录未设置")

        # 保存原图（原子写入，避免进程中断/并发重试留下半截图片）
        filepath = os.path.join(task_dir, filename)
        self._atomic_write_bytes(filepath, image_data)

        # 生成缩略图（50KB左右）
        thumbnail_data = compress_image(image_data, max_size_kb=50)
        thumbnail_filename = f"thumb_{filename}"
        thumbnail_path = os.path.join(task_dir, thumbnail_filename)
        self._atomic_write_bytes(thumbnail_path, thumbnail_data)

        return filepath

    @staticmethod
    def _atomic_write_bytes(filepath: str, data: bytes) -> None:
        """
        原子写二进制文件：先写同目录临时文件，再 os.replace() 覆盖，
        避免其他读者读到半截文件（与各服务的 _atomic_write_json 模式一致）。
        """
        dir_name = os.path.dirname(filepath) or "."
        fd, tmp_path = tempfile.mkstemp(prefix=".tmp_", dir=dir_name)
        try:
            with os.fdopen(fd, "wb") as f:
                f.write(data)
            os.replace(tmp_path, filepath)
        except Exception:
            try:
                os.remove(tmp_path)
            except OSError:
                pass
            raise

    def _generate_single_image(
        self,
        page: Dict,
        task_id: str,
        reference_image: Optional[bytes] = None,
        retry_count: int = 0,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = "",
        record_id: Optional[str] = None,
        total_count: Optional[int] = None,
        style_prompt: str = "",
        retry_hint: bool = False
    ) -> Tuple[int, bool, Optional[str], Optional[str]]:
        """
        生成单张图片（带自动重试）

        Args:
            page: 页面数据
            task_id: 任务ID
            reference_image: 参考图片（封面图）
            retry_count: 当前重试次数
            full_outline: 完整的大纲文本
            user_images: 用户上传的参考图片列表
            user_topic: 用户原始输入
            style_prompt: 风格模板的风格描述（可选，为空时不追加）
            retry_hint: 是否在 prompt 末尾追加重试质量提示（单张重试路径为 True）

        Returns:
            (index, success, filename, error_message)
        """
        # 统一校验页面结构，缺字段时返回失败而不是抛 KeyError 中断整条流
        validation_error = self._validate_page(page)
        if validation_error:
            index = self._page_index(page)
            logger.error(f"❌ 图片 [{index}] 页面数据非法: {validation_error}")
            return (index, False, None, validation_error)

        index = page["index"]
        page_type = page["type"]
        page_content = page["content"]

        try:
            logger.debug(f"生成图片 [{index}]: type={page_type}")

            # 根据配置选择模板（短 prompt 或完整 prompt）
            if self.use_short_prompt and self.prompt_template_short:
                # 短 prompt 模式：只包含页面类型和内容
                prompt = self.prompt_template_short.format(
                    page_content=page_content,
                    page_type=page_type
                )
                logger.debug(f"  使用短 prompt 模式 ({len(prompt)} 字符)")
            else:
                # 完整 prompt 模式：包含大纲和用户需求
                prompt = self.prompt_template.format(
                    page_content=page_content,
                    page_type=page_type,
                    full_outline=full_outline,
                    user_topic=user_topic if user_topic else "未提供"
                )

            # 统一组装：风格块（强调框架）→ 品牌视觉约束 → 风格重申 → 重试提示
            prompt = self._compose_prompt(prompt, style_prompt, retry_hint=retry_hint)

            # 调用生成器生成图片。所有路径共用 limiter，避免批量和重试打爆上游。
            with self.rate_limiter.acquire():
                if self.provider_config.get('type') == 'google_genai':
                    logger.debug(f"  使用 Google GenAI 生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'gemini-3-pro-image-preview'),
                        reference_image=reference_image,
                    )
                elif self.provider_config.get('type') == 'image_api':
                    logger.debug(f"  使用 Image API 生成器")
                    # Image API 支持多张参考图片
                    # 组合参考图片：用户上传的图片 + 封面图
                    reference_images = []
                    if user_images:
                        reference_images.extend(user_images)
                    if reference_image:
                        reference_images.append(reference_image)

                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        aspect_ratio=self.provider_config.get('default_aspect_ratio', '3:4'),
                        temperature=self.provider_config.get('temperature', 1.0),
                        model=self.provider_config.get('model', 'nano-banana-2'),
                        reference_images=reference_images if reference_images else None,
                    )
                else:
                    logger.debug(f"  使用 OpenAI 兼容生成器")
                    image_data = self.generator.generate_image(
                        prompt=prompt,
                        size=self.provider_config.get('default_size', '1024x1024'),
                        model=self.provider_config.get('model'),
                        quality=self.provider_config.get('quality', 'standard'),
                    )

            # 保存图片（由 task_id 显式推导本任务目录，避免并发串目录）
            filename = f"{index}.png"
            self._save_image(image_data, filename, self._get_task_dir(task_id))
            logger.info(f"✅ 图片 [{index}] 生成成功: {filename}")

            if record_id:
                self.history_service.merge_generated_image(
                    record_id,
                    task_id,
                    index,
                    filename,
                    total_count=total_count,
                )

            return (index, True, filename, None)

        except Exception as e:
            error_msg = str(e)
            logger.error(f"❌ 图片 [{index}] 生成失败: {error_msg[:200]}")
            return (index, False, None, error_msg)

    def generate_images(
        self,
        pages: list,
        task_id: str = None,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = "",
        record_id: Optional[str] = None,
        force: bool = False,
        style_prompt: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """
        生成图片（生成器，支持 SSE 流式返回）
        优化版本：先生成封面，然后并发生成其他页面

        先做参数校验再返回内部生成器，保证非法 task_id 在进入 SSE 流
        之前就抛错（路由层可正常返回 400，而不是流中断）。

        Args:
            pages: 页面列表
            task_id: 任务 ID（可选）
            full_outline: 完整的大纲文本（用于保持风格一致）
            user_images: 用户上传的参考图片列表（可选）
            user_topic: 用户原始输入（用于保持意图一致）
            style_prompt: 风格模板的风格描述（可选，封面页与内容页统一应用）

        Yields:
            进度事件字典
        """
        # 防止 task_id / record_id 路径遍历写入（如 "../../x"）
        if task_id is not None:
            validate_safe_id(task_id, "task_id")
        if record_id:
            validate_safe_id(record_id, "record_id")

        return self._generate_images_stream(
            pages,
            task_id=task_id,
            full_outline=full_outline,
            user_images=user_images,
            user_topic=user_topic,
            record_id=record_id,
            force=force,
            style_prompt=style_prompt,
        )

    def _generate_images_stream(
        self,
        pages: list,
        task_id: str = None,
        full_outline: str = "",
        user_images: Optional[List[bytes]] = None,
        user_topic: str = "",
        record_id: Optional[str] = None,
        force: bool = False,
        style_prompt: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """generate_images 的内部生成器实现（参数校验已在外层完成）。"""
        if record_id and not force:
            cached_events = self.get_cached_generation_events(record_id, pages)
            if cached_events:
                for event in cached_events:
                    yield event
                return

        if task_id is None and record_id:
            record = self.history_service.get_record(record_id, sync_images=True)
            task_id = record.get("images", {}).get("task_id") if record else None

        if task_id is None:
            task_id = f"task_{uuid.uuid4().hex[:8]}"

        logger.info(f"开始图片生成任务: task_id={task_id}, pages={len(pages)}")

        # 创建任务专属目录（局部变量，不写共享实例属性，避免并发任务串目录）
        task_dir = os.path.join(self.history_root_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)
        logger.debug(f"任务目录: {task_dir}")

        total = len(pages)
        generated_images = [""] * total
        failed_pages = []
        cover_image_data = None

        # 预校验页面结构：畸形页直接标记失败，不参与生成，避免中途 KeyError 中断流
        valid_pages = []
        invalid_pages = []
        for page in pages:
            validation_error = self._validate_page(page)
            if validation_error:
                invalid_pages.append((page, validation_error))
            else:
                valid_pages.append(page)

        # 压缩用户上传的参考图到200KB以内（减少内存和传输开销）
        compressed_user_images = None
        if user_images:
            compressed_user_images = [compress_image(img, max_size_kb=200) for img in user_images]

        # 初始化任务状态（带容量上限）。持有局部引用，
        # 即使状态被容量淘汰也不影响本次生成流程。
        task_state = {
            "pages": pages,
            "generated": {},
            "failed": {},
            "cover_image": None,
            "full_outline": full_outline,
            "user_images": compressed_user_images,
            "user_topic": user_topic,
            "style_prompt": style_prompt
        }
        self._set_task_state(task_id, task_state)

        try:
            # 对畸形页发出结构化 error 事件，而不是抛出中断整条流
            for page, validation_error in invalid_pages:
                failed_pages.append(page)
                bad_index = self._page_index(page)
                task_state["failed"][bad_index] = validation_error
                yield {
                    "event": "error",
                    "data": {
                        "index": bad_index,
                        "status": "error",
                        "message": validation_error,
                        "retryable": False,
                        "phase": "validate"
                    }
                }

            # ==================== 第一阶段：生成封面 ====================
            cover_page = None
            other_pages = []

            for page in valid_pages:
                if page.get("type") == "cover":
                    cover_page = page
                else:
                    other_pages.append(page)

            # 如果没有封面，使用第一页作为封面
            if cover_page is None and len(valid_pages) > 0:
                cover_page = valid_pages[0]
                other_pages = valid_pages[1:]

            if cover_page:
                # 发送封面生成进度
                yield {
                    "event": "progress",
                    "data": {
                        "index": cover_page.get("index"),
                        "status": "generating",
                        "message": "正在生成封面...",
                        "current": 1,
                        "total": total,
                        "phase": "cover"
                    }
                }

                # 生成封面（使用用户上传的图片作为参考）
                index, success, filename, error = self._generate_single_image(
                    cover_page, task_id, reference_image=None, full_outline=full_outline,
                    user_images=compressed_user_images, user_topic=user_topic,
                    record_id=record_id, total_count=total,
                    style_prompt=style_prompt
                )

                if success:
                    self._remember_generated(generated_images, index, filename, total)
                    task_state["generated"][index] = filename

                    # 读取封面图片作为参考，并立即压缩到200KB以内
                    cover_path = os.path.join(task_dir, filename)
                    with open(cover_path, "rb") as f:
                        cover_image_data = f.read()

                    # 压缩封面图（减少内存占用和后续传输开销）
                    cover_image_data = compress_image(cover_image_data, max_size_kb=200)
                    task_state["cover_image"] = cover_image_data

                    yield {
                        "event": "complete",
                        "data": {
                            "index": index,
                            "status": "done",
                            "image_url": f"/api/images/{task_id}/{filename}",
                            "phase": "cover"
                        }
                    }
                else:
                    failed_pages.append(cover_page)
                    task_state["failed"][index] = error

                    yield {
                        "event": "error",
                        "data": {
                            "index": index,
                            "status": "error",
                            "message": error,
                            "retryable": True,
                            "phase": "cover"
                        }
                    }

            # ==================== 第二阶段：生成其他页面 ====================
            if other_pages:
                high_concurrency = self.worker_count > 1

                if high_concurrency:
                    # 高并发模式：并行生成
                    yield {
                        "event": "progress",
                        "data": {
                            "status": "batch_start",
                            "message": f"开始并发生成 {len(other_pages)} 页内容...",
                            "current": self._count_generated(generated_images),
                            "total": total,
                            "phase": "content"
                        }
                    }

                    # 使用线程池并发生成
                    with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
                        try:
                            # 提交所有任务
                            future_to_page = {
                                executor.submit(
                                    self._generate_single_image,
                                    page,
                                    task_id,
                                    cover_image_data,  # 使用封面作为参考
                                    0,  # retry_count
                                    full_outline,  # 传入完整大纲
                                    compressed_user_images,  # 用户上传的参考图片（已压缩）
                                    user_topic,  # 用户原始输入
                                    record_id,
                                    total,
                                    style_prompt=style_prompt  # 风格模板描述，保持整套图一致
                                ): page
                                for page in other_pages
                            }

                            # 发送每个页面的进度
                            for page in other_pages:
                                yield {
                                    "event": "progress",
                                    "data": {
                                        "index": page.get("index"),
                                        "status": "generating",
                                        "current": self._count_generated(generated_images) + 1,
                                        "total": total,
                                        "phase": "content"
                                    }
                                }

                            # 收集结果
                            for future in as_completed(future_to_page):
                                page = future_to_page[future]
                                try:
                                    index, success, filename, error = future.result()

                                    if success:
                                        self._remember_generated(generated_images, index, filename, total)
                                        task_state["generated"][index] = filename

                                        yield {
                                            "event": "complete",
                                            "data": {
                                                "index": index,
                                                "status": "done",
                                                "image_url": f"/api/images/{task_id}/{filename}",
                                                "phase": "content"
                                            }
                                        }
                                    else:
                                        failed_pages.append(page)
                                        task_state["failed"][index] = error

                                        yield {
                                            "event": "error",
                                            "data": {
                                                "index": index,
                                                "status": "error",
                                                "message": error,
                                                "retryable": True,
                                                "phase": "content"
                                            }
                                        }

                                except Exception as e:
                                    failed_pages.append(page)
                                    error_msg = str(e)
                                    bad_index = self._page_index(page)
                                    task_state["failed"][bad_index] = error_msg

                                    yield {
                                        "event": "error",
                                        "data": {
                                            "index": bad_index,
                                            "status": "error",
                                            "message": error_msg,
                                            "retryable": True,
                                            "phase": "content"
                                        }
                                    }
                        except GeneratorExit:
                            # 客户端断开（SSE 断连）：取消尚未开始的任务，
                            # 避免线程池退出时把剩余生成任务全部跑完（白耗上游配额）
                            executor.shutdown(wait=False, cancel_futures=True)
                            raise
                else:
                    # 顺序模式：逐个生成
                    yield {
                        "event": "progress",
                        "data": {
                            "status": "batch_start",
                            "message": f"开始顺序生成 {len(other_pages)} 页内容...",
                            "current": self._count_generated(generated_images),
                            "total": total,
                            "phase": "content"
                        }
                    }

                    for page in other_pages:
                        # 发送生成进度
                        yield {
                            "event": "progress",
                            "data": {
                                "index": page.get("index"),
                                "status": "generating",
                                "current": self._count_generated(generated_images) + 1,
                                "total": total,
                                "phase": "content"
                            }
                        }

                        # 生成单张图片
                        index, success, filename, error = self._generate_single_image(
                            page,
                            task_id,
                            cover_image_data,
                            0,
                            full_outline,
                            compressed_user_images,
                            user_topic,
                            record_id,
                            total,
                            style_prompt=style_prompt
                        )

                        if success:
                            self._remember_generated(generated_images, index, filename, total)
                            task_state["generated"][index] = filename

                            yield {
                                "event": "complete",
                                "data": {
                                    "index": index,
                                    "status": "done",
                                    "image_url": f"/api/images/{task_id}/{filename}",
                                    "phase": "content"
                                }
                            }
                        else:
                            failed_pages.append(page)
                            task_state["failed"][index] = error

                            yield {
                                "event": "error",
                                "data": {
                                    "index": index,
                                    "status": "error",
                                    "message": error,
                                    "retryable": True,
                                    "phase": "content"
                                }
                            }

            # ==================== 完成 ====================
            yield {
                "event": "finish",
                "data": {
                    "success": len(failed_pages) == 0,
                    "task_id": task_id,
                    "images": generated_images,
                    "total": total,
                    "completed": self._count_generated(generated_images),
                    "failed": len(failed_pages),
                    "failed_indices": [self._page_index(p) for p in failed_pages]
                }
            }
        finally:
            # 流结束（正常完成/异常/客户端断开）后释放封面图和用户参考图，
            # 避免大对象在进程级单例中长期驻留导致内存泄漏
            self._release_task_heavy_data(task_id)

    def get_cached_generation_events(self, record_id: str, pages: list) -> List[Dict[str, Any]]:
        record = self.history_service.get_record(record_id, sync_images=True)
        if not record:
            return []

        images = record.get("images") or {}
        task_id = images.get("task_id")
        generated = images.get("generated") or []
        if not task_id or not HistoryImageMerger.has_images(generated):
            return []

        total = len(pages)
        completed = 0
        failed_indices = []
        events: List[Dict[str, Any]] = []

        for page in pages:
            index = page.get("index")
            filename = generated[index] if isinstance(index, int) and 0 <= index < len(generated) else ""
            if filename:
                completed += 1
                events.append({
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}",
                        "phase": "cached",
                        "cached": True,
                    }
                })
            else:
                failed_indices.append(index)
                events.append({
                    "event": "error",
                    "data": {
                        "index": index,
                        "status": "error",
                        "message": "历史记录中缺少该页图片，可手动补全",
                        "retryable": True,
                        "phase": "cached",
                        "cached": True,
                    }
                })

        events.append({
            "event": "finish",
            "data": {
                "success": len(failed_indices) == 0,
                "task_id": task_id,
                "images": generated,
                "total": total,
                "completed": completed,
                "failed": len(failed_indices),
                "failed_indices": failed_indices,
                "cached": True,
            }
        })
        return events

    def _resolve_cover_filename(self, pages: Optional[List[Dict]], record_id: Optional[str] = None) -> str:
        """
        推导封面图文件名（用于任务状态被淘汰后从磁盘回退加载封面参考图）。

        与生成流程选封面的逻辑一致：优先取 type=="cover" 的页，
        没有封面页时回退第一页；pages 不可用且提供了 record_id 时
        从历史记录读取页面；页面信息完全不可用时回退 "0.png"。
        """
        if not pages and record_id:
            try:
                record = self.history_service.get_record(record_id)
                if record:
                    pages = record.get("outline", {}).get("pages", [])
            except Exception as e:
                logger.warning(f"读取历史记录推导封面文件名失败，回退默认: {e}")
        if pages:
            cover_page = next(
                (p for p in pages if isinstance(p, dict) and p.get("type") == "cover"),
                None,
            )
            if cover_page is None:
                cover_page = pages[0]
            index = self._page_index(cover_page)
            if index >= 0:
                return f"{index}.png"
        return "0.png"

    def retry_single_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = "",
        record_id: Optional[str] = None,
        style_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        重试生成单张图片

        Args:
            task_id: 任务ID
            page: 页面数据
            use_reference: 是否使用封面作为参考
            full_outline: 完整大纲文本（从前端传入）
            user_topic: 用户原始输入（从前端传入）
            style_prompt: 风格模板的风格描述（可选，缺省时回退任务状态中的值）

        Returns:
            生成结果
        """
        # 防止 task_id 路径遍历写入
        validate_safe_id(task_id, "task_id")

        task_dir = os.path.join(self.history_root_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)

        reference_image = None
        user_images = None
        state_pages = None
        total_count = None

        # 首先尝试从任务状态中获取上下文。统一在锁内用 get 取引用，
        # 避免与容量淘汰/清理并发时 check-then-use 竞态导致 KeyError
        with self._task_states_lock:
            task_state = self._task_states.get(task_id)
            if task_state:
                if use_reference:
                    reference_image = task_state.get("cover_image")
                # 如果没有传入上下文，则使用任务状态中的
                if not full_outline:
                    full_outline = task_state.get("full_outline", "")
                if not user_topic:
                    user_topic = task_state.get("user_topic", "")
                if not style_prompt:
                    style_prompt = task_state.get("style_prompt", "")
                user_images = task_state.get("user_images")
                state_pages = task_state.get("pages")
                total_count = len(state_pages or [])

        # 如果任务状态中没有封面图，尝试从文件系统加载
        # （封面文件名按 type=="cover" 的页 index 推导，不硬编码 0.png）
        if use_reference and reference_image is None:
            cover_path = os.path.join(
                task_dir, self._resolve_cover_filename(state_pages, record_id)
            )
            if os.path.exists(cover_path):
                with open(cover_path, "rb") as f:
                    cover_data = f.read()
                # 压缩封面图到 200KB
                reference_image = compress_image(cover_data, max_size_kb=200)

        # 单张重试/重新生成：追加质量反馈提示做轻量 prompt 变异，
        # 避免用完全相同的 prompt 重蹈上一次的文字/排版问题
        index, success, filename, error = self._generate_single_image(
            page,
            task_id,
            reference_image,
            0,
            full_outline,
            user_images,
            user_topic,
            record_id,
            total_count,
            style_prompt=style_prompt,
            retry_hint=True
        )

        if success:
            # 锁内用 get 取引用后再更新，避免状态被淘汰时 KeyError
            with self._task_states_lock:
                task_state = self._task_states.get(task_id)
                if task_state:
                    task_state["generated"][index] = filename
                    task_state["failed"].pop(index, None)

            return {
                "success": True,
                "index": index,
                "image_url": f"/api/images/{task_id}/{filename}"
            }
        else:
            return {
                "success": False,
                "index": index,
                "error": error,
                "retryable": True
            }

    def retry_failed_images(
        self,
        task_id: str,
        pages: List[Dict],
        record_id: Optional[str] = None,
        style_prompt: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """
        批量重试失败的图片

        先做参数校验再返回内部生成器，保证非法 task_id 在进入 SSE 流
        之前就抛错（路由层可正常返回 400，而不是流中断）。

        Args:
            task_id: 任务ID
            pages: 需要重试的页面列表
            style_prompt: 风格模板的风格描述（可选，缺省时回退任务状态中的值）

        Yields:
            进度事件
        """
        # 防止 task_id / record_id 路径遍历写入
        validate_safe_id(task_id, "task_id")
        if record_id:
            validate_safe_id(record_id, "record_id")

        return self._retry_failed_images_stream(
            task_id, pages, record_id=record_id, style_prompt=style_prompt
        )

    def _retry_failed_images_stream(
        self,
        task_id: str,
        pages: List[Dict],
        record_id: Optional[str] = None,
        style_prompt: str = ""
    ) -> Generator[Dict[str, Any], None, None]:
        """retry_failed_images 的内部生成器实现（参数校验已在外层完成）。"""
        task_dir = os.path.join(self.history_root_dir, task_id)
        os.makedirs(task_dir, exist_ok=True)

        # 获取参考图和上下文。统一在锁内用 get 取引用，
        # 避免与容量淘汰/清理并发时 check-then-use 竞态导致 KeyError
        reference_image = None
        user_images = None
        user_topic = ""
        full_outline = ""
        state_pages = None
        total_count = None
        with self._task_states_lock:
            task_state = self._task_states.get(task_id)
            if task_state:
                reference_image = task_state.get("cover_image")
                user_images = task_state.get("user_images")
                user_topic = task_state.get("user_topic", "")
                full_outline = task_state.get("full_outline", "")
                if not style_prompt:
                    style_prompt = task_state.get("style_prompt", "")
                state_pages = task_state.get("pages")
                total_count = len(state_pages or [])

        # 任务状态中没有封面图时从磁盘回退加载
        # （封面文件名按 type=="cover" 的页 index 推导，不硬编码 0.png）
        if reference_image is None:
            cover_path = os.path.join(
                task_dir, self._resolve_cover_filename(state_pages, record_id)
            )
            if os.path.exists(cover_path):
                with open(cover_path, "rb") as f:
                    reference_image = compress_image(f.read(), max_size_kb=200)

        total = len(pages)
        success_count = 0
        failed_count = 0

        yield {
            "event": "retry_start",
            "data": {
                "total": total,
                "message": f"开始重试 {total} 张失败的图片"
            }
        }

        if record_id:
            record = self.history_service.get_record(record_id)
            if record:
                total_count = total_count or len(record.get("outline", {}).get("pages", []))

        def handle_result(page: Dict, result: Tuple[int, bool, Optional[str], Optional[str]]):
            nonlocal success_count, failed_count
            index, success, filename, error = result
            if success:
                success_count += 1
                # 锁内用 get 取引用后再更新，避免状态被淘汰时 KeyError
                with self._task_states_lock:
                    state = self._task_states.get(task_id)
                    if state:
                        state["generated"][index] = filename
                        state["failed"].pop(index, None)
                return {
                    "event": "complete",
                    "data": {
                        "index": index,
                        "status": "done",
                        "image_url": f"/api/images/{task_id}/{filename}"
                    }
                }

            failed_count += 1
            return {
                "event": "error",
                "data": {
                    "index": index,
                    "status": "error",
                    "message": error,
                    "retryable": True
                }
            }

        if self.worker_count > 1:
            with ThreadPoolExecutor(max_workers=self.worker_count) as executor:
                try:
                    future_to_page = {
                        executor.submit(
                            self._generate_single_image,
                            page,
                            task_id,
                            reference_image,
                            0,
                            full_outline,
                            user_images,
                            user_topic,
                            record_id,
                            total_count,
                            style_prompt=style_prompt
                        ): page
                        for page in pages
                    }

                    for future in as_completed(future_to_page):
                        page = future_to_page[future]
                        try:
                            yield handle_result(page, future.result())
                        except Exception as e:
                            failed_count += 1
                            yield {
                                "event": "error",
                                "data": {
                                    "index": self._page_index(page),
                                    "status": "error",
                                    "message": str(e),
                                    "retryable": True
                                }
                            }
                except GeneratorExit:
                    # 客户端断开（SSE 断连）：取消尚未开始的任务，
                    # 避免线程池退出时把剩余重试任务全部跑完（白耗上游配额）
                    executor.shutdown(wait=False, cancel_futures=True)
                    raise
        else:
            for page in pages:
                result = self._generate_single_image(
                    page,
                    task_id,
                    reference_image,
                    0,
                    full_outline,
                    user_images,
                    user_topic,
                    record_id,
                    total_count,
                    style_prompt=style_prompt
                )
                yield handle_result(page, result)

        yield {
            "event": "retry_finish",
            "data": {
                "success": failed_count == 0,
                "total": total,
                "completed": success_count,
                "failed": failed_count
            }
        }

    def regenerate_image(
        self,
        task_id: str,
        page: Dict,
        use_reference: bool = True,
        full_outline: str = "",
        user_topic: str = "",
        record_id: Optional[str] = None,
        style_prompt: str = ""
    ) -> Dict[str, Any]:
        """
        重新生成图片（用户手动触发，即使成功的也可以重新生成）

        Args:
            task_id: 任务ID
            page: 页面数据
            use_reference: 是否使用封面作为参考
            full_outline: 完整大纲文本
            user_topic: 用户原始输入
            style_prompt: 风格模板的风格描述（可选）

        Returns:
            生成结果
        """
        return self.retry_single_image(
            task_id, page, use_reference,
            full_outline=full_outline,
            user_topic=user_topic,
            record_id=record_id,
            style_prompt=style_prompt
        )

    def get_image_path(self, task_id: str, filename: str) -> str:
        """
        获取图片完整路径

        Args:
            task_id: 任务ID
            filename: 文件名

        Returns:
            完整路径
        """
        # 防止 task_id 路径遍历
        validate_safe_id(task_id, "task_id")
        task_dir = os.path.join(self.history_root_dir, task_id)
        return os.path.join(task_dir, filename)

    def get_task_state(self, task_id: str) -> Optional[Dict]:
        """获取任务状态"""
        return self._task_states.get(task_id)

    def cleanup_task(self, task_id: str):
        """清理任务状态（释放内存）"""
        with self._task_states_lock:
            self._task_states.pop(task_id, None)


# 全局服务实例（惰性初始化，配模块级锁防止首次并发请求构造出两个实例）
_service_instance = None
_service_instance_lock = threading.Lock()

def get_image_service() -> ImageService:
    """获取全局图片生成服务实例（双检查锁定的惰性单例）"""
    global _service_instance
    if _service_instance is None:
        with _service_instance_lock:
            if _service_instance is None:
                _service_instance = ImageService()
    return _service_instance

def reset_image_service():
    """重置全局服务实例（配置更新后调用）"""
    global _service_instance
    _service_instance = None
