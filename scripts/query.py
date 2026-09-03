#!/usr/bin/env python3
"""Start and poll Pi Agent knowledge queries."""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, Iterable

from _cli import print_json, run
from _client import (
    ConfigError,
    emit_update_notice,
    operation_id,
    request_json,
    wait_query,
)


ARGS = None


def _read_query() -> str:
    if bool(ARGS.query) == bool(ARGS.query_file):
        raise ConfigError("--query 和 --query-file 必须且只能提供一个")
    if ARGS.query_file:
        path = Path(ARGS.query_file).expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"查询文件不存在：{path}")
        try:
            value = path.read_text(encoding="utf-8").strip()
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"无法读取查询文件：{exc}") from exc
    else:
        value = ARGS.query.strip()
    if not 1 <= len(value) <= 4000:
        raise ConfigError("query 长度必须为 1-4000 个字符")
    return value


def _render(data: Dict[str, Any], operation_key: str = "") -> None:
    if operation_key:
        print(f"操作幂等键：{operation_key}")
    print(f"查询 ID：{data.get('query_id', '-')}")
    print(f"任务状态：{data.get('status', '-')}")
    if data.get("answer_status"):
        print(f"回答状态：{data.get('answer_status')}")
    if data.get("answer"):
        print("\n回答：")
        print(data["answer"])
    verified = [
        item
        for item in (data.get("citations") or [])
        if isinstance(item, dict) and item.get("verified") is True
    ]
    if verified:
        print("\n已验证证据：")
        for citation in verified:
            location = []
            if citation.get("page") is not None:
                location.append(f"page={citation['page']}")
            if citation.get("line_start") is not None:
                location.append(
                    f"lines={citation['line_start']}-{citation.get('line_end', citation['line_start'])}"
                )
            suffix = f" ({', '.join(location)})" if location else ""
            print(
                f"- {citation.get('title', '-')} "
                f"[{citation.get('document_id', '-')}]{suffix}"
            )
            if citation.get("quote"):
                print(f"  {citation['quote']}")
            if citation.get("source_url"):
                print(f"  {citation['source_url']}")
    usage = data.get("usage") or {}
    if usage:
        print(
            "\nToken："
            f"input={usage.get('input_tokens', 0)}, "
            f"output={usage.get('output_tokens', 0)}, "
            f"total={usage.get('total_tokens', 0)}"
        )
    if data.get("total_cost_usd") not in {None, ""}:
        print(f"费用：${data.get('total_cost_usd')}")
    if data.get("error_message"):
        print(f"错误：{data['error_message']}")


def main() -> int:
    global ARGS
    parser = argparse.ArgumentParser(description="执行 Skill 知识库 Pi Agent 查询")
    subparsers = parser.add_subparsers(dest="command", required=True)

    ask = subparsers.add_parser("ask", help="创建查询并默认等待结果")
    ask.add_argument("--query")
    ask.add_argument("--query-file")
    ask.add_argument("--include-images", action="store_true")
    ask.add_argument("--max-sources", type=int, default=12)
    ask.add_argument("--operation-id")
    group = ask.add_mutually_exclusive_group()
    group.add_argument("--wait", dest="wait", action="store_true")
    group.add_argument("--no-wait", dest="wait", action="store_false")
    ask.set_defaults(wait=True)
    ask.add_argument("--wait-timeout", type=float, default=180.0)
    ask.add_argument("--json", action="store_true")

    status = subparsers.add_parser("status", help="查看或等待已有查询")
    status.add_argument("query_id")
    group = status.add_mutually_exclusive_group()
    group.add_argument("--wait", dest="wait", action="store_true")
    group.add_argument("--no-wait", dest="wait", action="store_false")
    status.set_defaults(wait=False)
    status.add_argument("--wait-timeout", type=float, default=180.0)
    status.add_argument("--json", action="store_true")

    ARGS = parser.parse_args()
    emit_update_notice()

    if ARGS.command == "ask":
        if not 1 <= ARGS.max_sources <= 50:
            raise ConfigError("max-sources 必须为 1-50")
        key = operation_id(ARGS.operation_id, "query")
        data = request_json(
            "POST",
            "/queries",
            body={
                "query": _read_query(),
                "include_images": ARGS.include_images,
                "max_sources": ARGS.max_sources,
            },
            idempotency_key=key,
        )
        if not isinstance(data, dict):
            raise ConfigError("查询创建接口返回结构不正确")
        if ARGS.wait and data.get("status") not in {"succeeded", "failed", "cancelled"}:
            query_id = data.get("query_id")
            if not query_id:
                raise ConfigError("查询创建响应缺少 query_id")
            data = wait_query(query_id, timeout=ARGS.wait_timeout)
        result = {"operation_id": key, "query": data}
        if ARGS.json:
            print_json(result)
        else:
            _render(data, key)
    else:
        data = (
            wait_query(ARGS.query_id, timeout=ARGS.wait_timeout)
            if ARGS.wait
            else request_json("GET", f"/queries/{ARGS.query_id}")
        )
        if not isinstance(data, dict):
            raise ConfigError("查询状态接口返回结构不正确")
        if ARGS.json:
            print_json(data)
        else:
            _render(data)

    return 3 if data.get("status") in {"failed", "cancelled"} else 0


if __name__ == "__main__":
    run(main, json_requested=lambda: bool(ARGS and ARGS.json))
