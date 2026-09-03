"""Standard-library client for the IndustryKB Skill API."""

from __future__ import annotations

import http.client
import json
import mimetypes
import os
import random
import shutil
import ssl
import sys
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable, Dict, Iterable, List, Mapping, Optional, Sequence, Tuple


SKILL_ROOT = Path(__file__).resolve().parent.parent
API_PREFIX = "/api/v1/skills/kb"
DEFAULT_BASE_URL = "https://industry.afrgame.dev:31000"
API_KEY_ENV = "ADGINE_KNOWLEDGE_API_KEY"
BASE_URL_ENV = "ADGINE_KNOWLEDGE_BASE_URL"
VERSION = (SKILL_ROOT / "VERSION").read_text(encoding="utf-8").strip()
USER_AGENT = f"adgine-knowledge-skill/{VERSION}"
RETRYABLE_HTTP = {500, 502, 503}
SUPPORTED_EXTENSIONS = {
    ".pdf",
    ".docx",
    ".xlsx",
    ".pptx",
    ".txt",
    ".md",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}


class ConfigError(RuntimeError):
    pass


class ApiError(RuntimeError):
    def __init__(
        self,
        status: int,
        message: str,
        *,
        code: Optional[int] = None,
        data: Any = None,
    ) -> None:
        super().__init__(message)
        self.status = status
        self.code = code
        self.message = message
        self.data = data

    def __str__(self) -> str:
        prefix = f"HTTP {self.status}" if self.status else "network error"
        code = f", code={self.code}" if self.code is not None else ""
        return f"{prefix}{code}: {self.message}"


class PollTimeout(RuntimeError):
    def __init__(self, message: str, latest: Optional[Dict[str, Any]] = None) -> None:
        super().__init__(message)
        self.latest = latest or {}


@dataclass(frozen=True)
class Config:
    base_url: str
    api_key: str
    timeout: float = 30.0


def load_dotenv(path: Optional[Path] = None) -> None:
    env_path = path or SKILL_ROOT / ".env"
    try:
        lines = env_path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return
    for raw in lines:
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        if line.startswith("export "):
            line = line[7:].lstrip()
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if len(value) >= 2 and value[0] == value[-1] and value[0] in {'"', "'"}:
            value = value[1:-1]
        if key:
            os.environ.setdefault(key, value)


def normalize_base_url(value: str) -> str:
    raw = value.strip().rstrip("/")
    parsed = urllib.parse.urlsplit(raw)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise ConfigError("ADGINE_KNOWLEDGE_BASE_URL 必须是有效的 http/https 地址")
    if parsed.query or parsed.fragment:
        raise ConfigError("ADGINE_KNOWLEDGE_BASE_URL 不能包含 query 或 fragment")
    path = parsed.path.rstrip("/")
    if path.endswith(API_PREFIX):
        path = path[: -len(API_PREFIX)]
    return urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, path, "", "")).rstrip("/")


def get_config(
    *,
    require_key: bool = True,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = 30.0,
) -> Config:
    load_dotenv()
    resolved_key = (api_key if api_key is not None else os.getenv(API_KEY_ENV, "")).strip()
    if require_key and not resolved_key:
        raise ConfigError(
            "缺少 ADGINE_KNOWLEDGE_API_KEY；请运行 setup.py 或设置环境变量"
        )
    resolved_base = base_url or os.getenv(BASE_URL_ENV, DEFAULT_BASE_URL)
    return Config(
        base_url=normalize_base_url(resolved_base),
        api_key=resolved_key,
        timeout=timeout,
    )


def operation_id(explicit: Optional[str], prefix: str) -> str:
    value = explicit.strip() if explicit else f"{prefix}-{uuid.uuid4()}"
    if not 1 <= len(value) <= 128:
        raise ConfigError("Idempotency-Key 长度必须为 1-128 个字符")
    if any(ord(char) < 33 or ord(char) > 126 for char in value):
        raise ConfigError("Idempotency-Key 只能包含可见 ASCII 字符且不能包含空格")
    return value


def api_url(config: Config, path: str = "") -> str:
    suffix = path if path.startswith("/") or not path else f"/{path}"
    return f"{config.base_url}{API_PREFIX}{suffix}"


def _headers(
    config: Config,
    *,
    content_type: Optional[str] = None,
    idempotency_key: Optional[str] = None,
) -> Dict[str, str]:
    headers = {
        "Accept": "application/json",
        "Authorization": f"Bearer {config.api_key}",
        "User-Agent": USER_AGENT,
    }
    if content_type:
        headers["Content-Type"] = content_type
    if idempotency_key:
        headers["Idempotency-Key"] = idempotency_key
    return headers


def _decode_payload(raw: bytes) -> Any:
    if not raw:
        return None
    try:
        return json.loads(raw.decode("utf-8"))
    except (UnicodeError, ValueError) as exc:
        preview = raw[:300].decode("utf-8", errors="replace")
        raise ApiError(0, f"服务返回了非 JSON 内容: {preview}") from exc


def _error_from_payload(status: int, raw: bytes) -> ApiError:
    try:
        payload = json.loads(raw.decode("utf-8")) if raw else {}
    except (UnicodeError, ValueError):
        preview = raw[:300].decode("utf-8", errors="replace")
        return ApiError(status, preview or "empty error response")
    if isinstance(payload, dict):
        return ApiError(
            status,
            str(payload.get("message") or "request failed"),
            code=payload.get("code"),
            data=payload.get("data"),
        )
    return ApiError(status, "request failed", data=payload)


def _unwrap(status: int, raw: bytes) -> Any:
    if status == 204 and not raw:
        return None
    payload = _decode_payload(raw)
    if not isinstance(payload, dict):
        raise ApiError(status, "服务返回 JSON 结构不正确", data=payload)
    if payload.get("code") != 0:
        raise ApiError(
            status,
            str(payload.get("message") or "request failed"),
            code=payload.get("code"),
            data=payload.get("data"),
        )
    return payload.get("data")


def _backoff(attempt: int) -> None:
    delay = min(4.0, float(2**attempt)) + random.uniform(0.0, 0.25)
    time.sleep(delay)


def request_json(
    method: str,
    path: str = "",
    *,
    body: Optional[Mapping[str, Any]] = None,
    params: Optional[Mapping[str, Any]] = None,
    idempotency_key: Optional[str] = None,
    config: Optional[Config] = None,
    attempts: int = 3,
) -> Any:
    cfg = config or get_config()
    url = api_url(cfg, path)
    if params:
        query = urllib.parse.urlencode(
            [(key, value) for key, value in params.items() if value is not None]
        )
        if query:
            url = f"{url}?{query}"
    data = None
    content_type = None
    if body is not None:
        data = json.dumps(body, ensure_ascii=False).encode("utf-8")
        content_type = "application/json"
    headers = _headers(
        cfg, content_type=content_type, idempotency_key=idempotency_key
    )
    last_error: Optional[BaseException] = None
    for attempt in range(max(1, attempts)):
        request = urllib.request.Request(url, data=data, headers=headers, method=method.upper())
        try:
            with urllib.request.urlopen(request, timeout=cfg.timeout) as response:
                return _unwrap(response.status, response.read())
        except urllib.error.HTTPError as exc:
            raw = exc.read()
            if exc.code in RETRYABLE_HTTP and attempt + 1 < attempts:
                last_error = exc
                _backoff(attempt)
                continue
            raise _error_from_payload(exc.code, raw) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                _backoff(attempt)
                continue
            raise ApiError(0, str(exc)) from exc
    raise ApiError(0, str(last_error or "request failed"))


def _safe_form_token(value: str, label: str) -> str:
    if "\r" in value or "\n" in value or '"' in value:
        raise ConfigError(f"{label} 包含不安全字符")
    return value


def _field_part(boundary: str, name: str, value: str) -> bytes:
    safe_name = _safe_form_token(name, "multipart field name")
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{safe_name}"\r\n\r\n'
        f"{value}\r\n"
    ).encode("utf-8")


def _file_header(boundary: str, field: str, path: Path) -> bytes:
    safe_field = _safe_form_token(field, "multipart field name")
    fallback = path.name.encode("ascii", errors="replace").decode("ascii")
    fallback = _safe_form_token(fallback, "filename")
    encoded = urllib.parse.quote(path.name, safe="")
    mime = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="{safe_field}"; '
        f'filename="{fallback}"; filename*=UTF-8\'\'{encoded}\r\n'
        f"Content-Type: {mime}\r\n\r\n"
    ).encode("utf-8")


def _multipart_once(
    cfg: Config,
    method: str,
    path: str,
    fields: Sequence[Tuple[str, str]],
    files: Sequence[Tuple[str, Path]],
    idempotency_key: Optional[str],
) -> Tuple[int, bytes]:
    boundary = f"adgine-knowledge-{uuid.uuid4().hex}"
    field_parts = [_field_part(boundary, key, value) for key, value in fields]
    file_parts = [(_file_header(boundary, field, file_path), file_path) for field, file_path in files]
    closing = f"--{boundary}--\r\n".encode("ascii")
    content_length = sum(len(part) for part in field_parts) + len(closing)
    for header, file_path in file_parts:
        content_length += len(header) + file_path.stat().st_size + 2

    parsed = urllib.parse.urlsplit(api_url(cfg, path))
    request_path = parsed.path or "/"
    if parsed.query:
        request_path = f"{request_path}?{parsed.query}"
    connection_type = (
        http.client.HTTPSConnection if parsed.scheme == "https" else http.client.HTTPConnection
    )
    connection = connection_type(parsed.hostname, parsed.port, timeout=cfg.timeout)
    try:
        connection.putrequest(method.upper(), request_path)
        for key, value in _headers(
            cfg,
            content_type=f"multipart/form-data; boundary={boundary}",
            idempotency_key=idempotency_key,
        ).items():
            connection.putheader(key, value)
        connection.putheader("Content-Length", str(content_length))
        connection.endheaders()
        for part in field_parts:
            connection.send(part)
        for header, file_path in file_parts:
            connection.send(header)
            with file_path.open("rb") as source:
                while True:
                    chunk = source.read(64 * 1024)
                    if not chunk:
                        break
                    connection.send(chunk)
            connection.send(b"\r\n")
        connection.send(closing)
        response = connection.getresponse()
        return response.status, response.read()
    finally:
        connection.close()


def request_multipart(
    method: str,
    path: str,
    *,
    files: Sequence[Tuple[str, Path]],
    fields: Sequence[Tuple[str, str]] = (),
    idempotency_key: Optional[str] = None,
    config: Optional[Config] = None,
    attempts: int = 3,
) -> Any:
    cfg = config or get_config()
    normalized_files: List[Tuple[str, Path]] = []
    for field, raw_path in files:
        file_path = Path(raw_path).expanduser().resolve()
        if not file_path.is_file():
            raise ConfigError(f"文件不存在或不是普通文件: {file_path}")
        normalized_files.append((field, file_path))
    if not normalized_files:
        raise ConfigError("至少需要一个上传文件")

    last_error: Optional[BaseException] = None
    for attempt in range(max(1, attempts)):
        try:
            status, raw = _multipart_once(
                cfg,
                method,
                path,
                fields,
                normalized_files,
                idempotency_key,
            )
            if status in RETRYABLE_HTTP and attempt + 1 < attempts:
                last_error = _error_from_payload(status, raw)
                _backoff(attempt)
                continue
            if not 200 <= status < 300:
                raise _error_from_payload(status, raw)
            return _unwrap(status, raw)
        except ApiError:
            raise
        except (http.client.HTTPException, ssl.SSLError, TimeoutError, OSError) as exc:
            last_error = exc
            if attempt + 1 < attempts:
                _backoff(attempt)
                continue
            raise ApiError(0, str(exc)) from exc
    raise ApiError(0, str(last_error or "upload failed"))


def download_to(
    document_id: str,
    destination: Path,
    *,
    config: Optional[Config] = None,
) -> Path:
    cfg = config or get_config()
    target = Path(destination).expanduser().resolve()
    if target.exists() and target.is_dir():
        raise ConfigError("下载目标必须是文件路径，不能只是目录")
    target.parent.mkdir(parents=True, exist_ok=True)
    request = urllib.request.Request(
        api_url(cfg, f"/files/{document_id}/download"),
        headers=_headers(cfg),
        method="GET",
    )
    temp_name: Optional[str] = None
    try:
        with urllib.request.urlopen(request, timeout=cfg.timeout) as response:
            with tempfile.NamedTemporaryFile(
                "wb", dir=str(target.parent), delete=False
            ) as handle:
                temp_name = handle.name
                shutil.copyfileobj(response, handle, length=64 * 1024)
        os.replace(temp_name, target)
        return target
    except urllib.error.HTTPError as exc:
        raise _error_from_payload(exc.code, exc.read()) from exc
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise ApiError(0, str(exc)) from exc
    finally:
        if temp_name:
            try:
                Path(temp_name).unlink(missing_ok=True)
            except OSError:
                pass


def _poll_delay(elapsed: float) -> float:
    return 2.0 if elapsed < 10.0 else 5.0


def wait_document(
    document_id: str,
    *,
    timeout: float = 300.0,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    cfg = config or get_config()
    started = time.monotonic()
    latest: Dict[str, Any] = {}
    while True:
        result = request_json("GET", f"/files/{document_id}", config=cfg)
        latest = result if isinstance(result, dict) else {"data": result}
        status = str(latest.get("status", ""))
        if status == "ready":
            return latest
        if status in {"error", "archived"}:
            return latest
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            raise PollTimeout(
                f"等待文档 {document_id} 就绪超时（{timeout:g}s）", latest
            )
        time.sleep(min(_poll_delay(elapsed), max(0.0, timeout - elapsed)))


def wait_snapshot(
    *,
    timeout: float = 300.0,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    cfg = config or get_config()
    started = time.monotonic()
    latest: Dict[str, Any] = {}
    while True:
        result = request_json("GET", "", config=cfg)
        latest = result if isinstance(result, dict) else {"data": result}
        status = str(latest.get("snapshot_status", ""))
        if status == "ready":
            return latest
        if status == "failed":
            return latest
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            raise PollTimeout(f"等待知识库快照就绪超时（{timeout:g}s）", latest)
        time.sleep(min(_poll_delay(elapsed), max(0.0, timeout - elapsed)))


def wait_query(
    query_id: str,
    *,
    timeout: float = 180.0,
    config: Optional[Config] = None,
) -> Dict[str, Any]:
    cfg = config or get_config()
    started = time.monotonic()
    latest: Dict[str, Any] = {}
    while True:
        result = request_json("GET", f"/queries/{query_id}", config=cfg)
        latest = result if isinstance(result, dict) else {"data": result}
        if str(latest.get("status", "")) in {"succeeded", "failed", "cancelled"}:
            return latest
        elapsed = time.monotonic() - started
        if elapsed >= timeout:
            raise PollTimeout(f"等待查询 {query_id} 完成超时（{timeout:g}s）", latest)
        time.sleep(min(_poll_delay(elapsed), max(0.0, timeout - elapsed)))


def emit_update_notice() -> None:
    try:
        from _version import update_notice

        notice = update_notice()
        if notice:
            print(f"[update] {notice}", file=sys.stderr)
    except Exception:
        # This deliberately includes all failures: version checks are advisory only.
        return
