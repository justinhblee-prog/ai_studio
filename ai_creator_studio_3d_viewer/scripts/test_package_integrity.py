from __future__ import annotations

import json
import tempfile
import unittest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_package_integrity import audit_viewer_package


class ViewerPackageIntegrityTests(unittest.TestCase):
    def _fixture(self, root: Path) -> None:
        (root / "src").mkdir()
        (root / "scripts").mkdir()
        (root / "src" / "index.ts").write_text("export { default as Viewer } from './Viewer';\n", encoding="utf-8")
        (root / "src" / "Viewer.tsx").write_text("import React from 'react';\nimport './Viewer.css';\n", encoding="utf-8")
        (root / "src" / "Viewer.css").write_text(".viewer {}\n", encoding="utf-8")
        (root / "scripts" / "check.py").write_text("pass\n", encoding="utf-8")
        (root / "tsconfig.json").write_text(json.dumps({"include": ["src/**/*.ts", "src/**/*.tsx"]}), encoding="utf-8")
        (root / "package.json").write_text(json.dumps({
            "scripts": {"check": "python scripts/check.py"},
            "dependencies": {"three": "^0.180.0"},
            "peerDependencies": {"react": ">=18", "react-dom": ">=18"},
            "devDependencies": {"typescript": "^5.8.0"},
        }), encoding="utf-8")

    def test_current_package_has_no_integrity_findings(self):
        root = Path(__file__).resolve().parents[1]
        self.assertEqual(audit_viewer_package(root), [])

    def test_missing_relative_import_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)
            (root / "src" / "Viewer.tsx").write_text("import './Missing.css';\n", encoding="utf-8")
            findings = audit_viewer_package(root)
            self.assertTrue(any("imports missing local module: ./Missing.css" in item for item in findings))

    def test_undeclared_external_dependency_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)
            (root / "src" / "Viewer.tsx").write_text("import React from 'react';\nimport { x } from 'unlisted-lib';\n", encoding="utf-8")
            findings = audit_viewer_package(root)
            self.assertTrue(any("imports undeclared package: unlisted-lib" in item for item in findings))

    def test_missing_npm_script_target_is_reported(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            self._fixture(root)
            package = json.loads((root / "package.json").read_text(encoding="utf-8"))
            package["scripts"]["broken"] = "python scripts/not-here.py"
            (root / "package.json").write_text(json.dumps(package), encoding="utf-8")
            findings = audit_viewer_package(root)
            self.assertTrue(any("references missing file: scripts/not-here.py" in item for item in findings))


if __name__ == "__main__":
    unittest.main()
