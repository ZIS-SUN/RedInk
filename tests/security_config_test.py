"""启动期安全校验（fail-closed）测试 —— W0-B

规则：监听非环回地址（不是 127.0.0.1 / ::1 / localhost）且未设置
REDINK_ACCESS_TOKEN 时，除非显式设置 REDINK_ALLOW_INSECURE=1，
否则拒绝启动（SystemExit）。环回监听行为完全不变。
"""
import pytest

from backend.app import create_app, validate_security_config
from backend.config import Config


# ==================== 纯函数：validate_security_config ====================

def test_nonloopback_without_token_refuses_to_start():
    """非环回 + 无令牌 + 无豁免 → 拒绝启动，错误信息给出三种解决办法"""
    with pytest.raises(SystemExit) as exc_info:
        validate_security_config("0.0.0.0", "", False)

    message = str(exc_info.value)
    # 三种解决办法都要出现在错误说明里
    assert "REDINK_ACCESS_TOKEN" in message
    assert "127.0.0.1" in message
    assert "REDINK_ALLOW_INSECURE=1" in message


def test_nonloopback_with_token_passes():
    """非环回 + 有令牌 → 通过，无警告"""
    assert validate_security_config("0.0.0.0", "some-strong-token", False) is None


def test_nonloopback_with_explicit_insecure_passes_with_warning():
    """非环回 + REDINK_ALLOW_INSECURE=1 → 通过，但返回醒目警告文本"""
    warning = validate_security_config("0.0.0.0", "", True)

    assert warning is not None
    assert "REDINK_ALLOW_INSECURE" in warning


def test_loopback_without_token_passes():
    """环回 + 无令牌 → 通过（本机行为完全不变，无警告）"""
    assert validate_security_config("127.0.0.1", "", False) is None


@pytest.mark.parametrize("host", ["127.0.0.1", "::1", "localhost", "LOCALHOST"])
def test_loopback_variants_pass(host):
    assert validate_security_config(host, "", False) is None


def test_whitespace_token_counts_as_missing():
    """令牌只有空白字符视同未设置，仍然拒绝启动"""
    with pytest.raises(SystemExit):
        validate_security_config("0.0.0.0", "   ", False)


# ==================== 接线：create_app 启动期执行校验 ====================

def _clear_security_env(monkeypatch):
    monkeypatch.delenv("REDINK_ACCESS_TOKEN", raising=False)
    monkeypatch.delenv("REDINK_ALLOW_INSECURE", raising=False)


def test_create_app_refuses_nonloopback_without_token(monkeypatch):
    monkeypatch.setattr(Config, "HOST", "0.0.0.0")
    _clear_security_env(monkeypatch)

    with pytest.raises(SystemExit):
        create_app()


def test_create_app_nonloopback_with_token_starts(monkeypatch):
    monkeypatch.setattr(Config, "HOST", "0.0.0.0")
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("REDINK_ACCESS_TOKEN", "test-token")

    assert create_app() is not None


def test_create_app_nonloopback_with_allow_insecure_starts(monkeypatch):
    monkeypatch.setattr(Config, "HOST", "0.0.0.0")
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("REDINK_ALLOW_INSECURE", "1")

    assert create_app() is not None


def test_create_app_allow_insecure_requires_exact_value_1(monkeypatch):
    """安全豁免开关必须严格等于 "1"，拼写错误一律 fail-closed"""
    monkeypatch.setattr(Config, "HOST", "0.0.0.0")
    _clear_security_env(monkeypatch)
    monkeypatch.setenv("REDINK_ALLOW_INSECURE", "true")

    with pytest.raises(SystemExit):
        create_app()


def test_create_app_loopback_without_token_starts(monkeypatch):
    monkeypatch.setattr(Config, "HOST", "127.0.0.1")
    _clear_security_env(monkeypatch)

    assert create_app() is not None
