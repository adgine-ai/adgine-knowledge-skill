"""Low-frequency, non-blocking version checks for the Skill."""

from __future__ import annotations

import json
import os
import re
import subprocess
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple


SKILL_ROOT = Path(__file__).resolve().parent.parent
LOCAL_VERSION_FILE = SKILL_ROOT / "VERSION"
DEFAULT_VERSION_URL = (
    "https://raw.githubusercontent.com/adgine-ai/"
    "Adgine-Knowledge/main/VERSION"
)
DEFAULT_RELEASE_URL = (
    "https://github.com/adgine-ai/Adgine-Knowledge/releases/latest"
)
CACHE_SECONDS = 24 * 60 * 60


def read_local_version() -> str:
    try:
        return LOCAL_VERSION_FILE.read_text(encoding="utf-8").strip()
    except OSError:
        return "0.0.0"


def _version_tuple(value: str) -> Tuple[int, ...]:
    match = re.match(r"^v?(\d+(?:\.\d+)*)", value.strip())
    if not match:
        return (0,)
    return tuple(int(part) for part in match.group(1).split("."))


def _cache_path() -> Path:
    override = os.getenv("ADGINE_KNOWLEDGE_VERSION_CACHE", "").strip()
    if override:
        return Path(override).expanduser()
    cache_root = os.getenv("XDG_CACHE_HOME", "").strip()
    root = Path(cache_root).expanduser() if cache_root else Path.home() / ".cache"
    return root / "adgine-knowledge" / "version-check.json"


def _load_cache() -> Optional[Dict[str, Any]]:
    try:
        data = json.loads(_cache_path().read_text(encoding="utf-8"))
        if isinstance(data, dict):
            return data
    except (OSError, ValueError):
        pass
    return None


def _save_cache(data: Dict[str, Any]) -> None:
    target = _cache_path()
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        with tempfile.NamedTemporaryFile(
            "w", encoding="utf-8", dir=str(target.parent), delete=False
        ) as handle:
            json.dump(data, handle, ensure_ascii=False)
            temp_name = handle.name
        os.replace(temp_name, target)
    except OSError:
        # Version checks must never break a knowledge-base operation.
        return


def _urls_from_git_origin() -> Tuple[Optional[str], Optional[str]]:
    """Derive update URLs after the standalone repository gets a GitHub remote."""
    try:
        result = subprocess.run(
            ["git", "-C", str(SKILL_ROOT), "config", "--get", "remote.origin.url"],
            check=False,
            capture_output=True,
            text=True,
            timeout=1.0,
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    origin = result.stdout.strip()
    match = re.search(r"github\.com[/:]([^/]+)/([^/]+?)(?:\.git)?$", origin)
    if not match:
        return None, None
    owner, repository = match.group(1), match.group(2)
    version_url = f"https://raw.githubusercontent.com/{owner}/{repository}/main/VERSION"
    release_url = f"https://github.com/{owner}/{repository}/releases/latest"
    return version_url, release_url


def check_for_update(force: bool = False, timeout: float = 1.5) -> Dict[str, Any]:
    local = read_local_version()
    if os.getenv("ADGINE_KNOWLEDGE_SKIP_VERSION_CHECK", "").lower() in {
        "1",
        "true",
        "yes",
    }:
        return {"local_version": local, "skipped": True, "update_available": False}

    now = int(time.time())
    cached = _load_cache()
    if (
        not force
        and cached
        and now - int(cached.get("checked_at", 0)) < CACHE_SECONDS
        and cached.get("local_version") == local
    ):
        return cached

    git_version_url, git_release_url = _urls_from_git_origin()
    version_url = os.getenv(
        "ADGINE_KNOWLEDGE_VERSION_URL", git_version_url or DEFAULT_VERSION_URL
    ).strip()
    release_url = os.getenv(
        "ADGINE_KNOWLEDGE_RELEASE_URL", git_release_url or DEFAULT_RELEASE_URL
    ).strip()
    result: Dict[str, Any] = {
        "checked_at": now,
        "local_version": local,
        "version_url": version_url,
        "release_url": release_url,
        "update_available": False,
    }
    try:
        request = urllib.request.Request(
            version_url,
            headers={"User-Agent": "adgine-knowledge-skill-version-check"},
        )
        with urllib.request.urlopen(request, timeout=timeout) as response:
            remote = response.read(128).decode("utf-8").strip()
        if not remote or len(remote) > 64:
            raise ValueError("remote VERSION is invalid")
        result["remote_version"] = remote
        result["update_available"] = _version_tuple(remote) > _version_tuple(local)
    except (OSError, ValueError, UnicodeError, urllib.error.URLError) as exc:
        result["error"] = str(exc)

    _save_cache(result)
    return result


def update_notice(force: bool = False) -> str:
    result = check_for_update(force=force)
    if not result.get("update_available"):
        return ""
    return (
        "Adgine Knowledge Skill 有新版本 "
        f"{result.get('remote_version')}（当前 {result.get('local_version')}）。"
        "用户要求更新时再执行升级；不要静默更新。"
    )
