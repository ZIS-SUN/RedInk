#!/usr/bin/env python3
"""版本一致性检查：比对 pyproject.toml / frontend/package.json / redink.spec 三处版本号。

用法：
    uv run python scripts/check-version.py            # 仅检查三处是否一致
    uv run python scripts/check-version.py v0.2.0     # 额外断言版本等于给定 tag（v 前缀可省略）

退出码：三处不一致或与给定 tag 不符时非零退出。
backend/app.py 中硬编码的版本只做核对告警，不阻断（该文件不由本流程维护）。
"""

import json
import re
import sys
import tomllib
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent


def read_versions() -> dict[str, str]:
    versions: dict[str, str] = {}

    pyproject = tomllib.loads((PROJECT_ROOT / "pyproject.toml").read_text(encoding="utf-8"))
    versions["pyproject.toml"] = pyproject["project"]["version"]

    package_json = json.loads((PROJECT_ROOT / "frontend" / "package.json").read_text(encoding="utf-8"))
    versions["frontend/package.json"] = package_json["version"]

    spec_text = (PROJECT_ROOT / "redink.spec").read_text(encoding="utf-8")
    match = re.search(r"'CFBundleShortVersionString':\s*'([^']+)'", spec_text)
    if not match:
        print("错误：redink.spec 中未找到 CFBundleShortVersionString", file=sys.stderr)
        sys.exit(1)
    versions["redink.spec"] = match.group(1)

    return versions


def warn_app_py(expected: str) -> None:
    """backend/app.py 的硬编码版本仅告警，不作为失败条件。"""
    app_py = PROJECT_ROOT / "backend" / "app.py"
    if not app_py.is_file():
        return
    match = re.search(r'"version":\s*"([^"]+)"', app_py.read_text(encoding="utf-8"))
    if match is None:
        print("警告：backend/app.py 中未找到硬编码版本号，请人工确认", file=sys.stderr)
    elif match.group(1) != expected:
        print(
            f"警告：backend/app.py 硬编码版本为 {match.group(1)}，与 {expected} 不一致"
            "（该文件不在本检查的阻断范围内，请另行更新）",
            file=sys.stderr,
        )


def main() -> None:
    versions = read_versions()
    for source, version in versions.items():
        print(f"  {source}: {version}")

    unique = set(versions.values())
    if len(unique) != 1:
        print("错误：三处版本号不一致，请统一后再发版", file=sys.stderr)
        sys.exit(1)

    version = unique.pop()

    if len(sys.argv) > 1:
        expected = sys.argv[1].lstrip("v")
        if version != expected:
            print(
                f"错误：tag 版本 {expected} 与项目版本 {version} 不一致。"
                "请先在 pyproject.toml、frontend/package.json、redink.spec 三处 bump 版本并提交，再打 tag",
                file=sys.stderr,
            )
            sys.exit(1)
        print(f"通过：tag 版本与项目版本一致（{version}）")
    else:
        print(f"通过：三处版本号一致（{version}）")

    warn_app_py(version)


if __name__ == "__main__":
    main()
