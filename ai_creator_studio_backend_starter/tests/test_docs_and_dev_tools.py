"""B-20 / B-21: the docs index stays complete, and the one-command local start cannot be pointed at a real database by accident."""
import os

import pytest

from scripts import dev_up, docs_check


def test_every_document_in_docs_is_in_the_index_and_nothing_listed_is_missing(capsys):
    assert docs_check.check() == 0, capsys.readouterr().out
    names = {p.name for p in docs_check.documents()}
    assert {"ONBOARDING.md", "README.md"} <= names and "INDEX.md" not in names


def test_the_index_notices_a_new_undocumented_file_and_a_removed_one(tmp_path, monkeypatch, capsys):
    (tmp_path / "A.md").write_text("# Alpha\n\nfirst line\n", encoding="utf-8")
    monkeypatch.setattr(docs_check, "DOCS", tmp_path)
    monkeypatch.setattr(docs_check, "INDEX", tmp_path / "INDEX.md")
    docs_check.INDEX.write_text(docs_check.render(), encoding="utf-8")
    assert docs_check.check() == 0
    (tmp_path / "B.md").write_text("# Beta\n", encoding="utf-8")
    assert docs_check.check() == 1 and "NOT IN THE INDEX: docs/B.md" in capsys.readouterr().out
    (tmp_path / "A.md").unlink()
    (tmp_path / "B.md").unlink()
    assert docs_check.check() == 1 and "LISTED BUT GONE: docs/A.md" in capsys.readouterr().out
    docs_check.INDEX.unlink()
    assert docs_check.check() == 1


def test_titles_and_first_lines_are_read_and_pipes_cannot_break_the_table(tmp_path):
    p = tmp_path / "X.md"
    p.write_text("\n# A | B\n\n" + "x" * 200 + "\n", encoding="utf-8")
    title, first = docs_check.describe(p)
    assert title == "A / B" and first.endswith("…") and len(first) == 111 and "|" not in title + first


def test_the_local_start_is_mock_only_never_sees_a_database_url_and_keeps_the_callers_python_path(tmp_path, monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "postgresql://u:p@real-host/db")
    monkeypatch.setenv("DATABASE_BACKEND", "postgresql")
    monkeypatch.setenv("PROVIDER_MODE", "fashn")
    monkeypatch.setenv("PYTHONPATH", "/somewhere")
    one, two = dev_up.environment(tmp_path / "a"), dev_up.environment(tmp_path / "b")
    assert one["PROVIDER_MODE"] == "mock" and "DATABASE_URL" not in one and "DATABASE_BACKEND" not in one
    assert one["PYTHONPATH"].split(os.pathsep) == [str(dev_up.BACKEND), "/somewhere"]
    assert one["ASSET_API_TOKENS"] == "local-dev-token:dev-user" and len(one["ASSET_SIGNING_SECRET"]) >= 32 and one["ASSET_SIGNING_SECRET"] != two["ASSET_SIGNING_SECRET"]
    assert one["ASSET_DATABASE_PATH"].startswith(str(tmp_path / "a")) and (tmp_path / "a").is_dir()


def test_prerequisites_name_what_is_missing(monkeypatch):
    import builtins
    real_import = builtins.__import__

    def deny(name, *args, **kwargs):
        if name in ("fastapi", "fcntl"):
            raise ImportError(name)
        return real_import(name, *args, **kwargs)
    monkeypatch.setattr(builtins, "__import__", deny)
    problems = dev_up.prerequisites()
    assert any("fastapi" in p and "pip install" in p for p in problems) and any("fcntl" in p and "WSL" in p for p in problems)


def test_the_dev_token_is_public_and_only_meant_for_the_local_mock_server():
    assert dev_up.DEV_TOKEN == "local-dev-token" and dev_up.free_port() > 0 and dev_up.BACKEND.name == "ai_creator_studio_backend_starter"
    assert "127.0.0.1" in open(dev_up.__file__, encoding="utf-8").read()
