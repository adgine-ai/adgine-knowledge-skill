from __future__ import annotations

import json
import io
import http.client
import os
import sys
import tempfile
import unittest
import urllib.error
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _client  # noqa: E402


class DownloadResponse(io.BytesIO):
    def __init__(self, raw, content_length=None):
        super().__init__(raw)
        self.headers = {"Content-Length": str(len(raw) if content_length is None else content_length)}


class InterruptedDownload(DownloadResponse):
    def read(self, size=-1):
        if self.tell():
            raise http.client.IncompleteRead(b"", 10)
        return super().read(3)


class FakeResponse:
    def __init__(self, payload, status=200):
        self.status = status
        self.payload = payload

    def read(self, _size=-1):
        if isinstance(self.payload, bytes):
            return self.payload
        return json.dumps(self.payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class FakeMultipartResponse:
    status = 200

    def read(self):
        return json.dumps({"code": 0, "data": [{"document_id": "doc-1"}]}).encode(
            "utf-8"
        )


class FakeConnection:
    latest = None

    def __init__(self, host, port=None, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.headers = {}
        self.chunks = []
        self.request = None
        FakeConnection.latest = self

    def putrequest(self, method, path):
        self.request = (method, path)

    def putheader(self, key, value):
        self.headers[key] = value

    def endheaders(self):
        return None

    def send(self, chunk):
        self.chunks.append(chunk)

    def getresponse(self):
        return FakeMultipartResponse()

    def close(self):
        return None


class ClientTests(unittest.TestCase):
    def test_download_preserves_image_and_html_bytes_and_authenticates(self):
        config = _client.Config("https://example.com", "skkb_test")
        for name, raw in (
            ("图片.png", b"\x89PNG\r\n\x1a\n\x00\xff"),
            ("页面.html", "<!doctype html><p>中文</p>".encode("utf-8")),
        ):
            with self.subTest(name=name), tempfile.TemporaryDirectory() as directory:
                target = (Path(directory) / "downloads" / name).resolve()
                with mock.patch("urllib.request.urlopen", return_value=DownloadResponse(raw)) as fetch:
                    self.assertEqual(_client.download_to("doc-1", target, config=config), target)
                self.assertEqual(target.read_bytes(), raw)
                request = fetch.call_args.args[0]
                self.assertEqual(request.full_url, "https://example.com/api/v1/skills/kb/files/doc-1/download")
                self.assertEqual(request.get_header("Authorization"), "Bearer skkb_test")
                self.assertEqual(list(target.parent.iterdir()), [target])

    def test_failed_download_retains_target_and_cleans_temporary_file(self):
        config = _client.Config("https://example.com", "skkb_test")
        for response in (InterruptedDownload(b"partial-data"), DownloadResponse(b"short", 100)):
            with self.subTest(response=type(response).__name__), tempfile.TemporaryDirectory() as directory:
                target = Path(directory) / "page.html"
                target.write_bytes(b"previous file")
                with mock.patch("urllib.request.urlopen", return_value=response):
                    with self.assertRaises(_client.ApiError):
                        _client.download_to("doc-1", target, config=config)
                self.assertEqual(target.read_bytes(), b"previous file")
                self.assertEqual(list(target.parent.iterdir()), [target])

    def test_http_error_is_not_saved_as_file(self):
        config = _client.Config("https://example.com", "skkb_test")
        error = urllib.error.HTTPError("https://example.com", 403, "Forbidden", {}, io.BytesIO(
            b'{"code":40300,"message":"insufficient permission"}'
        ))
        with tempfile.TemporaryDirectory() as directory:
            target = Path(directory) / "page.html"
            with mock.patch("urllib.request.urlopen", side_effect=error):
                with self.assertRaises(_client.ApiError) as caught:
                    _client.download_to("doc-1", target, config=config)
            self.assertEqual(caught.exception.status, 403)
            self.assertFalse(target.exists())
            self.assertEqual(list(Path(directory).iterdir()), [])

    def test_download_without_length_and_directory_target(self):
        config = _client.Config("https://example.com", "skkb_test")
        with tempfile.TemporaryDirectory() as directory:
            response = DownloadResponse(b"html")
            response.headers = {}
            target = Path(directory) / "page.html"
            with mock.patch("urllib.request.urlopen", return_value=response):
                _client.download_to("doc-1", target, config=config)
            self.assertEqual(target.read_bytes(), b"html")
            with mock.patch("urllib.request.urlopen") as fetch:
                with self.assertRaises(_client.ConfigError):
                    _client.download_to("doc-1", Path(directory), config=config)
                fetch.assert_not_called()

    def test_default_base_url_is_production_environment(self):
        self.assertEqual(
            _client.DEFAULT_BASE_URL, "https://industry.adgine.ai"
        )

    def test_normalize_base_url_accepts_endpoint_and_strips_prefix(self):
        self.assertEqual(
            _client.normalize_base_url("https://example.com/api/v1/skills/kb/"),
            "https://example.com",
        )

    def test_normalize_base_url_rejects_query(self):
        with self.assertRaises(_client.ConfigError):
            _client.normalize_base_url("https://example.com?token=secret")

    def test_load_dotenv_does_not_override_process_environment(self):
        with tempfile.TemporaryDirectory() as directory:
            env_file = Path(directory) / ".env"
            env_file.write_text(
                "ADGINE_KNOWLEDGE_API_KEY=skkb_file\nCUSTOM_VALUE='quoted'\n",
                encoding="utf-8",
            )
            with mock.patch.dict(
                os.environ, {"ADGINE_KNOWLEDGE_API_KEY": "skkb_process"}, clear=True
            ):
                _client.load_dotenv(env_file)
                self.assertEqual(os.environ["ADGINE_KNOWLEDGE_API_KEY"], "skkb_process")
                self.assertEqual(os.environ["CUSTOM_VALUE"], "quoted")

    def test_operation_id_is_stable_when_explicit(self):
        self.assertEqual(_client.operation_id("sync-42", "upload"), "sync-42")

    def test_operation_id_rejects_spaces(self):
        with self.assertRaises(_client.ConfigError):
            _client.operation_id("not valid", "query")

    def test_request_json_unwraps_data_and_sends_bearer(self):
        config = _client.Config("https://example.com", "skkb_test")
        response = FakeResponse({"code": 0, "data": {"id": "kb-1"}, "message": "ok"})
        with mock.patch("urllib.request.urlopen", return_value=response) as urlopen:
            data = _client.request_json("GET", "", config=config, attempts=1)
        self.assertEqual(data, {"id": "kb-1"})
        request = urlopen.call_args.args[0]
        self.assertEqual(request.get_header("Authorization"), "Bearer skkb_test")
        self.assertEqual(request.full_url, "https://example.com/api/v1/skills/kb")

    def test_request_json_raises_for_application_error(self):
        config = _client.Config("https://example.com", "skkb_test")
        response = FakeResponse({"code": 40900, "data": None, "message": "busy"})
        with mock.patch("urllib.request.urlopen", return_value=response):
            with self.assertRaises(_client.ApiError) as caught:
                _client.request_json("GET", "", config=config, attempts=1)
        self.assertEqual(caught.exception.code, 40900)

    def test_request_multipart_keeps_per_item_error(self):
        config = _client.Config("https://example.com", "skkb_test")
        payload = {
            "code": 0,
            "data": [{"file_name": "bad.zip", "error": "unsupported"}],
            "message": "ok",
        }
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "bad.zip"
            path.write_bytes(b"zip")
            with mock.patch.object(
                _client,
                "_multipart_once",
                return_value=(200, json.dumps(payload).encode("utf-8")),
            ):
                data = _client.request_multipart(
                    "POST",
                    "/files",
                    files=[("files", path)],
                    config=config,
                    attempts=1,
                )
        self.assertEqual(data[0]["error"], "unsupported")

    def test_streaming_multipart_repeats_files_and_has_exact_length(self):
        config = _client.Config("http://example.com", "skkb_test")
        with tempfile.TemporaryDirectory() as directory:
            first = Path(directory) / "一.md"
            second = Path(directory) / "two.pdf"
            first.write_bytes(b"first-body")
            second.write_bytes(b"second-body")
            with mock.patch("http.client.HTTPConnection", FakeConnection):
                result = _client.request_multipart(
                    "POST",
                    "/files",
                    files=[("files", first), ("files", second)],
                    fields=[("directory_id", "dir-1")],
                    idempotency_key="upload-1",
                    config=config,
                    attempts=1,
                )
        connection = FakeConnection.latest
        body = b"".join(connection.chunks)
        self.assertEqual(result[0]["document_id"], "doc-1")
        self.assertEqual(connection.request, ("POST", "/api/v1/skills/kb/files"))
        self.assertEqual(int(connection.headers["Content-Length"]), len(body))
        self.assertEqual(body.count(b'name="files"'), 2)
        self.assertIn(b'name="directory_id"', body)
        self.assertIn('filename="一.md"'.encode("utf-8"), body)
        self.assertNotIn(b'filename="?.md"', body)
        self.assertIn(b"first-body", body)
        self.assertIn(b"second-body", body)
        self.assertEqual(connection.headers["Idempotency-Key"], "upload-1")

    def test_wait_document_stops_at_ready(self):
        states = [{"status": "processing"}, {"status": "ready", "id": "doc-1"}]
        with mock.patch.object(_client, "request_json", side_effect=states), mock.patch(
            "time.sleep"
        ):
            result = _client.wait_document(
                "doc-1", config=_client.Config("https://example.com", "skkb_test")
            )
        self.assertEqual(result["status"], "ready")


if __name__ == "__main__":
    unittest.main()
