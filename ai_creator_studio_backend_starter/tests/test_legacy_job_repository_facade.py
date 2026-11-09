from pathlib import Path


def test_legacy_job_repository_is_facade_without_embedded_sql():
    source = Path("app/job_repository.py").read_text()
    forbidden = ("SELECT ", "INSERT INTO ", "UPDATE ", "DELETE FROM ", "CREATE TABLE ")
    assert not any(statement in source.upper() for statement in forbidden)
    assert "def create_job" in source
    assert "def transition_job" in source
    assert "def reconcile_unknown_submission" in source


def test_storage_contract_no_longer_claims_sql_lives_in_legacy_module():
    source = Path("app/storage.py").read_text()
    assert "query dialect remain in\njob_repository.py" not in source
