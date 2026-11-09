from pathlib import Path


def test_original_qa_ids_and_scenarios_are_preserved_in_evidence_crosswalk():
    report = Path("docs/QA_T01_T14_IMPLEMENTATION_EVIDENCE_v0_1.md").read_text()
    for index in range(1, 15):
        assert f"T-{index:02d}" in report
    assert "No Gate is marked PASS" in report
    assert "T-05" in report and "T-06" in report and "T-10" in report
