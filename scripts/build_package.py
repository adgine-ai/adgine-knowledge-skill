#!/usr/bin/env python3
"""Build distributable .skill and .zip archives for Adgine Knowledge."""

from __future__ import annotations

import argparse
import re
import zipfile
from pathlib import Path
from typing import Iterable


EXCLUDE_DIRS = {
    ".git",
    ".github",
    ".idea",
    ".pytest_cache",
    ".vscode",
    "__pycache__",
    "dist",
    "tests",
}
EXCLUDE_FILES = {
    ".env",
    ".gitignore",
    "scripts/build_package.py",
}
EXCLUDE_SUFFIXES = {".pyc", ".pyo"}
VERSION_PATTERN = re.compile(r"^\d+\.\d+\.\d+(?:[-+][0-9A-Za-z.-]+)?$")


def iter_package_files(root: Path) -> Iterable[Path]:
    for item in sorted(root.rglob("*")):
        if not item.is_file():
            continue
        relative = item.relative_to(root)
        if any(part in EXCLUDE_DIRS for part in relative.parts):
            continue
        if relative.as_posix() in EXCLUDE_FILES or item.suffix in EXCLUDE_SUFFIXES:
            continue
        yield item


def read_version(root: Path) -> str:
    version = (root / "VERSION").read_text(encoding="utf-8").strip()
    if not VERSION_PATTERN.fullmatch(version):
        raise ValueError(f"VERSION 格式不正确: {version!r}")
    return version


def build_archive(output_path: Path, root: Path) -> None:
    if not (root / "SKILL.md").is_file():
        raise FileNotFoundError("Skill 根目录缺少 SKILL.md")
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in iter_package_files(root):
            archive.write(item, item.relative_to(root).as_posix())


def main() -> int:
    parser = argparse.ArgumentParser(description="构建 Adgine Knowledge Skill 安装包")
    parser.add_argument("--output", default="dist", help="输出目录，默认 dist/")
    args = parser.parse_args()

    root = Path(__file__).resolve().parent.parent
    output_dir = Path(args.output).expanduser()
    if not output_dir.is_absolute():
        output_dir = root / output_dir
    version = read_version(root)
    base_name = f"adgine-knowledge-v{version}"
    for extension in (".skill", ".zip"):
        output_path = output_dir / f"{base_name}{extension}"
        build_archive(output_path, root)
        print(f"Built: {output_path} ({output_path.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

