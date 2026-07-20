"""图片生成本进程限流器。"""
import threading
import time
from contextlib import contextmanager


class ImageQueueTimeoutError(TimeoutError):
    """等待图片生成并发额度超时（本机排队饱和，而非网络问题）。

    继承 TimeoutError 保持既有 except TimeoutError 调用方兼容；
    消息以"图片生成排队超时"开头，backend.errors 据此归类为
    QUEUE_TIMEOUT（而不是误导用户查网络的 NETWORK_TIMEOUT）。
    """


class ImageRateLimiter:
    """限制同一进程内图片上游请求的并发数和启动间隔。"""

    # 等待并发额度的默认超时（秒）。超时抛出 ImageQueueTimeoutError
    # （backend.errors 分类为可重试的 QUEUE_TIMEOUT），避免请求无限期阻塞。
    DEFAULT_ACQUIRE_TIMEOUT_SECONDS = 600.0

    def __init__(
        self,
        max_concurrent: int = 1,
        interval_seconds: float = 3.0,
        acquire_timeout_seconds: float = None,
    ):
        self.max_concurrent = max(1, int(max_concurrent or 1))
        self.interval_seconds = max(0.0, float(interval_seconds or 0))
        self.acquire_timeout_seconds = float(
            acquire_timeout_seconds
            if acquire_timeout_seconds is not None
            else self.DEFAULT_ACQUIRE_TIMEOUT_SECONDS
        )
        self._semaphore = threading.Semaphore(self.max_concurrent)
        self._lock = threading.Lock()
        self._last_start_at = 0.0

    @contextmanager
    def acquire(self, timeout: float = None):
        """
        获取一个并发额度（上下文管理器）。

        Args:
            timeout: 等待额度的超时秒数；缺省使用实例的 acquire_timeout_seconds

        Raises:
            ImageQueueTimeoutError: 等待超时（本机排队饱和，可重试）
        """
        wait_timeout = self.acquire_timeout_seconds if timeout is None else float(timeout)
        if not self._semaphore.acquire(timeout=wait_timeout):
            raise ImageQueueTimeoutError(
                f"图片生成排队超时：等待并发额度超过 {wait_timeout:.0f} 秒"
                "（本机排队任务过多），请减少页数或稍后重试"
            )
        try:
            with self._lock:
                now = time.monotonic()
                wait_for = self._last_start_at + self.interval_seconds - now
                if wait_for > 0:
                    time.sleep(wait_for)
                self._last_start_at = time.monotonic()
            yield
        finally:
            self._semaphore.release()
