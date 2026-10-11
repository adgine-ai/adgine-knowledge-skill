from __future__ import annotations

import sys
import io
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _client  # noqa: E402
import query  # noqa: E402


class QueryTests(unittest.TestCase):
    def test_render_includes_server_images_without_inventing_missing_urls(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            query._render({"status": "succeeded", "images": [
                {"asset_id": "img-1", "url": "https://example.com/product.png", "caption": "产品图", "description": "侧面图"},
                {"asset_id": "img-2", "caption": "no-url"}, None,
            ]})
        rendered = output.getvalue()
        for value in ("img-1", "https://example.com/product.png", "产品图", "侧面图"):
            self.assertIn(value, rendered)
        self.assertNotIn("img-2", rendered)

    def test_ask_sends_include_images_and_preserves_json_images(self):
        args = ["query.py", "ask", "--query", "产品图", "--include-images", "--json", "--operation-id", "query-images"]
        images = [{"asset_id": "img-1", "url": "https://example.com/product.png"}]
        with mock.patch.object(sys, "argv", args), mock.patch.object(query, "emit_update_notice"), mock.patch.object(
            query, "request_json", return_value={"query_id": "q-1", "status": "pending"}
        ) as request, mock.patch.object(query, "wait_query", return_value={
            "status": "succeeded", "answer_status": "complete", "images": images
        }), mock.patch.object(query, "print_json") as output:
            self.assertEqual(query.main(), 0)
        self.assertTrue(request.call_args.kwargs["body"]["include_images"])
        self.assertEqual(output.call_args.args[0]["query"]["images"], images)

    def test_empty_images_render_without_an_image_section(self):
        with mock.patch("sys.stdout", new_callable=io.StringIO) as output:
            query._render({"status": "succeeded", "images": []})
        self.assertNotIn("相关图片", output.getvalue())

    def test_query_argument(self):
        query.ARGS = SimpleNamespace(query="  产品价格？  ", query_file=None)
        self.assertEqual(query._read_query(), "产品价格？")

    def test_query_file(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "query.txt"
            path.write_text("适用对象是什么？\n", encoding="utf-8")
            query.ARGS = SimpleNamespace(query=None, query_file=str(path))
            self.assertEqual(query._read_query(), "适用对象是什么？")

    def test_query_requires_exactly_one_source(self):
        query.ARGS = SimpleNamespace(query="one", query_file="two")
        with self.assertRaises(_client.ConfigError):
            query._read_query()

    def test_query_length_limit(self):
        query.ARGS = SimpleNamespace(query="x" * 4001, query_file=None)
        with self.assertRaises(_client.ConfigError):
            query._read_query()


if __name__ == "__main__":
    unittest.main()
