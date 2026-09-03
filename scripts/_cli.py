"""Shared CLI formatting and error handling."""

from __future__ import annotations

import json
import sys
from typing import Any, Callable, Dict, Optional

from _client import ApiError, ConfigError, PollTimeout


def print_json(value: Any) -> None:
    print(json.dumps(value, ensure_ascii=False, indent=2, default=str))


def format_bytes(value: Any) -> str:
    try:
        size = float(value)
    except (TypeError, ValueError):
        return str(value or "-")
    units = ["B", "KB", "MB", "GB", "TB"]
    index = 0
    while size >= 1024 and index < len(units) - 1:
        size /= 1024
        index += 1
    return f"{size:.1f} {units[index]}" if index else f"{int(size)} B"


def error_payload(exc: BaseException) -> Dict[str, Any]:
    if isinstance(exc, ApiError):
        return {
            "ok": False,
            "error": "api_error",
            "http_status": exc.status,
            "code": exc.code,
            "message": exc.message,
            "data": exc.data,
        }
    if isinstance(exc, PollTimeout):
        return {
            "ok": False,
            "error": "poll_timeout",
            "message": str(exc),
            "latest": exc.latest,
        }
    return {"ok": False, "error": "configuration_error", "message": str(exc)}


def run(main: Callable[[], int], *, json_requested: Optional[Callable[[], bool]] = None) -> None:
    try:
        code = main()
    except (ApiError, ConfigError, PollTimeout) as exc:
        wants_json = bool(json_requested and json_requested())
        if wants_json:
            print_json(error_payload(exc))
        else:
            print(f"错误：{exc}", file=sys.stderr)
        raise SystemExit(2)
    except KeyboardInterrupt:
        print("操作已取消", file=sys.stderr)
        raise SystemExit(130)
    raise SystemExit(code)

