from __future__ import annotations

import importlib.util
import tempfile
import unittest
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "adgine_knowledge_build_package", ROOT / "scripts" / "build_package.py"
)
assert SPEC and SPEC.loader
package_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(package_module)


class PackageTests(unittest.TestCase):
    def test_archive_contains_runtime_and_excludes_secrets_and_tests(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory) / "skill"
            root.mkdir()
            (root / "SKILL.md").write_text(
                "---\nname: test\ndescription: Test skill\ndescription_zh: 测试\n"
                "description_en: Test\nauthor: Adgine\nversion: 1.2.3\n---\n", encoding="utf-8")
            (root / "VERSION").write_text("1.2.3\n", encoding="utf-8")
            (root / ".env").write_text("SECRET=value\n", encoding="utf-8")
            (root / ".env.example").write_text("SECRET=\n", encoding="utf-8")
            (root / ".env.test").write_text("SECRET=value\n", encoding="utf-8")
            (root / ".DS_Store").write_bytes(b"junk")
            (root / "scripts").mkdir()
            (root / "scripts" / "client.py").write_text("pass\n", encoding="utf-8")
            (root / "tests").mkdir()
            (root / "tests" / "test_client.py").write_text("pass\n", encoding="utf-8")
            output = Path(directory) / "output.skill"

            package_module.build_archive(output, root)

            with zipfile.ZipFile(output) as archive:
                names = set(archive.namelist())
            self.assertIn("SKILL.md", names)
            self.assertIn("VERSION", names)
            self.assertIn(".env.example", names)
            self.assertIn("scripts/client.py", names)
            self.assertNotIn(".env", names)
            self.assertNotIn(".env.test", names)
            self.assertNotIn(".DS_Store", names)
            self.assertNotIn("tests/test_client.py", names)

    def test_version_validation(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("not-a-version\n", encoding="utf-8")
            with self.assertRaises(ValueError):
                package_module.read_version(root)

    def test_release_metadata_matches_version_and_is_complete(self):
        package_module.validate_release_metadata(ROOT)

    def test_release_rejects_mismatched_or_missing_metadata(self):
        text = (ROOT / "SKILL.md").read_text(encoding="utf-8")
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "VERSION").write_text("9.9.9\n", encoding="utf-8")
            (root / "SKILL.md").write_text(text, encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "不一致"):
                package_module.validate_release_metadata(root)
            (root / "VERSION").write_text((ROOT / "VERSION").read_text(), encoding="utf-8")
            (root / "SKILL.md").write_text(
                "\n".join(line for line in text.splitlines() if not line.startswith("author:")),
                encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "author"):
                package_module.validate_release_metadata(root)


if __name__ == "__main__":
    unittest.main()
