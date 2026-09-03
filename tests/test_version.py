from __future__ import annotations

import json
import os
import sys
import tempfile
import unittest
from pathlib import Path
from unittest import mock


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import _version  # noqa: E402


class FakeResponse:
    def read(self, _size=-1):
        return b"9.9.9\n"

    def __enter__(self):
        return self

    def __exit__(self, *_args):
        return False


class VersionTests(unittest.TestCase):
    def test_update_urls_are_derived_from_git_origin(self):
        completed = mock.Mock(stdout="git@github.com:adgine-ai/Adgine-Knowledge.git\n")
        with mock.patch("subprocess.run", return_value=completed):
            version_url, release_url = _version._urls_from_git_origin()
        self.assertEqual(
            version_url,
            "https://raw.githubusercontent.com/adgine-ai/Adgine-Knowledge/main/VERSION",
        )
        self.assertEqual(
            release_url,
            "https://github.com/adgine-ai/Adgine-Knowledge/releases/latest",
        )

    def test_newer_version_is_detected_and_cached(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "ADGINE_KNOWLEDGE_VERSION_CACHE": str(Path(directory) / "cache.json"),
                "ADGINE_KNOWLEDGE_SKIP_VERSION_CHECK": "",
            },
            clear=False,
        ), mock.patch("urllib.request.urlopen", return_value=FakeResponse()):
            result = _version.check_for_update(force=True)
            cache = json.loads((Path(directory) / "cache.json").read_text(encoding="utf-8"))
        self.assertTrue(result["update_available"])
        self.assertEqual(cache["remote_version"], "9.9.9")

    def test_network_failure_is_non_blocking(self):
        with tempfile.TemporaryDirectory() as directory, mock.patch.dict(
            os.environ,
            {
                "ADGINE_KNOWLEDGE_VERSION_CACHE": str(Path(directory) / "cache.json"),
                "ADGINE_KNOWLEDGE_SKIP_VERSION_CHECK": "",
            },
            clear=False,
        ), mock.patch("urllib.request.urlopen", side_effect=OSError("offline")):
            result = _version.check_for_update(force=True)
        self.assertFalse(result["update_available"])
        self.assertIn("error", result)


if __name__ == "__main__":
    unittest.main()
