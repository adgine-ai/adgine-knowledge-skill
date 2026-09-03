#!/usr/bin/env python3
"""Inspect the knowledge base bound to the configured API key."""

from __future__ import annotations

import argparse
from typing import Any, Dict, Iterable, List

from _cli import format_bytes, print_json, run
from _client import emit_update_notice, request_json, wait_snapshot


ARGS = None


def _walk_tree(nodes: Iterable[Dict[str, Any]], depth: int = 0) -> Iterable[str]:
    for node in nodes:
        yield f"{'  ' * depth}- {node.get('name', '-')} [{node.get('id', '-')}]"
        children = node.get("children") or []
        if isinstance(children, list):
            yield from _walk_tree(children, depth + 1)


def main() -> int:
    global ARGS
    parser = argparse.ArgumentParser(description="查看当前 Key 绑定的 Skill 知识库")
    subparsers = parser.add_subparsers(dest="command", required=True)

    info = subparsers.add_parser("info", help="查看知识库信息")
    info.add_argument("--json", action="store_true")

    tree = subparsers.add_parser("tree", help="查看目录树")
    tree.add_argument("--json", action="store_true")

    wait = subparsers.add_parser("wait-ready", help="等待知识库快照就绪")
    wait.add_argument("--timeout", type=float, default=300.0)
    wait.add_argument("--json", action="store_true")

    ARGS = parser.parse_args()
    emit_update_notice()

    if ARGS.command == "info":
        data = request_json("GET", "")
        if ARGS.json:
            print_json(data)
        else:
            print(f"知识库：{data.get('name', '-')} ({data.get('id', '-')})")
            print(f"类型：{data.get('knowledge_base_type', '-')}")
            print(f"查询引擎：{data.get('query_engine', '-')}")
            print(f"快照状态：{data.get('snapshot_status', '-')}")
            print(
                f"文档：{data.get('document_count', 0)}/{data.get('max_documents', '-')}"
            )
            print(
                "容量："
                f"{format_bytes(data.get('total_bytes'))}/"
                f"{format_bytes(data.get('max_bytes'))}"
            )
        return 0

    if ARGS.command == "tree":
        data = request_json("GET", "/tree")
        if ARGS.json:
            print_json(data)
        else:
            nodes = data if isinstance(data, list) else []
            lines = list(_walk_tree(nodes))
            print("\n".join(lines) if lines else "目录树为空")
        return 0

    data = wait_snapshot(timeout=ARGS.timeout)
    if ARGS.json:
        print_json(data)
    else:
        print(f"快照状态：{data.get('snapshot_status', '-')}")
    return 0 if data.get("snapshot_status") == "ready" else 3


if __name__ == "__main__":
    run(main, json_requested=lambda: bool(ARGS and ARGS.json))

