#!/usr/bin/env python3
"""Upload, inspect, update, version, download, and delete documents."""

from __future__ import annotations

import argparse
import json
import os
import tempfile
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence

from _cli import format_bytes, print_json, run
from _client import (
    ConfigError,
    SUPPORTED_EXTENSIONS,
    download_to,
    emit_update_notice,
    operation_id,
    request_json,
    request_multipart,
    wait_document,
    wait_snapshot,
)


ARGS = None


def _add_json(parser: argparse.ArgumentParser) -> None:
    parser.add_argument("--json", action="store_true", help="输出 JSON")


def _add_wait(parser: argparse.ArgumentParser, default: bool = True) -> None:
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--wait", dest="wait", action="store_true", help="等待入库完成")
    group.add_argument("--no-wait", dest="wait", action="store_false", help="只返回任务 ID")
    parser.set_defaults(wait=default)
    parser.add_argument("--wait-timeout", type=float, default=300.0)


def _ensure_supported(paths: Sequence[Path]) -> None:
    for path in paths:
        if path.suffix.lower() not in SUPPORTED_EXTENSIONS:
            allowed = ", ".join(sorted(extension.lstrip(".") for extension in SUPPORTED_EXTENSIONS))
            raise ConfigError(f"不支持的文件类型 {path.suffix or '(无扩展名)'}；支持：{allowed}")


def _extract_document_id(item: Any) -> Optional[str]:
    if not isinstance(item, dict):
        return None
    for key in ("document_id", "new_document_id", "existing_id", "id"):
        value = item.get(key)
        if value:
            return str(value)
    return None


def _save_text(path: Path, content: str, force: bool) -> Path:
    target = path.expanduser().resolve()
    if target.exists() and not force:
        raise ConfigError(f"本地文件已存在：{target}；如需覆盖请添加 --force")
    target.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(
        "w", encoding="utf-8", dir=str(target.parent), delete=False
    ) as handle:
        handle.write(content)
        temp_name = handle.name
    os.replace(temp_name, target)
    return target


def _render_list(data: Dict[str, Any]) -> None:
    items = data.get("data") or []
    print(
        f"文件 {len(items)} 条（总数 {data.get('total', len(items))}，"
        f"第 {data.get('page', '-')} 页）"
    )
    for item in items:
        print(
            f"- {item.get('name', '-')} [{item.get('id', '-')}] "
            f"status={item.get('status', '-')} version={item.get('version', '-')} "
            f"size={format_bytes(item.get('file_size'))}"
        )


def _render_upload(result: Dict[str, Any]) -> None:
    print(f"操作幂等键：{result['operation_id']}")
    for item in result.get("items", []):
        name = item.get("file_name", "-")
        if item.get("error"):
            extra = f" existing_id={item.get('existing_id')}" if item.get("existing_id") else ""
            print(f"- 失败：{name}: {item['error']}{extra}")
            continue
        document_id = _extract_document_id(item) or "-"
        duplicate = " duplicate=true" if item.get("duplicate") else ""
        final = item.get("final_status") or item.get("status") or "-"
        print(f"- {name} [{document_id}] status={final}{duplicate}")
    if result.get("snapshot_status"):
        print(f"知识库快照：{result['snapshot_status']}")


def _upload() -> int:
    paths = [Path(value).expanduser().resolve() for value in ARGS.file]
    _ensure_supported(paths)
    key = operation_id(ARGS.operation_id, "upload")
    fields = [("directory_id", ARGS.directory_id)] if ARGS.directory_id else []
    data = request_multipart(
        "POST",
        "/files",
        files=[("files", path) for path in paths],
        fields=fields,
        idempotency_key=key,
    )
    if not isinstance(data, list):
        raise ConfigError("上传接口返回结构不正确：data 应为数组")
    items = data
    had_failure = False
    ready_count = 0
    if ARGS.wait:
        for item in items:
            if item.get("error"):
                had_failure = True
                continue
            document_id = _extract_document_id(item)
            if not document_id:
                had_failure = True
                item["error"] = "响应缺少 document_id"
                continue
            final = wait_document(document_id, timeout=ARGS.wait_timeout)
            item["final_status"] = final.get("status")
            item["document"] = final
            if final.get("status") == "ready":
                ready_count += 1
            else:
                had_failure = True
        snapshot = None
        if ready_count:
            snapshot = wait_snapshot(timeout=ARGS.wait_timeout)
            if snapshot.get("snapshot_status") != "ready":
                had_failure = True
    else:
        snapshot = None
        had_failure = any(bool(item.get("error")) for item in items)

    result = {
        "ok": not had_failure,
        "operation_id": key,
        "items": items,
        "snapshot_status": snapshot.get("snapshot_status") if snapshot else None,
    }
    if ARGS.json:
        print_json(result)
    else:
        _render_upload(result)
    return 0 if not had_failure else 3


def _list() -> int:
    if ARGS.page < 1:
        raise ConfigError("page 必须大于等于 1")
    if not 1 <= ARGS.page_size <= 100:
        raise ConfigError("page-size 必须为 1-100")
    data = request_json(
        "GET",
        "/files",
        params={
            "page": ARGS.page,
            "page_size": ARGS.page_size,
            "status": ARGS.status,
            "keyword": ARGS.keyword,
            "directory_id": ARGS.directory_id,
        },
    )
    if not isinstance(data, dict):
        raise ConfigError("文件列表接口返回结构不正确")
    if ARGS.json:
        print_json(data)
    else:
        _render_list(data)
    return 0


def _status() -> int:
    data = (
        wait_document(ARGS.document_id, timeout=ARGS.wait_timeout)
        if ARGS.wait
        else request_json("GET", f"/files/{ARGS.document_id}")
    )
    if not isinstance(data, dict):
        raise ConfigError("文件详情接口返回结构不正确")
    if ARGS.json:
        print_json(data)
    else:
        print(f"文件：{data.get('name', '-')} [{data.get('id', ARGS.document_id)}]")
        print(f"状态：{data.get('status', '-')}")
        if data.get("error_message"):
            print(f"错误：{data['error_message']}")
    return 0 if data.get("status") not in {"error", "archived"} else 3


def _content() -> int:
    if ARGS.preview_chars < 0:
        raise ConfigError("preview-chars 不能为负数")
    data = request_json("GET", f"/files/{ARGS.document_id}/content")
    if not isinstance(data, dict):
        raise ConfigError("文件内容接口返回结构不正确")
    markdown = str(data.get("markdown") or "")
    if ARGS.output:
        saved = _save_text(Path(ARGS.output), markdown, ARGS.force)
        result = {
            "document_id": ARGS.document_id,
            "name": data.get("name"),
            "output": str(saved),
            "characters": len(markdown),
        }
        if ARGS.json:
            print_json(result)
        else:
            print(f"Canonical Markdown 已保存：{saved}（{len(markdown)} 字符）")
    elif ARGS.json:
        print_json(data)
    else:
        preview = markdown if ARGS.preview_chars == 0 else markdown[: ARGS.preview_chars]
        print(preview)
        if ARGS.preview_chars and len(markdown) > ARGS.preview_chars:
            print(f"\n… 已截断，共 {len(markdown)} 字符；使用 --preview-chars 0 查看全部")
    return 0


def _download() -> int:
    target = Path(ARGS.output).expanduser().resolve()
    if target.exists() and not ARGS.force:
        raise ConfigError(f"本地文件已存在：{target}；如需覆盖请添加 --force")
    saved = download_to(ARGS.document_id, target)
    result = {"ok": True, "document_id": ARGS.document_id, "output": str(saved)}
    if ARGS.json:
        print_json(result)
    else:
        print(f"原文件已下载：{saved}")
    return 0


def _read_markdown_argument() -> str:
    if bool(ARGS.markdown) == bool(ARGS.file):
        raise ConfigError("--markdown 和 --file 必须且只能提供一个")
    if ARGS.file:
        path = Path(ARGS.file).expanduser().resolve()
        if not path.is_file():
            raise ConfigError(f"Markdown 文件不存在：{path}")
        try:
            content = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError) as exc:
            raise ConfigError(f"无法读取 Markdown 文件：{exc}") from exc
    else:
        content = ARGS.markdown
    if not content or not content.strip():
        raise ConfigError("Canonical Markdown 不能为空")
    return content


def _update_markdown() -> int:
    key = operation_id(ARGS.operation_id, "edit-markdown")
    data = request_json(
        "PUT",
        f"/files/{ARGS.document_id}/content",
        body={"markdown": _read_markdown_argument()},
        idempotency_key=key,
    )
    final = None
    snapshot = None
    if ARGS.wait:
        final = wait_document(ARGS.document_id, timeout=ARGS.wait_timeout)
        if final.get("status") == "ready":
            snapshot = wait_snapshot(timeout=ARGS.wait_timeout)
    result = {
        "ok": not final or final.get("status") == "ready",
        "operation_id": key,
        "data": data,
        "document": final,
        "snapshot": snapshot,
    }
    if ARGS.json:
        print_json(result)
    else:
        print(f"Canonical Markdown 已更新；幂等键：{key}")
        if final:
            print(f"文档状态：{final.get('status', '-')}")
        if snapshot:
            print(f"快照状态：{snapshot.get('snapshot_status', '-')}")
    return 0 if result["ok"] else 3


def _new_version() -> int:
    path = Path(ARGS.file).expanduser().resolve()
    _ensure_supported([path])
    key = operation_id(ARGS.operation_id, "new-version")
    data = request_multipart(
        "POST",
        f"/files/{ARGS.document_id}/versions",
        files=[("file", path)],
        idempotency_key=key,
    )
    if not isinstance(data, dict):
        raise ConfigError("新版本接口返回结构不正确")
    new_id = _extract_document_id(data)
    final = None
    snapshot = None
    if ARGS.wait:
        if not new_id:
            raise ConfigError("新版本响应缺少新的 document_id")
        final = wait_document(new_id, timeout=ARGS.wait_timeout)
        if final.get("status") == "ready":
            snapshot = wait_snapshot(timeout=ARGS.wait_timeout)
    result = {
        "ok": not final or final.get("status") == "ready",
        "operation_id": key,
        "old_document_id": ARGS.document_id,
        "new_document_id": new_id,
        "data": data,
        "document": final,
        "snapshot": snapshot,
    }
    if ARGS.json:
        print_json(result)
    else:
        print(f"新版本已上传；幂等键：{key}")
        print(f"旧文档 ID：{ARGS.document_id}")
        print(f"新文档 ID：{new_id or '-'}")
        if final:
            print(f"新文档状态：{final.get('status', '-')}")
    return 0 if result["ok"] else 3


def _simple_read(suffix: str) -> int:
    data = request_json("GET", f"/files/{ARGS.document_id}/{suffix}")
    if ARGS.json:
        print_json(data)
    else:
        print_json(data)
    return 0


def _delete() -> int:
    if not ARGS.yes:
        raise ConfigError("文件删除会永久清理存储、索引和记录；确认后请添加 --yes")
    data = request_json("DELETE", f"/files/{ARGS.document_id}")
    result = {"ok": True, "document_id": ARGS.document_id, "data": data}
    if ARGS.json:
        print_json(result)
    else:
        print(f"文件已永久删除：{ARGS.document_id}")
    return 0


def main() -> int:
    global ARGS
    parser = argparse.ArgumentParser(description="管理 Skill 知识库文件")
    subparsers = parser.add_subparsers(dest="command", required=True)

    listing = subparsers.add_parser("list", help="列出文件；keyword 只搜索文件名")
    listing.add_argument("--page", type=int, default=1)
    listing.add_argument("--page-size", type=int, default=20)
    listing.add_argument("--status")
    listing.add_argument("--keyword")
    listing.add_argument("--directory-id")
    _add_json(listing)

    upload = subparsers.add_parser("upload", help="上传一个或多个文件")
    upload.add_argument("--file", action="append", required=True)
    upload.add_argument("--directory-id")
    upload.add_argument("--operation-id")
    _add_wait(upload)
    _add_json(upload)

    status = subparsers.add_parser("status", help="查看或等待文件处理状态")
    status.add_argument("document_id")
    _add_wait(status, default=False)
    _add_json(status)

    content = subparsers.add_parser("content", help="读取 Canonical Markdown")
    content.add_argument("document_id")
    content.add_argument("--output")
    content.add_argument("--force", action="store_true")
    content.add_argument("--preview-chars", type=int, default=8000)
    _add_json(content)

    download = subparsers.add_parser("download", help="下载原文件")
    download.add_argument("document_id")
    download.add_argument("--output", required=True)
    download.add_argument("--force", action="store_true")
    _add_json(download)

    metadata = subparsers.add_parser("metadata", help="查看文档和快照元数据")
    metadata.add_argument("document_id")
    _add_json(metadata)

    history = subparsers.add_parser("history", help="查看入库处理历史")
    history.add_argument("document_id")
    _add_json(history)

    update = subparsers.add_parser("update-markdown", help="修改 Canonical Markdown")
    update.add_argument("document_id")
    update.add_argument("--markdown")
    update.add_argument("--file")
    update.add_argument("--operation-id")
    _add_wait(update)
    _add_json(update)

    version = subparsers.add_parser("new-version", help="上传原文件的新版本")
    version.add_argument("document_id", help="当前 ready 文档 ID")
    version.add_argument("--file", required=True)
    version.add_argument("--operation-id")
    _add_wait(version)
    _add_json(version)

    delete = subparsers.add_parser("delete", help="永久删除文件")
    delete.add_argument("document_id")
    delete.add_argument("--yes", action="store_true")
    _add_json(delete)

    ARGS = parser.parse_args()
    emit_update_notice()

    if ARGS.command == "list":
        return _list()
    if ARGS.command == "upload":
        return _upload()
    if ARGS.command == "status":
        return _status()
    if ARGS.command == "content":
        return _content()
    if ARGS.command == "download":
        return _download()
    if ARGS.command == "metadata":
        return _simple_read("metadata")
    if ARGS.command == "history":
        return _simple_read("processing-history")
    if ARGS.command == "update-markdown":
        return _update_markdown()
    if ARGS.command == "new-version":
        return _new_version()
    return _delete()


if __name__ == "__main__":
    run(main, json_requested=lambda: bool(ARGS and ARGS.json))
