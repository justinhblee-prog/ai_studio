from __future__ import annotations
import json
import subprocess
import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
import validate_viewer_request_contract as validator

class ViewerRequestContractTests(unittest.TestCase):
    def test_shorthand_and_nested_object_keys_are_extracted(self):
        body = "{ workspace_id: workspaceId, operation, option_values, nested: { child: true }, ids: [a, b] }"
        self.assertEqual(validator.top_level_keys(body), ["workspace_id", "operation", "option_values", "nested", "ids"])

    def test_all_viewer_json_request_bodies_match_runtime_openapi(self):
        completed = subprocess.run([sys.executable, str(Path(__file__).with_name("validate_viewer_request_contract.py"))], capture_output=True, text=True)
        self.assertEqual(completed.returncode, 0, completed.stdout + completed.stderr)
        report_path = Path(__file__).resolve().parents[1] / "docs" / "viewer_request_contract_audit.v1.json"
        report = json.loads(report_path.read_text(encoding="utf-8"))
        self.assertEqual(report["json_body_calls_checked"], 15)
        self.assertEqual(report["skipped"], [])
        self.assertEqual(report["findings"], [])
        self.assertEqual(len(report["enum_checks"]), 2)

if __name__ == "__main__":
    unittest.main()
