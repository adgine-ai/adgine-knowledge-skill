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
    ".DS_Store",
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
        if item.name in {".DS_Store", ".env"} or (
            item.name.startswith(".env.") and item.name != ".env.example"
        ):
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
    validate_release_metadata(root)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output_path, "w", zipfile.ZIP_DEFLATED) as archive:
        for item in iter_package_files(root):
            archive.write(item, item.relative_to(root).as_posix())


def validate_release_metadata(root: Path) -> None:
    """Validate the single-line release fields used by this WorkBuddy package."""
    content = (root / "SKILL.md").read_text(encoding="utf-8")
    frontmatter = re.match(r"\A---\r?\n(.*?)\r?\n---(?:\r?\n|$)", content, re.DOTALL)
    if frontmatter is None:
        raise ValueError("SKILL.md 缺少 YAML frontmatter")
    fields = {}
    for field in ("name", "description", "description_zh", "description_en", "version", "author"):
        matches = re.findall(rf"^{field}:[ \t]*(.*)$", frontmatter.group(1), re.MULTILINE)
        if len(matches) != 1 or not matches[0].strip().strip("\"'"):
            raise ValueError(f"SKILL.md 缺少或重复发布字段：{field}")
        fields[field] = matches[0].strip().strip("\"'")
    if fields["version"] != read_version(root):
        raise ValueError("SKILL.md version 与 VERSION 不一致")
    if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", fields["name"]):
        raise ValueError("SKILL.md name 必须由小写字母、数字和连字符组成")


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
