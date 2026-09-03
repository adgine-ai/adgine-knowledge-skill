from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _client  # noqa: E402
import query  # noqa: E402


class QueryTests(unittest.TestCase):
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

