#!/usr/bin/env python3
"""Configure the API key and endpoint for this Skill."""

from __future__ import annotations

import argparse
import getpass
import os
import sys
import tempfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "scripts"))

from _client import (  # noqa: E402
    API_KEY_ENV,
    BASE_URL_ENV,
    DEFAULT_BASE_URL,
    ApiError,
    Config,
    ConfigError,
    normalize_base_url,
    request_json,
)


def _read_existing(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []


def _write_env(path: Path, api_key: str, base_url: str) -> None:
    replacements = {API_KEY_ENV: api_key, BASE_URL_ENV: base_url}
    output: list[str] = []
    seen = set()
    for line in _read_existing(path):
        stripped = line.strip()
        candidate = stripped[7:].lstrip() if stripped.startswith("export ") else stripped
        if "=" in candidate:
            key = candidate.split("=", 1)[0].strip()
            if key in replacements:
                output.append(f"{key}={replacements[key]}")
                seen.add(key)
                continue
        output.append(line)
    if output and output[-1] != "":
        output.append("")
    for key in (API_KEY_ENV, BASE_URL_ENV):
        if key not in seen:
            output.append(f"{key}={replacements[key]}")
    output.append("")

    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(path.parent), delete=False
    ) as handle:
        handle.write("\n".join(output))
        temp_name = handle.name
    os.chmod(temp_name, 0o600)
    os.replace(temp_name, path)


def main() -> int:
    parser = argparse.ArgumentParser(description="配置 Adgine Knowledge Skill")
    parser.add_argument("key", nargs="?", help=argparse.SUPPRESS)
    parser.add_argument("--key", dest="key_option", help="skkb_ API Key")
    parser.add_argument(
        "--base-url",
        default=os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL),
        help=f"IndustryKB 服务地址（默认 {DEFAULT_BASE_URL}）",
    )
    parser.add_argument(
        "--no-verify", action="store_true", help="只保存配置，不请求服务验证"
    )
    args = parser.parse_args()

    if args.key and args.key_option:
        parser.error("API Key 只能通过位置参数或 --key 提供一次")
    api_key = (args.key_option or args.key or "").strip()
    if not api_key and sys.stdin.isatty():
        api_key = getpass.getpass("Adgine Knowledge API Key: ").strip()
    if not api_key:
        parser.error("缺少 API Key；请使用 --key 或在交互终端输入")
    if not api_key.startswith("skkb_"):
        parser.error("API Key 格式错误：应以 skkb_ 开头")

    try:
        base_url = normalize_base_url(args.base_url)
        _write_env(ROOT / ".env", api_key, base_url)
        print(f"配置已保存到 {ROOT / '.env'}（API Key 未显示）")
        if args.no_verify:
            print("已跳过在线验证")
            return 0
        config = Config(base_url=base_url, api_key=api_key)
        data = request_json("GET", "", config=config)
    except (ConfigError, ApiError) as exc:
        print(f"配置已保存，但在线验证失败：{exc}", file=sys.stderr)
        return 2

    print(f"鉴权成功：{data.get('name', '-')} ({data.get('id', '-')})")
    print(f"快照状态：{data.get('snapshot_status', '-')}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
