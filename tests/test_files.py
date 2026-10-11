from __future__ import annotations

import sys
import hashlib
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _client  # noqa: E402
import files  # noqa: E402


class FilesTests(unittest.TestCase):
    def test_download_reports_saved_artifact_and_requires_explicit_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = (Path(directory) / "图片.png").resolve()
            raw = b"\x89PNG\r\n\x1a\n\x00\xff"
            files.ARGS = SimpleNamespace(document_id="doc-1", output=str(path), force=False, json=True)
            def save(_document_id, target):
                target.write_bytes(raw)
                return target
            with mock.patch.object(files, "download_to", side_effect=save) as download, mock.patch.object(files, "print_json") as output:
                self.assertEqual(files._download(), 0)
                result = output.call_args.args[0]
                self.assertEqual(result["output"], str(path))
                self.assertEqual(result["file_name"], "图片.png")
                self.assertEqual(result["file_size"], len(raw))
                self.assertEqual(result["sha256"], hashlib.sha256(raw).hexdigest())
                download.reset_mock()
                with self.assertRaises(_client.ConfigError):
                    files._download()
                download.assert_not_called()
                files.ARGS.force = True
                self.assertEqual(files._download(), 0)
                download.assert_called_once()

    def test_extract_document_id_handles_new_version(self):
        self.assertEqual(files._extract_document_id({"new_document_id": "new-1"}), "new-1")

    def test_extract_document_id_handles_duplicate_existing_id(self):
        self.assertEqual(files._extract_document_id({"existing_id": "old-1"}), "old-1")

    def test_unsupported_extension_fails_before_upload(self):
        with self.assertRaises(_client.ConfigError):
            files._ensure_supported([Path("archive.zip")])

    def test_save_text_requires_force_to_overwrite(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "doc.md"
            path.write_text("old", encoding="utf-8")
            with self.assertRaises(_client.ConfigError):
                files._save_text(path, "new", False)
            files._save_text(path, "new", True)
            self.assertEqual(path.read_text(encoding="utf-8"), "new")

    def test_batch_upload_reports_per_item_failure(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good.md"
            bad = Path(directory) / "bad.pdf"
            good.write_text("good", encoding="utf-8")
            bad.write_bytes(b"bad")
            files.ARGS = SimpleNamespace(
                file=[str(good), str(bad)],
                operation_id="batch-1",
                directory_id=None,
                wait=False,
                wait_timeout=1,
                json=True,
            )
            response = [
                {"file_name": "good.md", "document_id": "doc-1", "status": "pending"},
                {"file_name": "bad.pdf", "error": "parse rejected"},
            ]
            with mock.patch.object(files, "request_multipart", return_value=response), mock.patch.object(
                files, "print_json"
            ) as output:
                code = files._upload()
        self.assertEqual(code, 3)
        self.assertFalse(output.call_args.args[0]["ok"])

    def test_batch_upload_waits_for_document_and_snapshot(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "good.md"
            path.write_text("good", encoding="utf-8")
            files.ARGS = SimpleNamespace(
                file=[str(path)],
                operation_id="batch-2",
                directory_id=None,
                wait=True,
                wait_timeout=1,
                json=True,
            )
            with mock.patch.object(
                files,
                "request_multipart",
                return_value=[
                    {"file_name": "good.md", "document_id": "doc-1", "status": "pending"}
                ],
            ), mock.patch.object(
                files, "wait_document", return_value={"id": "doc-1", "status": "ready"}
            ) as wait_document, mock.patch.object(
                files, "wait_snapshot", return_value={"snapshot_status": "ready"}
            ) as wait_snapshot, mock.patch.object(files, "print_json"):
                code = files._upload()
        self.assertEqual(code, 0)
        wait_document.assert_called_once()
        wait_snapshot.assert_called_once()

    def test_append_markdown_delegates_merge_and_concurrency_to_server(self):
        files.ARGS = SimpleNamespace(
            document_id="doc-1",
            markdown="## New facts\n\nAppended content",
            file=None,
            operation_id="append-1",
            wait=True,
            wait_timeout=1,
            json=True,
        )
        with mock.patch.object(
            files,
            "request_json",
            return_value={"document_id": "doc-1", "coalesced": False},
        ) as request, mock.patch.object(
            files, "wait_document", return_value={"id": "doc-1", "status": "ready"}
        ) as wait_document, mock.patch.object(
            files, "wait_snapshot", return_value={"snapshot_status": "ready"}
        ) as wait_snapshot, mock.patch.object(files, "print_json") as output:
            code = files._append_markdown()

        self.assertEqual(code, 0)
        request.assert_called_once_with(
            "POST",
            "/files/doc-1/content/append",
            body={"markdown": "## New facts\n\nAppended content"},
            idempotency_key="append-1",
            attempts=1,
        )
        wait_document.assert_called_once_with("doc-1", timeout=1)
        wait_snapshot.assert_called_once_with(timeout=1)
        self.assertTrue(output.call_args.args[0]["ok"])


if __name__ == "__main__":
    unittest.main()
