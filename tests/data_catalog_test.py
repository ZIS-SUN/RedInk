"""
数据资产注册表（backend/data_catalog.py）与数据根目录覆盖（REDINK_DATA_DIR）测试：

- 注册表内容：core_data / config_with_secrets / runtime_derived 分类完整且正确
- 派生视图：data_admin 备份白名单、paths 播种列表均从注册表派生（消除硬编码漂移）
- REDINK_DATA_DIR：环境变量覆盖数据根目录（含冻结环境）；非法/不可创建路径报清晰错误
- seed_user_data：播种目录/示例配置从注册表派生
- 注册表守卫：扫描 backend/services/ 与 backend/routes/ 中 get_data_root()
  拼接出现的目录/文件字面量，确保全部已注册（防止未来新增 store 再漏备份）
"""
import re
from pathlib import Path

import pytest

from backend import paths
from backend.data_catalog import (
    DATA_ASSETS,
    config_seed_examples,
    config_with_secrets_file_names,
    core_data_dir_names,
    core_data_file_names,
    get_asset,
    registered_names,
    seeded_dir_names,
)
from backend.paths import DataRootError, get_data_root, seed_user_data


PROJECT_ROOT = Path(paths.__file__).resolve().parent.parent


# ==================== 注册表内容 ====================

class TestCatalogContents:
    def test_core_data_dirs_cover_all_persistent_stores(self):
        """核心数据目录必须齐全——特别是历史上漏备份的三个 store。"""
        assert set(core_data_dir_names()) == {
            "history",
            "brand_kits",
            "content_calendar",
            "analytics_data",
            "idea_library",
            "clips",
            "custom_prompts",
        }

    def test_core_data_files_contain_publish_accounts(self):
        assert set(core_data_file_names()) == {"publish_accounts.json"}

    def test_provider_configs_are_config_with_secrets(self):
        for name in ("text_providers.yaml", "image_providers.yaml"):
            asset = get_asset(name)
            assert asset is not None, name
            assert asset.kind == "file"
            assert asset.category == "config_with_secrets"
            # 默认不进备份（仅 include_keys=True 时由 data_admin 特判带上）
            assert asset.include_in_backup is False
        assert set(config_with_secrets_file_names()) == {
            "text_providers.yaml",
            "image_providers.yaml",
        }

    def test_runtime_derived_assets_excluded_from_backup(self):
        for name in ("output", "logs", "publish_exports"):
            asset = get_asset(name)
            assert asset is not None, name
            assert asset.category == "runtime_derived"
            assert asset.include_in_backup is False

    def test_core_data_assets_all_included_in_backup(self):
        core = [a for a in DATA_ASSETS if a.category == "core_data"]
        assert core, "注册表必须包含 core_data 资产"
        for asset in core:
            assert asset.include_in_backup is True, asset.name

    def test_asset_names_unique_and_valid(self):
        names = [a.name for a in DATA_ASSETS]
        assert len(names) == len(set(names))
        for asset in DATA_ASSETS:
            assert asset.kind in ("dir", "file"), asset.name
            assert asset.category in (
                "core_data", "config_with_secrets", "runtime_derived"
            ), asset.name
            # 顶层资产名不允许路径分隔符
            assert "/" not in asset.name and "\\" not in asset.name

    def test_get_asset_unknown_returns_none(self):
        assert get_asset("no_such_asset") is None


# ==================== 派生视图（消除硬编码漂移） ====================

class TestDerivedViews:
    def test_data_admin_whitelists_derive_from_catalog(self):
        from backend.services import data_admin

        assert set(data_admin.DATA_DIRS) == set(core_data_dir_names())
        assert set(data_admin.DATA_FILES) == set(core_data_file_names())
        assert set(data_admin.CONFIG_FILES) == set(config_with_secrets_file_names())

    def test_paths_no_longer_hardcodes_asset_lists(self):
        """paths.py 的独立硬编码清单必须删除，统一从注册表派生。"""
        assert not hasattr(paths, "_DATA_DIR_NAMES")
        assert not hasattr(paths, "_CONFIG_SEEDS")

    def test_seeded_dirs_include_all_core_data_dirs(self):
        assert set(seeded_dir_names()) == {
            "history",
            "brand_kits",
            "content_calendar",
            "analytics_data",
            "idea_library",
            "clips",
            "custom_prompts",
        }

    def test_config_seed_examples_mapping(self):
        assert config_seed_examples() == {
            "text_providers.yaml": "text_providers.yaml.example",
            "image_providers.yaml": "image_providers.yaml.example",
        }


# ==================== REDINK_DATA_DIR 覆盖 ====================

class TestRedinkDataDirOverride:
    def test_env_override_takes_effect(self, monkeypatch, tmp_path):
        target = tmp_path / "custom" / "data"
        monkeypatch.setenv("REDINK_DATA_DIR", str(target))
        assert get_data_root() == target
        # 目录被自动创建
        assert target.is_dir()

    def test_env_override_wins_over_frozen_branch(self, monkeypatch, tmp_path):
        target = tmp_path / "frozen-override"
        monkeypatch.setenv("REDINK_DATA_DIR", str(target))
        monkeypatch.setattr(paths, "is_frozen", lambda: True)
        assert get_data_root() == target

    def test_unset_env_keeps_project_root(self, monkeypatch):
        monkeypatch.delenv("REDINK_DATA_DIR", raising=False)
        monkeypatch.setattr(paths, "is_frozen", lambda: False)
        assert get_data_root() == PROJECT_ROOT

    def test_blank_env_treated_as_unset(self, monkeypatch):
        monkeypatch.setenv("REDINK_DATA_DIR", "   ")
        monkeypatch.setattr(paths, "is_frozen", lambda: False)
        assert get_data_root() == PROJECT_ROOT

    def test_env_pointing_at_file_raises_clear_error(self, monkeypatch, tmp_path):
        file_path = tmp_path / "not_a_dir"
        file_path.write_text("x", encoding="utf-8")
        monkeypatch.setenv("REDINK_DATA_DIR", str(file_path))
        with pytest.raises(DataRootError) as exc_info:
            get_data_root()
        assert "REDINK_DATA_DIR" in str(exc_info.value)

    def test_env_uncreatable_path_raises_clear_error(self, monkeypatch, tmp_path):
        blocker = tmp_path / "blocker"
        blocker.write_text("x", encoding="utf-8")
        monkeypatch.setenv("REDINK_DATA_DIR", str(blocker / "sub"))
        with pytest.raises(DataRootError) as exc_info:
            get_data_root()
        assert "REDINK_DATA_DIR" in str(exc_info.value)


# ==================== seed_user_data 从注册表派生 ====================

class TestSeedUserData:
    def test_seed_creates_all_catalog_seed_dirs_and_configs(self, monkeypatch, tmp_path):
        data_root = tmp_path / "seed_root"
        monkeypatch.setenv("REDINK_DATA_DIR", str(data_root))
        monkeypatch.setattr(paths, "is_frozen", lambda: True)
        # 冻结环境的资源基准指向项目根（项目根下有 *.yaml.example）
        monkeypatch.setattr(paths, "resource_path", lambda rel: PROJECT_ROOT / rel)

        seed_user_data()

        for dir_name in seeded_dir_names():
            assert (data_root / dir_name).is_dir(), dir_name
        assert (data_root / "text_providers.yaml").is_file()
        assert (data_root / "image_providers.yaml").is_file()

    def test_seed_noop_when_not_frozen(self, monkeypatch, tmp_path):
        data_root = tmp_path / "seed_root"
        monkeypatch.setenv("REDINK_DATA_DIR", str(data_root))
        monkeypatch.setattr(paths, "is_frozen", lambda: False)

        seed_user_data()

        assert not any((data_root / d).exists() for d in seeded_dir_names())


# ==================== 注册表守卫 ====================

def _extract_data_root_literals(source: str) -> set:
    """
    提取源码中"数据根拼接"出现的路径字面量（取首段目录/文件名）：

    1. get_data_root() / "literal"
    2. get_data_root() / CONSTANT，且同文件存在 CONSTANT = "literal"
    3. VAR = get_data_root() 后出现的 VAR / "literal"
    """
    literals = set()

    for match in re.finditer(r"get_data_root\(\)\s*/\s*(['\"])([^'\"]+)\1", source):
        literals.add(match.group(2))

    for match in re.finditer(r"get_data_root\(\)\s*/\s*([A-Za-z_][A-Za-z0-9_]*)", source):
        const_name = match.group(1)
        assign = re.search(
            rf"^\s*{re.escape(const_name)}\s*=\s*(['\"])([^'\"]+)\1",
            source,
            re.MULTILINE,
        )
        if assign:
            literals.add(assign.group(2))

    for match in re.finditer(
        r"^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=\s*get_data_root\(\)\s*$",
        source,
        re.MULTILINE,
    ):
        var_name = match.group(1)
        for join in re.finditer(
            rf"\b{re.escape(var_name)}\s*/\s*(['\"])([^'\"]+)\1", source
        ):
            literals.add(join.group(2))

    return {Path(lit).parts[0] for lit in literals if lit.strip()}


class TestRegistryGuard:
    def test_all_data_root_literals_are_registered(self):
        """
        backend/services/ 与 backend/routes/ 中所有基于数据根拼接的
        目录/文件字面量都必须已在 data_catalog 注册，防止未来新增
        store 后再次漏出备份白名单。
        """
        backend_dir = PROJECT_ROOT / "backend"
        known = registered_names()
        offenders = {}

        for scan_dir in (backend_dir / "services", backend_dir / "routes"):
            for py_file in sorted(scan_dir.glob("*.py")):
                source = py_file.read_text(encoding="utf-8")
                unknown = {
                    top for top in _extract_data_root_literals(source)
                    if top not in known
                }
                if unknown:
                    offenders[py_file.name] = sorted(unknown)

        assert not offenders, (
            f"以下文件在数据根下写入了未注册的目录/文件，请在 "
            f"backend/data_catalog.py 的 DATA_ASSETS 中登记后再使用: {offenders}"
        )

    def test_guard_extractor_catches_known_patterns(self):
        """守卫的提取器本身必须能识别三种拼接写法（防止守卫失效）。"""
        sample = '\n'.join([
            'p1 = get_data_root() / "direct_dir" / "file.json"',
            "_CONST_NAME = 'const_dir'",
            "p2 = get_data_root() / _CONST_NAME / 'x'",
            "ROOT_VAR = get_data_root()",
            "p3 = ROOT_VAR / 'var_dir'",
        ])
        assert _extract_data_root_literals(sample) == {
            "direct_dir", "const_dir", "var_dir",
        }
