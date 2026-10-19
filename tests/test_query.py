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
    def test_name_search_and_summary_do_not_add_identity_constraints(self):
        for mode in ("search", "summarize"):
            with self.subTest(mode=mode):
                args = ["query.py", "ask", "--query", "查看工作", "--employee-name", "示例员工",
                        "--mode", mode, "--no-wait", "--json"]
                result = {"query_id": "q-name", "status": "queued", "query_scope": {
                    "mode": mode, "filters": {"employee_names": ["示例员工"], "employee_ids": []}}}
                with mock.patch.object(sys, "argv", args), mock.patch.object(query, "emit_update_notice"), \
                     mock.patch.object(query, "request_json", side_effect=[
                         {"filters_supported": True, "filter_metadata_ready": True}, result
                     ]) as request, mock.patch.object(query, "print_json"):
                    self.assertEqual(query.main(), 0)
                self.assertEqual(request.call_count, 2)
                self.assertEqual(request.call_args.args, ("POST", "/queries"))
                self.assertEqual(request.call_args.kwargs["body"]["filters"], {"employee_names": ["示例员工"]})

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

    def test_scoped_summary_sends_exact_business_filters(self):
        args = ["query.py", "ask", "--query", "总结上周工作", "--no-wait", "--json",
                "--employee-name", "唐立兴", "--employee-id", "ou_123",
                "--date-from", "2026-10-05", "--date-to-exclusive", "2026-10-12",
                "--directory-path", "/信息碎片", "--record-kind", "work_record", "--mode", "summarize"]
        with mock.patch.object(sys, "argv", args), mock.patch.object(query, "emit_update_notice"), mock.patch.object(
            query, "request_json", side_effect=[
                {"filters_supported": True, "filter_metadata_ready": True},
                {"query_id": "q1", "status": "queued", "query_scope": {"mode": "summarize", "filters": {
                    "employee_names": ["唐立兴"], "employee_ids": ["ou_123"],
                    "date_from": "2026-10-05", "date_to_exclusive": "2026-10-12",
                    "directory_paths": ["/信息碎片"], "record_kinds": ["work_record"]}}}]
        ) as request, mock.patch.object(query, "print_json"):
            self.assertEqual(query.main(), 0)
        body = request.call_args.kwargs["body"]
        self.assertEqual(body["mode"], "summarize")
        self.assertEqual(body["filters"], {
            "employee_names": ["唐立兴"], "employee_ids": ["ou_123"],
            "date_from": "2026-10-05", "date_to_exclusive": "2026-10-12",
            "directory_paths": ["/信息碎片"], "record_kinds": ["work_record"],
        })

    def test_partial_date_filter_is_rejected_before_request(self):
        with mock.patch.object(sys, "argv", ["query.py", "ask", "--query", "工作", "--date-from", "2026-10-05"]), \
             mock.patch.object(query, "emit_update_notice"), mock.patch.object(query, "request_json") as request:
            with self.assertRaises(_client.ConfigError):
                query.main()
        request.assert_not_called()

    def test_old_server_is_rejected_before_creating_an_unfiltered_query(self):
        args = ["query.py", "ask", "--query", "总结工作", "--employee-name", "唐立兴"]
        with mock.patch.object(sys, "argv", args), mock.patch.object(query, "emit_update_notice"), mock.patch.object(
            query, "request_json", side_effect=_client.ApiError(404, "not found")
        ) as request, mock.patch.object(query, "wait_query") as wait:
            with self.assertRaises(_client.ConfigError):
                query.main()
        request.assert_called_once_with("GET", "/queries/capabilities")
        wait.assert_not_called()

    def test_missing_scope_confirmation_is_not_treated_as_a_filtered_result(self):
        args = ["query.py", "ask", "--query", "总结工作", "--employee-name", "唐立兴"]
        with mock.patch.object(sys, "argv", args), mock.patch.object(query, "emit_update_notice"), mock.patch.object(
            query, "request_json", side_effect=[
                {"filters_supported": True, "filter_metadata_ready": True},
                {"query_id": "q1", "status": "queued"}]
        ), mock.patch.object(query, "wait_query") as wait:
            with self.assertRaises(_client.ConfigError):
                query.main()
        wait.assert_not_called()


if __name__ == "__main__":
    unittest.main()
