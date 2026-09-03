#!/usr/bin/env python3
"""Validate local configuration and the bound Skill knowledge base."""

from __future__ import annotations

import argparse

from _cli import print_json, run
from _client import emit_update_notice, get_config, request_json


ARGS = None


def main() -> int:
    global ARGS
    parser = argparse.ArgumentParser(description="验证 Adgine Knowledge API Key")
    parser.add_argument("--json", action="store_true", help="输出 JSON")
    ARGS = parser.parse_args()
    emit_update_notice()
    config = get_config()
    data = request_json("GET", "", config=config)
    result = {
        "ok": True,
        "base_url": config.base_url,
        "knowledge_base": data,
    }
    if ARGS.json:
        print_json(result)
    else:
        print("鉴权成功")
        print(f"服务地址：{config.base_url}")
        print(f"知识库：{data.get('name', '-')} ({data.get('id', '-')})")
        print(f"快照状态：{data.get('snapshot_status', '-')}")
    return 0


if __name__ == "__main__":
    run(main, json_requested=lambda: bool(ARGS and ARGS.json))

