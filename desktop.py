"""RedInk 桌面入口。

用 pywebview 打开原生窗口，内部在守护线程中运行 Flask 后端。
被 PyInstaller 打包为 macOS 的 RedInk.app（见 redink.spec）。
"""

import json
import os
import socket
import subprocess
import sys
import threading
import time
import traceback
import urllib.request
from pathlib import Path

PREFERRED_PORT = 12398
HEALTH_TIMEOUT_SECONDS = 30.0

# 窗口默认与钳制范围（窗口大小记忆读取时使用）
DEFAULT_WINDOW_WIDTH = 1440
DEFAULT_WINDOW_HEIGHT = 900
MIN_WINDOW_WIDTH, MAX_WINDOW_WIDTH = 1024, 4000
MIN_WINDOW_HEIGHT, MAX_WINDOW_HEIGHT = 700, 3000
WINDOW_STATE_FILENAME = "window_state.json"

# osascript 通知文案的最大长度
NOTIFY_MAX_LENGTH = 200

# 桌面 app 面向国内直连（siliconflow / 用户中转站），
# 清掉可能从 shell / launchd 继承来的代理变量，避免 requests 走坏代理。
_PROXY_ENV_VARS = (
    "HTTP_PROXY",
    "HTTPS_PROXY",
    "ALL_PROXY",
    "FTP_PROXY",
    "SOCKS_PROXY",
    "NO_PROXY",
)


def _strip_proxy_env() -> None:
    for name in _PROXY_ENV_VARS:
        os.environ.pop(name, None)
        os.environ.pop(name.lower(), None)


# ==================== macOS 原生通知 ====================


def _escape_osascript(text: str) -> str:
    """
    清洗要嵌入 osascript 双引号字符串的文本：

    去掉双引号与反斜杠（防 AppleScript 注入），再截断到 NOTIFY_MAX_LENGTH。
    """
    cleaned = str(text).replace("\\", "").replace('"', "")
    return cleaned[:NOTIFY_MAX_LENGTH]


class DesktopApi:
    """暴露给前端的 pywebview js_api（window.pywebview.api.*）。"""

    def notify(self, title: str, message: str) -> bool:
        """发送 macOS 系统通知；任何异常兜底返回 False。"""
        try:
            script = (
                f'display notification "{_escape_osascript(message)}" '
                f'with title "{_escape_osascript(title)}"'
            )
            result = subprocess.run(
                ["osascript", "-e", script],
                capture_output=True,
                timeout=5,
            )
            return result.returncode == 0
        except Exception:
            return False


# ==================== 窗口大小/位置记忆 ====================


def _window_state_path() -> Path:
    from backend.paths import get_data_root

    return get_data_root() / WINDOW_STATE_FILENAME


def _as_int(value: object) -> int | None:
    """bool 是 int 的子类，显式排除；其余数值转 int，非数值返回 None。"""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return None
    return int(value)


def _load_window_state(path: Path | None = None) -> dict:
    """
    读取窗口状态。缺失/损坏时返回默认尺寸（不含 x/y）；
    width/height 钳制到合法范围；x/y 仅在两者都是数值时保留。
    """
    state = {"width": DEFAULT_WINDOW_WIDTH, "height": DEFAULT_WINDOW_HEIGHT}
    try:
        raw = json.loads((path or _window_state_path()).read_text("utf-8"))
    except Exception:
        return state
    if not isinstance(raw, dict):
        return state

    width = _as_int(raw.get("width"))
    if width is not None:
        state["width"] = min(max(width, MIN_WINDOW_WIDTH), MAX_WINDOW_WIDTH)
    height = _as_int(raw.get("height"))
    if height is not None:
        state["height"] = min(max(height, MIN_WINDOW_HEIGHT), MAX_WINDOW_HEIGHT)

    x = _as_int(raw.get("x"))
    y = _as_int(raw.get("y"))
    if x is not None and y is not None:
        state["x"] = x
        state["y"] = y
    return state


def _save_window_state(state: dict, path: Path | None = None) -> None:
    """
    原子写入窗口状态（临时文件 + os.replace），异常静默。

    None / 非数值字段跳过；width/height 缺失时整体放弃保存。
    """
    try:
        data = {}
        for key in ("width", "height", "x", "y"):
            value = _as_int(state.get(key))
            if value is not None:
                data[key] = value
        if "width" not in data or "height" not in data:
            return
        target = path or _window_state_path()
        tmp = target.with_name(target.name + ".tmp")
        tmp.write_text(json.dumps(data, ensure_ascii=False), "utf-8")
        os.replace(tmp, target)
    except Exception:
        pass


def _port_is_free(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(("127.0.0.1", port))
            return True
        except OSError:
            return False


def _pick_port() -> int:
    if _port_is_free(PREFERRED_PORT):
        return PREFERRED_PORT
    # 首选端口被占用，让系统分配一个空闲端口
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return sock.getsockname()[1]


def _start_backend(port: int) -> threading.Thread:
    from backend.app import create_app

    app = create_app()

    def run() -> None:
        try:
            app.run(
                host="127.0.0.1",
                port=port,
                debug=False,
                use_reloader=False,
                threaded=True,
            )
        except Exception:
            traceback.print_exc()

    thread = threading.Thread(target=run, name="redink-backend", daemon=True)
    thread.start()
    return thread


def _wait_for_backend(port: int, timeout: float = HEALTH_TIMEOUT_SECONDS) -> None:
    url = f"http://127.0.0.1:{port}/api/health"
    deadline = time.monotonic() + timeout
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=2) as response:
                if response.status == 200:
                    return
        except Exception as exc:  # noqa: BLE001 - 启动阶段任何错误都重试
            last_error = exc
        time.sleep(0.2)
    raise RuntimeError(
        f"后端在 {timeout:.0f} 秒内未就绪（{url}）。"
        f"最后一次错误：{last_error!r}"
    )


def main() -> int:
    _strip_proxy_env()

    try:
        from backend.paths import seed_user_data

        seed_user_data()
    except Exception:
        print("[RedInk] seed_user_data 失败：", file=sys.stderr)
        traceback.print_exc()
        return 1

    port = _pick_port()
    print(f"[RedInk] 后端端口：{port}")

    try:
        _start_backend(port)
        _wait_for_backend(port)
    except Exception:
        print("[RedInk] 后端启动失败：", file=sys.stderr)
        traceback.print_exc()
        return 1

    try:
        import webview

        state = _load_window_state()
        window_kwargs = {
            "width": state["width"],
            "height": state["height"],
        }
        if "x" in state and "y" in state:
            window_kwargs["x"] = state["x"]
            window_kwargs["y"] = state["y"]

        window = webview.create_window(
            "红墨 RedInk",
            f"http://127.0.0.1:{port}",
            min_size=(1024, 700),
            js_api=DesktopApi(),
            **window_kwargs,
        )

        def _remember_window_state() -> None:
            try:
                _save_window_state(
                    {
                        "width": window.width,
                        "height": window.height,
                        "x": window.x,
                        "y": window.y,
                    }
                )
            except Exception:
                pass  # 记忆失败不影响关闭流程

        window.events.closing += _remember_window_state
        webview.start()
    except Exception:
        print("[RedInk] 窗口启动失败：", file=sys.stderr)
        traceback.print_exc()
        return 1

    # 窗口关闭后直接退出；后端线程是 daemon，会随进程结束
    return 0


if __name__ == "__main__":
    sys.exit(main())
