from __future__ import annotations

import json
import subprocess
import sys
import unittest
from pathlib import Path

SCRIPT = Path(__file__).with_name("validate_api_contract.py")


class ViewerApiContractValidatorTests(unittest.TestCase):
    def test_canonical_path_normalizes_parameters_and_query(self):
        namespace = {"__name__": "api_contract_validator_test"}
        source = SCRIPT.read_text(encoding="utf-8")
        exec(compile(source, str(SCRIPT), "exec"), namespace)
        self.assertEqual(
            namespace["canonical"]("/v1/assets/${encodeURIComponent(assetId)}/versions/${encodeURIComponent(versionId)}?workspace_id=ws"),
            "/v1/assets/{param}/versions/{param}",
        )

    def test_current_viewer_calls_match_runtime_openapi(self):
        completed = subprocess.run(
            [sys.executable, str(SCRIPT), "--json"],
            check=True,
            capture_output=True,
            text=True,
        )
        report = json.loads(completed.stdout)
        self.assertEqual(report["viewer_calls"], 63)
        self.assertEqual(report["matched"], 63)
        self.assertEqual(report["missing"], [])
        self.assertEqual(report["query_mismatches"], [])
        self.assertEqual(report["unresolved_dynamic"], [])


if __name__ == "__main__":
    unittest.main()
