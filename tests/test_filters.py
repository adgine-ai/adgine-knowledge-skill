import argparse
import json
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
from _filters import add_filter_args, read_filters
from _client import ConfigError


class FilterTests(unittest.TestCase):
    def parse(self, arguments):
        parser = argparse.ArgumentParser()
        add_filter_args(parser)
        return read_filters(parser.parse_args(arguments))

    def test_no_filters_preserves_legacy_requests(self):
        self.assertIsNone(self.parse([]))

    def test_repeated_and_boolean_flags(self):
        self.assertEqual(self.parse(["--employee-name", "甲", "--employee-name", "乙",
                                    "--include-test", "--all-revisions", "--no-descendants"]),
                         {"employee_names": ["甲", "乙"], "exclude_test": False,
                          "latest_only": False, "include_descendants": False})

    def test_file_validation_and_flag_override(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "filters.json"
            path.write_text(json.dumps({"employee_names": ["旧姓名"]}))
            self.assertEqual(self.parse(["--filters-file", str(path), "--employee-name", "新姓名"]),
                             {"employee_names": ["新姓名"]})
            path.write_text('{"employee_name":"typo"}')
            with self.assertRaises(ConfigError):
                self.parse(["--filters-file", str(path)])

    def test_reversed_dates(self):
        with self.assertRaises(ConfigError):
            self.parse(["--date-from", "2026-10-12", "--date-to-exclusive", "2026-10-05"])
