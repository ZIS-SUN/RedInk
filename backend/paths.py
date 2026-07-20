"""
路径中心化模块

统一提供三类路径，兼容开发/网页模式与 PyInstaller 冻结（打包成 .app）环境：

- get_data_root(): 可写目录，存放配置（text_providers.yaml / image_providers.yaml）
  与用户数据（history/ brand_kits/ content_calendar/ analytics_data/）。
  非冻结环境下即项目根目录，保持现有行为；冻结环境下为
  ~/Library/Application Support/RedInk。
- resource_path(rel): 只读资源（backend/prompts/*.txt、frontend/dist、
  *.yaml.example），随包分发。非冻结环境下以项目根目录为基准；
  冻结环境下以 PyInstaller 解包目录（sys._MEIPASS）为基准。
- seed_user_data(): 冻结环境首次运行时，把示例配置拷贝到可写目录并
  创建各数据目录；非冻结环境下为空操作。
"""

import shutil
import sys
from pathlib import Path

# get_data_root() 下需要保证存在的数据目录
_DATA_DIR_NAMES = ("history", "brand_kits", "content_calendar", "analytics_data")

# 配置文件名 -> 随包分发的示例文件名
_CONFIG_SEEDS = {
    "text_providers.yaml": "text_providers.yaml.example",
    "image_providers.yaml": "image_providers.yaml.example",
}


def is_frozen() -> bool:
    """是否运行在 PyInstaller 冻结环境中。"""
    return bool(getattr(sys, "frozen", False))


def get_data_root() -> Path:
    """
    可写数据根目录：配置 + 用户数据。

    非冻结环境返回项目根目录（保持现有行为）；
    冻结环境返回 ~/Library/Application Support/RedInk。
    """
    if is_frozen():
        root = Path.home() / "Library" / "Application Support" / "RedInk"
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

    - 若 get_data_root() 下缺少 text_providers.yaml / image_providers.yaml，
      从随包分发的 *.yaml.example 拷贝一份作为初始配置；
    - 确保 history/ brand_kits/ content_calendar/ analytics_data/ 存在。

    非冻结环境下为空操作（保持现有行为）。
    """
    if not is_frozen():
        return

    data_root = get_data_root()

    for config_name, example_name in _CONFIG_SEEDS.items():
        target = data_root / config_name
        if target.exists():
            continue
        source = resource_path(example_name)
        if source.exists():
            shutil.copyfile(source, target)

    for dir_name in _DATA_DIR_NAMES:
        (data_root / dir_name).mkdir(parents=True, exist_ok=True)
