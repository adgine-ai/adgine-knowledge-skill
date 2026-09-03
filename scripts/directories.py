#!/usr/bin/env python3
"""Manage directories in the bound Skill knowledge base."""

from __future__ import annotations

import argparse
from typing import Any, Dict, Iterable

from _cli import print_json, run
from _client import ConfigError, emit_update_notice, request_json


ARGS = None


def _walk(nodes: Iterable[Dict[str, Any]], depth: int = 0) -> Iterable[str]:
    for node in nodes:
        details = []
        for field in ("directory_count", "document_count", "total_count"):
            if field in node:
                details.append(f"{field}={node[field]}")
        suffix = f" ({', '.join(details)})" if details else ""
        yield f"{'  ' * depth}- {node.get('name', '-')} [{node.get('id', '-')}]%s" % suffix
        children = node.get("children") or []
        if isinstance(children, list):
            yield from _walk(children, depth + 1)


def main() -> int:
    global ARGS
    parser = argparse.ArgumentParser(description="管理 Skill 知识库目录")
    subparsers = parser.add_subparsers(dest="command", required=True)

    list_parser = subparsers.add_parser("list", help="列出目录树")
    list_parser.add_argument("--json", action="store_true")

    create = subparsers.add_parser("create", help="创建目录")
    create.add_argument("--name", required=True)
    create.add_argument("--parent-id")
    create.add_argument("--json", action="store_true")

    rename = subparsers.add_parser("rename", help="重命名目录")
    rename.add_argument("directory_id")
    rename.add_argument("--name", required=True)
    rename.add_argument("--json", action="store_true")

    delete = subparsers.add_parser("delete", help="删除空目录")
    delete.add_argument("directory_id")
    delete.add_argument("--yes", action="store_true", help="确认永久删除")
    delete.add_argument("--json", action="store_true")

    ARGS = parser.parse_args()
    emit_update_notice()

    if ARGS.command == "list":
        data = request_json("GET", "/tree")
        if ARGS.json:
            print_json(data)
        else:
            nodes = data if isinstance(data, list) else []
            lines = list(_walk(nodes))
            print("\n".join(lines) if lines else "目录树为空")
        return 0

    if ARGS.command == "create":
        data = request_json(
            "POST",
            "/dirs",
            body={"name": ARGS.name, "parent_id": ARGS.parent_id},
        )
        action = "目录已创建"
    elif ARGS.command == "rename":
        data = request_json(
            "PUT", f"/dirs/{ARGS.directory_id}", body={"name": ARGS.name}
        )
        action = "目录已重命名"
    else:
        if not ARGS.yes:
            raise ConfigError("目录删除是永久操作；确认后请重新执行并添加 --yes")
        data = request_json("DELETE", f"/dirs/{ARGS.directory_id}")
        action = "空目录已永久删除"

    if ARGS.json:
        print_json({"ok": True, "action": action, "data": data})
    else:
        print(action)
        if isinstance(data, dict) and data.get("id"):
            print(f"{data.get('name', '-')} [{data['id']}]")
    return 0


if __name__ == "__main__":
    run(main, json_requested=lambda: bool(ARGS and ARGS.json))

