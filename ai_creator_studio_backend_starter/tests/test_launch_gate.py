import importlib.util
from pathlib import Path

spec = importlib.util.spec_from_file_location("launch_gate", Path(__file__).resolve().parents[1] / "scripts" / "launch_gate.py")
gate = importlib.util.module_from_spec(spec); spec.loader.exec_module(gate)


def test_parse_pytest_counts():
    assert gate.parse_pytest("x\n684 passed, 59 skipped in 25.43s\n") == {"passed": 684, "failed": 0, "skipped": 59, "error": 0}
    assert gate.parse_pytest("1 failed, 10 passed, 2 errors in 3s")["failed"] == 1
    assert gate.parse_pytest("no summary here") == {"passed": 0, "failed": 0, "skipped": 0, "error": 0}


def test_exit_code_rules():
    ok = {"step": "a", "status": gate.PASS}
    manual = {"step": "m", "status": gate.SKIP, "manual": True}
    assert gate.exit_code([ok, manual]) == 0
    assert gate.exit_code([ok, {"step": "b", "status": gate.FAIL}, manual]) == 1
    assert gate.exit_code([ok, {"step": "c", "status": gate.SKIP}, manual]) == 2
    assert gate.exit_code([{"step": "b", "status": gate.FAIL}, {"step": "c", "status": gate.SKIP}]) == 1


def test_failing_step_is_reported_not_hidden(monkeypatch):
    monkeypatch.setitem(gate.STEPS, "tests", lambda: (gate.FAIL, "boom"))
    monkeypatch.setitem(gate.STEPS, "audit", lambda: (gate.PASS, "ok"))
    monkeypatch.setitem(gate.STEPS, "backup_drill", lambda: (gate.PASS, "ok"))
    results = gate.run()
    assert gate.exit_code(results) == 1
    assert sum(1 for r in results if r.get("manual")) == len(gate.MANUAL)


def test_the_backup_drill_really_runs_on_a_throwaway_database():
    status, detail = gate.step_backup_drill()
    assert status == gate.PASS, detail


def test_the_backup_drill_fails_when_verification_fails(monkeypatch):
    real = gate._run
    def fake(cmd, timeout, env=None):
        if "verify" in cmd:
            return type("R", (), {"returncode": 1, "stdout": "", "stderr": "tampered"})()
        return real(cmd, timeout, env)
    monkeypatch.setattr(gate, "_run", fake)
    status, detail = gate.step_backup_drill()
    assert status == gate.FAIL and "verify failed" in detail


def test_the_drill_runs_every_command_against_temp_paths_never_the_configured_database(tmp_path, monkeypatch):
    real_db = tmp_path / "real.sqlite3"
    real_db.write_bytes(b"not a real database")
    monkeypatch.setenv("ASSET_DATABASE_PATH", str(real_db))
    seen = []
    real = gate._run
    def spy(cmd, timeout, env=None):
        seen.append((cmd, env))
        return real(cmd, timeout, env)
    monkeypatch.setattr(gate, "_run", spy)
    assert gate.step_backup_drill()[0] == gate.PASS
    assert len(seen) == 4  # seed, backup, verify, restore
    for cmd, env in seen:
        assert env is not None, cmd
        assert env["ASSET_DATABASE_PATH"] != str(real_db), cmd
    assert real_db.read_bytes() == b"not a real database"
