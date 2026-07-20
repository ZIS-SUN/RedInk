"""
路径中心化模块

统一提供三类路径，兼容开发/网页模式与 PyInstaller 冻结（打包成 .app）环境：

- get_data_root(): 可写目录，存放配置（text_providers.yaml / image_providers.yaml）
  与用户数据（数据资产清单见 backend/data_catalog.py）。
  环境变量 REDINK_DATA_DIR 非空时优先生效（冻结/非冻结均适用），
  指向非法或不可创建的路径时抛 DataRootError；
  未设置时非冻结环境返回项目根目录（保持现有行为），冻结环境按平台分支：
  macOS 为 ~/Library/Application Support/RedInk，
  Windows 为 %APPDATA%/RedInk（无 APPDATA 时回退 ~/AppData/Roaming/RedInk），
  其他平台（Linux 等）为 $XDG_DATA_HOME/RedInk（无 XDG_DATA_HOME 时回退
  ~/.local/share/RedInk）。
- resource_path(rel): 只读资源（backend/prompts/*.txt、frontend/dist、
  *.yaml.example），随包分发。非冻结环境下以项目根目录为基准；
  冻结环境下以 PyInstaller 解包目录（sys._MEIPASS）为基准。
- seed_user_data(): 冻结环境首次运行时，把示例配置拷贝到可写目录并
  创建各数据目录（清单从 backend/data_catalog.py 派生）；
  非冻结环境下为空操作。
"""

import os
import shutil
import sys
from pathlib import Path
from typing import Optional

from backend.data_catalog import config_seed_examples, seeded_dir_names

# 数据根目录覆盖用环境变量
DATA_DIR_ENV_VAR = "REDINK_DATA_DIR"


class DataRootError(RuntimeError):
    """REDINK_DATA_DIR 指向非法或不可创建的路径时抛出。"""


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结环境中。"""
    return bool(getattr(sys, "frozen", False))


def _frozen_data_root() -> Path:
    """冻结环境下的可写数据根目录（不含 mkdir），按平台分支。"""
    if sys.platform == "darwin":
        # macOS 路径必须与历史行为逐字节一致
        return Path.home() / "Library" / "Application Support" / "RedInk"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        base = Path(appdata) if appdata else Path.home() / "AppData" / "Roaming"
        return base / "RedInk"
    # Linux 及其他类 Unix：遵循 XDG Base Directory 规范
    xdg_data_home = os.environ.get("XDG_DATA_HOME")
    base = Path(xdg_data_home) if xdg_data_home else Path.home() / ".local" / "share"
    return base / "RedInk"


def _env_data_root() -> Optional[Path]:
    """
    解析 REDINK_DATA_DIR 环境变量。

    Returns:
        未设置或为空白时返回 None；否则返回已创建好的目录路径。

    Raises:
        DataRootError: 路径无法创建（已存在同名文件、父级不可写等）
            或创建后不是目录时抛出，附带清晰的排查信息。
    """
    raw = os.environ.get(DATA_DIR_ENV_VAR)
    if raw is None or not raw.strip():
        return None

    root = Path(raw.strip()).expanduser()
    try:
        root.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise DataRootError(
            f"环境变量 {DATA_DIR_ENV_VAR} 指向的数据目录无法创建: "
            f"{raw!r}（{e}）。请确认该路径可写，或改用其他目录。"
        ) from e
    if not root.is_dir():
        raise DataRootError(
            f"环境变量 {DATA_DIR_ENV_VAR} 指向的路径不是目录: {raw!r}。"
            "请指向一个目录路径。"
        )
    return root


def get_data_root() -> Path:
    """
    可写数据根目录：配置 + 用户数据。

    优先级：REDINK_DATA_DIR 环境变量（非空时，冻结/非冻结均生效）>
    冻结环境平台分支（见 _frozen_data_root()）> 非冻结环境项目根目录
    （保持现有行为）。
    """
    env_root = _env_data_root()
    if env_root is not None:
        return env_root

    if is_frozen():
        root = _frozen_data_root()
    else:
        root = Path(__file__).resolve().parent.parent  # 项目根目录
    root.mkdir(parents=True, exist_ok=True)
    return root


def resource_path(rel: str) -> Path:
    """
    只读资源路径：随包分发的资源（prompts、frontend/dist、*.example）。

    非冻结环境以项目根目录为基准；冻结环境以 sys._MEIPASS 为基准。
    """
    if is_frozen():
        base = Path(getattr(sys, "_MEIPASS"))
    else:
        base = Path(__file__).resolve().parent.parent
    return base / rel


def seed_user_data() -> None:
    """
    冻结环境首次运行时初始化可写目录：

    - 若 get_data_root() 下缺少需播种的配置文件（text_providers.yaml /
      image_providers.yaml），从随包分发的 *.yaml.example 拷贝一份作为初始配置；
    - 确保注册表中标记播种的数据目录存在。

    播种清单统一从 backend/data_catalog.py 派生。
    非冻结环境下为空操作（保持现有行为）。
    """
    if not is_frozen():
        return

    data_root = get_data_root()

    for config_name, example_name in config_seed_examples().items():
        target = data_root / config_name
        if target.exists():
            continue
        source = resource_path(example_name)
        if source.exists():
            shutil.copyfile(source, target)

    for dir_name in seeded_dir_names():
        (data_root / dir_name).mkdir(parents=True, exist_ok=True)
