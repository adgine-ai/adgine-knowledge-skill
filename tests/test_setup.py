from __future__ import annotations

import importlib.util
import os
import stat
import tempfile
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location("adgine_knowledge_setup", ROOT / "setup.py")
assert SPEC and SPEC.loader
setup_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(setup_module)


class SetupTests(unittest.TestCase):
    def test_write_env_preserves_unrelated_settings_and_hides_permissions(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / ".env"
            path.write_text(
                "OTHER_SETTING=keep\nADGINE_KNOWLEDGE_API_KEY=skkb_old\n",
                encoding="utf-8",
            )
            setup_module._write_env(path, "skkb_new", "https://example.com")
            content = path.read_text(encoding="utf-8")
            self.assertIn("OTHER_SETTING=keep", content)
            self.assertIn("ADGINE_KNOWLEDGE_API_KEY=skkb_new", content)
            self.assertNotIn("skkb_old", content)
            self.assertEqual(stat.S_IMODE(path.stat().st_mode), 0o600)


if __name__ == "__main__":
    unittest.main()

