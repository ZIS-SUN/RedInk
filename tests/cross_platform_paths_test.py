"""
backend/paths.py 跨平台数据目录测试。

通过 monkeypatch sys.platform 与环境变量，断言冻结环境下
三平台（macOS / Windows / Linux）的数据根目录分支正确，
且 macOS 路径与历史行为逐字节一致。

只测 _frozen_data_root()（纯路径计算，无 mkdir 副作用），
get_data_root() 的冻结/非冻结开关行为由现有测试覆盖。
"""
from pathlib import Path

from backend import paths
from backend.paths import _frozen_data_root, get_data_root


HOME = Path.home()


class TestFrozenDataRootMacos:
    def test_macos_path_unchanged(self, monkeypatch):
        """macOS 路径必须与历史实现逐字节一致。"""
        monkeypatch.setattr(paths.sys, "platform", "darwin")
        assert _frozen_data_root() == HOME / "Library" / "Application Support" / "RedInk"
        assert str(_frozen_data_root()) == str(
            HOME / "Library" / "Application Support" / "RedInk"
        )

    def test_macos_ignores_appdata_and_xdg(self, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "darwin")
        monkeypatch.setenv("APPDATA", "/tmp/fake-appdata")
        monkeypatch.setenv("XDG_DATA_HOME", "/tmp/fake-xdg")
        assert _frozen_data_root() == HOME / "Library" / "Application Support" / "RedInk"


class TestFrozenDataRootWindows:
    def test_windows_uses_appdata_env(self, monkeypatch, tmp_path):
        monkeypatch.setattr(paths.sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", str(tmp_path / "Roaming"))
        assert _frozen_data_root() == tmp_path / "Roaming" / "RedInk"

    def test_windows_falls_back_without_appdata(self, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "win32")
        monkeypatch.delenv("APPDATA", raising=False)
        assert _frozen_data_root() == HOME / "AppData" / "Roaming" / "RedInk"

    def test_windows_empty_appdata_falls_back(self, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "win32")
        monkeypatch.setenv("APPDATA", "")
        assert _frozen_data_root() == HOME / "AppData" / "Roaming" / "RedInk"


class TestFrozenDataRootLinux:
    def test_linux_respects_xdg_data_home(self, monkeypatch, tmp_path):
        monkeypatch.setattr(paths.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", str(tmp_path / "xdg-data"))
        assert _frozen_data_root() == tmp_path / "xdg-data" / "RedInk"

    def test_linux_falls_back_without_xdg(self, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "linux")
        monkeypatch.delenv("XDG_DATA_HOME", raising=False)
        assert _frozen_data_root() == HOME / ".local" / "share" / "RedInk"

    def test_linux_empty_xdg_falls_back(self, monkeypatch):
        monkeypatch.setattr(paths.sys, "platform", "linux")
        monkeypatch.setenv("XDG_DATA_HOME", "")
        assert _frozen_data_root() == HOME / ".local" / "share" / "RedInk"


class TestGetDataRootDispatch:
    def test_non_frozen_returns_project_root(self, monkeypatch):
        """非冻结环境保持现有行为：项目根目录，与平台无关。"""
        monkeypatch.setattr(paths, "is_frozen", lambda: False)
        expected = Path(paths.__file__).resolve().parent.parent
        assert get_data_root() == expected

    def test_frozen_dispatches_to_platform_branch(self, monkeypatch, tmp_path):
        """冻结环境走 _frozen_data_root() 并创建目录。"""
        monkeypatch.setattr(paths, "is_frozen", lambda: True)
        target = tmp_path / "frozen-root" / "RedInk"
        monkeypatch.setattr(paths, "_frozen_data_root", lambda: target)
        assert get_data_root() == target
        assert target.is_dir()
