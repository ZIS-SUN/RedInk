"""
desktop.py 纯函数测试：osascript 转义 + 窗口状态读写钳制。

import desktop 不会启动窗口（入口有 if __name__ == '__main__' 保护）。
"""
import json

import desktop
from desktop import (
    DEFAULT_WINDOW_HEIGHT,
    DEFAULT_WINDOW_WIDTH,
    MAX_WINDOW_HEIGHT,
    MAX_WINDOW_WIDTH,
    MIN_WINDOW_HEIGHT,
    MIN_WINDOW_WIDTH,
    NOTIFY_MAX_LENGTH,
    _escape_osascript,
    _load_window_state,
    _save_window_state,
)


class TestEscapeOsascript:
    def test_plain_text_unchanged(self):
        assert _escape_osascript("全部 8 张图片生成完成 ✅") == "全部 8 张图片生成完成 ✅"

    def test_strips_double_quotes_and_backslashes(self):
        assert _escape_osascript('a"b\\c"d') == "abcd"

    def test_injection_payload_neutralized(self):
        payload = '" with title "hack" & do shell script "rm -rf ~'
        assert '"' not in _escape_osascript(payload)
        assert "\\" not in _escape_osascript(payload)

    def test_truncates_to_max_length(self):
        assert len(_escape_osascript("x" * 500)) == NOTIFY_MAX_LENGTH

    def test_non_str_coerced(self):
        assert _escape_osascript(123) == "123"


class TestLoadWindowState:
    def test_missing_file_returns_default(self, tmp_path):
        state = _load_window_state(tmp_path / "nope.json")
        assert state == {"width": DEFAULT_WINDOW_WIDTH, "height": DEFAULT_WINDOW_HEIGHT}

    def test_corrupted_json_returns_default(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text("{not json", "utf-8")
        state = _load_window_state(path)
        assert state == {"width": DEFAULT_WINDOW_WIDTH, "height": DEFAULT_WINDOW_HEIGHT}

    def test_non_dict_json_returns_default(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text("[1, 2]", "utf-8")
        state = _load_window_state(path)
        assert state == {"width": DEFAULT_WINDOW_WIDTH, "height": DEFAULT_WINDOW_HEIGHT}

    def test_valid_state_roundtrip(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text(json.dumps({"width": 1600, "height": 1000, "x": 40, "y": 60}), "utf-8")
        assert _load_window_state(path) == {"width": 1600, "height": 1000, "x": 40, "y": 60}

    def test_clamps_out_of_range_size(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text(json.dumps({"width": 99999, "height": 10}), "utf-8")
        state = _load_window_state(path)
        assert state["width"] == MAX_WINDOW_WIDTH
        assert state["height"] == MIN_WINDOW_HEIGHT

        path.write_text(json.dumps({"width": 1, "height": 99999}), "utf-8")
        state = _load_window_state(path)
        assert state["width"] == MIN_WINDOW_WIDTH
        assert state["height"] == MAX_WINDOW_HEIGHT

    def test_partial_xy_dropped(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text(json.dumps({"width": 1440, "height": 900, "x": 10}), "utf-8")
        state = _load_window_state(path)
        assert "x" not in state and "y" not in state

    def test_non_numeric_values_fall_back(self, tmp_path):
        path = tmp_path / "window_state.json"
        path.write_text(
            json.dumps({"width": "wide", "height": True, "x": None, "y": 5}), "utf-8"
        )
        state = _load_window_state(path)
        assert state == {"width": DEFAULT_WINDOW_WIDTH, "height": DEFAULT_WINDOW_HEIGHT}


class TestSaveWindowState:
    def test_atomic_write_and_load_back(self, tmp_path):
        path = tmp_path / "window_state.json"
        _save_window_state({"width": 1500, "height": 950, "x": 12, "y": 34}, path)
        assert json.loads(path.read_text("utf-8")) == {
            "width": 1500,
            "height": 950,
            "x": 12,
            "y": 34,
        }
        # 临时文件不残留
        assert not (tmp_path / "window_state.json.tmp").exists()

    def test_none_position_skipped(self, tmp_path):
        path = tmp_path / "window_state.json"
        _save_window_state({"width": 1500, "height": 950, "x": None, "y": None}, path)
        assert json.loads(path.read_text("utf-8")) == {"width": 1500, "height": 950}

    def test_missing_size_aborts_save(self, tmp_path):
        path = tmp_path / "window_state.json"
        _save_window_state({"width": None, "height": 950, "x": 1, "y": 2}, path)
        assert not path.exists()

    def test_save_exception_is_silent(self, tmp_path):
        # 目录不存在时写入失败，应静默不抛异常
        _save_window_state(
            {"width": 1500, "height": 950}, tmp_path / "no_dir" / "window_state.json"
        )

    def test_float_values_coerced_to_int(self, tmp_path):
        path = tmp_path / "window_state.json"
        _save_window_state({"width": 1500.7, "height": 950.2}, path)
        assert json.loads(path.read_text("utf-8")) == {"width": 1500, "height": 950}


def test_import_desktop_has_no_window_side_effect():
    """模块级只定义函数/常量，不应存在已创建的 webview 窗口。"""
    assert hasattr(desktop, "main")
    assert callable(desktop.DesktopApi().notify)


class TestHeadlessMode:
    def test_env_flag(self, monkeypatch):
        monkeypatch.setenv("REDINK_HEADLESS", "1")
        assert desktop._is_headless_mode([]) is True

    def test_cli_flag(self, monkeypatch):
        monkeypatch.delenv("REDINK_HEADLESS", raising=False)
        assert desktop._is_headless_mode(["--headless"]) is True

    def test_default_off(self, monkeypatch):
        monkeypatch.delenv("REDINK_HEADLESS", raising=False)
        assert desktop._is_headless_mode([]) is False


def test_wait_for_backend_bypasses_http_proxy(monkeypatch, tmp_path):
    """健康检查必须直连 127.0.0.1，不能被坏掉的 HTTP_PROXY 劫持超时。"""
    import threading

    from werkzeug.serving import make_server

    monkeypatch.setenv("REDINK_DATA_DIR", str(tmp_path / "data"))
    monkeypatch.setenv("HTTP_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("http_proxy", "http://127.0.0.1:1")
    monkeypatch.setenv("HTTPS_PROXY", "http://127.0.0.1:1")
    monkeypatch.setenv("ALL_PROXY", "http://127.0.0.1:1")

    from backend.app import create_app

    app = create_app()
    server = make_server("127.0.0.1", 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        desktop._wait_for_backend(server.server_port, timeout=10)
    finally:
        server.shutdown()
        thread.join(timeout=5)
