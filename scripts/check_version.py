#!/usr/bin/env python3
"""Check whether a newer Skill release is available."""

from __future__ import annotations

import argparse

from _cli import print_json
from _version import check_for_update


def main() -> int:
    parser = argparse.ArgumentParser(description="检查 Adgine Knowledge Skill 版本")
    parser.add_argument("--force", action="store_true", help="忽略 24 小时缓存")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    args = parser.parse_args()
    result = check_for_update(force=args.force)
    if args.json:
        print_json(result)
    elif result.get("update_available"):
        print(
            "发现新版本："
            f"{result.get('remote_version')}（当前 {result.get('local_version')}）\n"
            f"发布页：{result.get('release_url')}\n"
            "仅在用户明确要求时更新，不会自动修改本地文件。"
        )
    elif result.get("error"):
        print(f"当前版本：{result.get('local_version')}；远程版本检查暂不可用")
    elif result.get("skipped"):
        print(f"当前版本：{result.get('local_version')}；已按配置跳过远程检查")
    else:
        print(f"当前已是最新版本：{result.get('local_version')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

