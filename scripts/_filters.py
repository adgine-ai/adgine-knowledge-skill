"""Shared, dependency-free Skill query filter CLI parameters."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path

from _client import ConfigError

LIST_FLAGS = {
    "employee-name": "employee_names", "employee-id": "employee_ids",
    "directory-id": "directory_ids", "directory-path": "directory_paths",
    "document-id": "document_ids", "record-kind": "record_kinds",
    "report-type": "report_types", "scope": "scopes", "variant": "variants",
    "origin": "origins", "mime-type": "mime_types",
}
ALLOWED = set(LIST_FLAGS.values()) | {
    "date_from", "date_to_exclusive", "date_match", "include_descendants",
    "filename_keyword", "exclude_test", "latest_only",
}


def add_filter_args(parser, *, existing_directory=False):
    parser.add_argument("--filters-file", help="UTF-8 JSON filter object; explicit flags override its fields")
    for flag in LIST_FLAGS:
        if flag == "directory-id" and existing_directory:
            continue
        parser.add_argument("--" + flag, action="append", help="Repeat for multiple values")
    parser.add_argument("--date-from", help="Business date, YYYY-MM-DD, inclusive")
    parser.add_argument("--date-to-exclusive", help="Business date, YYYY-MM-DD, exclusive")
    parser.add_argument("--date-match", choices=["contained", "overlap"])
    parser.add_argument("--filename-keyword")
    parser.add_argument("--no-descendants", action="store_true")
    parser.add_argument("--include-test", action="store_true")
    parser.add_argument("--all-revisions", action="store_true")


def read_filters(args, *, existing_directory=False):
    filters = {}
    requested = bool(getattr(args, "filters_file", None))
    if getattr(args, "filters_file", None):
        try:
            filters = json.loads(Path(getattr(args, "filters_file", None)).expanduser().read_text(encoding="utf-8"))
        except (OSError, ValueError) as exc:
            raise ConfigError(f"Cannot read filters file: {exc}") from exc
        if not isinstance(filters, dict) or set(filters) - ALLOWED:
            raise ConfigError("filters-file must be an object containing supported filter fields")
    for flag, field in LIST_FLAGS.items():
        if flag == "directory-id" and existing_directory:
            continue
        value = getattr(args, flag.replace("-", "_"), None)
        if value is not None:
            filters[field] = value
    for flag in ("date_from", "date_to_exclusive", "date_match", "filename_keyword"):
        value = getattr(args, flag, None)
        if value is not None:
            filters[flag] = value
    if getattr(args, "no_descendants", False):
        filters["include_descendants"] = False
    if getattr(args, "include_test", False):
        filters["exclude_test"] = False
    if getattr(args, "all_revisions", False):
        filters["latest_only"] = False
    for field in LIST_FLAGS.values():
        if field in filters and (not isinstance(filters[field], list) or
                                 any(not isinstance(x, str) or not x.strip() for x in filters[field])):
            raise ConfigError(f"{field} must be a list of nonempty strings")
    for field in ("include_descendants", "exclude_test", "latest_only"):
        if field in filters and not isinstance(filters[field], bool):
            raise ConfigError(f"{field} must be a boolean")
    start, end = filters.get("date_from"), filters.get("date_to_exclusive")
    if bool(start) != bool(end):
        raise ConfigError("date-from and date-to-exclusive must be supplied together")
    if start:
        try:
            a, b = dt.date.fromisoformat(start), dt.date.fromisoformat(end)
        except (TypeError, ValueError) as exc:
            raise ConfigError("Dates must use YYYY-MM-DD") from exc
        if b <= a:
            raise ConfigError("date-to-exclusive must be after date-from")
        filters["date_from"], filters["date_to_exclusive"] = a.isoformat(), b.isoformat()
    return filters if filters or requested else None


def verify_applied_filters(data, filters, mode=None):
    scope = data.get("query_scope")
    if not isinstance(scope, dict) or not isinstance(scope.get("filters"), dict):
        raise ConfigError("Server did not confirm the filter scope; refusing to use an unfiltered result")
    for key, value in (filters or {}).items():
        actual = scope["filters"].get(key)
        if isinstance(value, list):
            value = sorted({v.strip() for v in value})
            actual = sorted(set(actual)) if isinstance(actual, list) else actual
        if actual != value:
            raise ConfigError(f"Server did not apply requested filter: {key}")
    if mode is not None and scope.get("mode") != mode:
        raise ConfigError("Server did not apply the requested query mode")
