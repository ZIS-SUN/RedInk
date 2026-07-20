"""
数据资产注册表：数据根目录（get_data_root()）下所有持久资产的唯一真源。

历史上"数据资产清单"分散硬编码在 backend/paths.py（播种）与
backend/services/data_admin.py（备份/导入白名单）里，两处已经漂移，
导致 idea_library/ clips/ custom_prompts/ 落盘却不进备份。本模块集中声明
每个资产的名称、类型、分类、是否进默认备份、是否首次运行播种，其他模块
一律从这里派生清单，禁止再各自硬编码。

分类语义：
- core_data: 用户核心数据。全部进默认备份；导入 v2 备份时按"注册表全量
  替换"语义处理（备份里没有的也要清空/删除，消除数据复活）。
- config_with_secrets: 含 API Key 的配置。仅 include_keys=True 时进备份；
  导入时仅当包内含有才覆盖，绝不因缺席而删除。
- runtime_derived: 运行期派生物（日志/导出产物等）。不进默认备份，
  也不参与导入替换。

新增持久化 store 时必须在 DATA_ASSETS 登记（tests/data_catalog_test.py
的注册表守卫测试会扫描 services/routes 里的数据根拼接字面量做强制检查）。
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet, Optional, Tuple

# 资产类型
KIND_DIR = "dir"
KIND_FILE = "file"

# 资产分类
CATEGORY_CORE_DATA = "core_data"
CATEGORY_CONFIG_WITH_SECRETS = "config_with_secrets"
CATEGORY_RUNTIME_DERIVED = "runtime_derived"


@dataclass(frozen=True)
class DataAsset:
    """数据根目录下的一个顶层持久资产（目录或文件）。"""

    name: str                  # 相对 data_root 的顶层名称
    kind: str                  # KIND_DIR / KIND_FILE
    category: str              # CATEGORY_*
    include_in_backup: bool    # 是否进默认备份包
    seed_on_first_run: bool    # 冻结环境首次运行是否播种
    seed_source: Optional[str] = None  # 播种来源（随包分发的示例文件名，仅配置文件用）


DATA_ASSETS: Tuple[DataAsset, ...] = (
    # ---- core_data 目录 ----
    DataAsset("history", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("brand_kits", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("content_calendar", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("analytics_data", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("idea_library", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("clips", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    DataAsset("custom_prompts", KIND_DIR, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=True),
    # ---- core_data 文件 ----
    DataAsset("publish_accounts.json", KIND_FILE, CATEGORY_CORE_DATA,
              include_in_backup=True, seed_on_first_run=False),
    # ---- config_with_secrets（仅 include_keys=True 时进备份） ----
    DataAsset("text_providers.yaml", KIND_FILE, CATEGORY_CONFIG_WITH_SECRETS,
              include_in_backup=False, seed_on_first_run=True,
              seed_source="text_providers.yaml.example"),
    DataAsset("image_providers.yaml", KIND_FILE, CATEGORY_CONFIG_WITH_SECRETS,
              include_in_backup=False, seed_on_first_run=True,
              seed_source="image_providers.yaml.example"),
    # ---- runtime_derived（不进默认备份） ----
    DataAsset("output", KIND_DIR, CATEGORY_RUNTIME_DERIVED,
              include_in_backup=False, seed_on_first_run=False),
    DataAsset("logs", KIND_DIR, CATEGORY_RUNTIME_DERIVED,
              include_in_backup=False, seed_on_first_run=False),
    DataAsset("publish_exports", KIND_DIR, CATEGORY_RUNTIME_DERIVED,
              include_in_backup=False, seed_on_first_run=False),
)

_ASSETS_BY_NAME: Dict[str, DataAsset] = {asset.name: asset for asset in DATA_ASSETS}

if len(_ASSETS_BY_NAME) != len(DATA_ASSETS):
    raise ValueError("data_catalog: DATA_ASSETS 中存在重名资产")


def get_asset(name: str) -> Optional[DataAsset]:
    """按顶层名称查资产，未注册返回 None。"""
    return _ASSETS_BY_NAME.get(name)


def is_registered(name: str) -> bool:
    return name in _ASSETS_BY_NAME


def registered_names() -> FrozenSet[str]:
    """全部已注册的顶层资产名。"""
    return frozenset(_ASSETS_BY_NAME)


def core_data_dir_names() -> Tuple[str, ...]:
    """core_data 目录名（备份白名单 + 导入全量替换范围）。"""
    return tuple(
        a.name for a in DATA_ASSETS
        if a.category == CATEGORY_CORE_DATA and a.kind == KIND_DIR
    )


def core_data_file_names() -> Tuple[str, ...]:
    """core_data 文件名（备份白名单 + 导入全量替换范围）。"""
    return tuple(
        a.name for a in DATA_ASSETS
        if a.category == CATEGORY_CORE_DATA and a.kind == KIND_FILE
    )


def config_with_secrets_file_names() -> Tuple[str, ...]:
    """含密钥的配置文件名（仅 include_keys=True 时进备份）。"""
    return tuple(
        a.name for a in DATA_ASSETS if a.category == CATEGORY_CONFIG_WITH_SECRETS
    )


def seeded_dir_names() -> Tuple[str, ...]:
    """冻结环境首次运行需要创建的目录名。"""
    return tuple(
        a.name for a in DATA_ASSETS
        if a.kind == KIND_DIR and a.seed_on_first_run
    )


def config_seed_examples() -> Dict[str, str]:
    """需要播种的配置文件名 -> 随包分发的示例文件名。"""
    return {
        a.name: a.seed_source for a in DATA_ASSETS
        if a.seed_on_first_run and a.seed_source
    }
