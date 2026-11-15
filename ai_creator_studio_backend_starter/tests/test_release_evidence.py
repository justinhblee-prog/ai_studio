"""R-031: the release evidence page. Values present / absent, defaults match the app, and no secret value is ever printed."""
import importlib
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import release_evidence as ev  # noqa: E402

FAKE_SECRET = "sk-fake-DO-NOT-LEAK-1234567890"
PYTEST_LOG = "........\n903 passed, 1 warning in 59.67s (0:00:59)\n78 passed, 1 warning in 34.81s\n"
FRONT_LOG = "# pass 4\n# fail 0\n# skipped 0\n# pass 8\n# fail 0\n# skipped 0\n"


def write_logs(tmp_path):
    (tmp_path / "pytest.txt").write_text(PYTEST_LOG)
    (tmp_path / "frontend.txt").write_text(FRONT_LOG)
    (tmp_path / "e2e_generation.txt").write_text("PASS x\nSUMMARY 9/9 generation steps passed\n")
    (tmp_path / "e2e_roles.txt").write_text("SUMMARY 5/6 role scenarios passed\n")
    (tmp_path / "e2e_broken.txt").write_text("crashed before any summary\n")


def test_with_logs_the_numbers_are_copied_exactly(tmp_path):
    write_logs(tmp_path)
    text = ev.render(tmp_path, "abc123", {})
    assert "`abc123`" in text
    assert "실행 1: passed 903, failed 0, skipped 0" in text and "실행 2: passed 78" in text
    assert "합계: passed 981" in text
    assert "node 시험 파일 2개: pass 12, fail 0, skipped 0" in text
    assert "| e2e_generation.txt | 9/9 | generation steps | 통과 |" in text
    assert "| e2e_roles.txt | 5/6 | role scenarios | 실패 |" in text
    assert "| e2e_broken.txt | 미확인 | SUMMARY 줄 없음 | 실패 또는 미완료 |" in text


def test_without_logs_everything_is_unknown_never_a_pass(tmp_path):
    text = ev.render(tmp_path, "abc123", {})
    assert text.count("미확인") >= 3
    assert "| 통과 |" not in text and "합계: passed" not in text and "실행 1:" not in text and "node 시험 파일" not in text
    assert ev.render(None, "abc123", {}).count("미확인") >= 3


def test_flag_defaults_match_the_app_and_overrides_are_shown(monkeypatch):
    for name, _, _ in ev.SETTINGS:
        monkeypatch.delenv(name, raising=False)
    monkeypatch.syspath_prepend(str(Path(__file__).resolve().parents[1]))
    from app import config
    config = importlib.reload(config)
    app_values = {"LEGAL_REQUIRE_ACCEPTANCE": "on" if config.LEGAL_REQUIRE_ACCEPTANCE else "off",
                  "ASSET_REQUIRE_RIGHTS_CONFIRMATION": "on" if config.ASSET_REQUIRE_RIGHTS_CONFIRMATION else "off",
                  "DATABASE_BACKEND": config.DATABASE_BACKEND, "PROVIDER_MODE": config.PROVIDER_MODE,
                  "PROVIDER_ROUTING_MODE": config.PROVIDER_ROUTING_MODE}
    for name, default, kind in ev.SETTINGS:
        assert ev.effective(name, default, kind, {}) == (app_values[name], "기본값"), name
    assert ev.effective("LEGAL_REQUIRE_ACCEPTANCE", "off", "flag_off", {"LEGAL_REQUIRE_ACCEPTANCE": "1"}) == ("on", "환경 변수로 지정")
    assert ev.effective("ASSET_REQUIRE_RIGHTS_CONFIRMATION", "on", "flag_on", {"ASSET_REQUIRE_RIGHTS_CONFIRMATION": "0"})[0] == "off"
    assert ev.effective("DATABASE_BACKEND", "sqlite", "text", {"DATABASE_BACKEND": " PostgreSQL "})[0] == "postgresql"


def test_secret_values_never_appear_but_their_names_do(tmp_path):
    write_logs(tmp_path)
    (tmp_path / "pytest.txt").write_text(PYTEST_LOG + f"warning mentions {FAKE_SECRET} by accident\n")
    (tmp_path / "e2e_leak.txt").write_text(f"SUMMARY 1/1 leak {FAKE_SECRET} steps passed\n")
    env = {"FASHN_API_KEY": FAKE_SECRET, "ASSET_SIGNING_SECRET": "", "PATH": "/usr/bin"}
    text = ev.render(tmp_path, f"commit-{FAKE_SECRET}", env)
    assert FAKE_SECRET not in text
    assert "`FASHN_API_KEY`: 설정됨" in text and "`ASSET_SIGNING_SECRET`: 비어 있음" in text
    assert "PATH" not in text.split("## 비밀값")[1]
    assert "[REDACTED]" in text


def test_main_writes_the_out_file(tmp_path, monkeypatch):
    write_logs(tmp_path)
    monkeypatch.setenv("FASHN_API_KEY", FAKE_SECRET)
    out = tmp_path / "evidence.md"
    assert ev.main(["--logs-dir", str(tmp_path), "--commit", "deadbeef", "--out", str(out)]) == 0
    body = out.read_text(encoding="utf-8")
    assert "deadbeef" in body and FAKE_SECRET not in body
