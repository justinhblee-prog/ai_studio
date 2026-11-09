"""Crash-window tests for Output artifact creation and maintenance recovery."""
import os
import subprocess
import sys
import time
from pathlib import Path


def test_hard_exit_after_temp_fsync_leaves_collectable_temp_artifact(tmp_path):
    project = Path(__file__).resolve().parents[1]
    code = r'''\
import asyncio, os, sys
from app import config
import app.output_store as store

class Response:
    headers = {"content-type": "image/png"}
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    def raise_for_status(self): pass
    async def aiter_bytes(self): yield b"\x89PNG\r\n\x1a\ncrash-window"
class Client:
    def __init__(self, *args, **kwargs): pass
    async def __aenter__(self): return self
    async def __aexit__(self, *args): return False
    def stream(self, *args, **kwargs): return Response()
store.httpx.AsyncClient = Client
config.FASHN_OUTPUT_HOSTS = ("cdn.fashn.ai",)
# Simulate SIGKILL-equivalent process death after the temp file is fsynced,
# immediately before its atomic rename to the immutable attempt filename.
def crash_before_rename(src, dst): os._exit(73)
store.os.replace = crash_before_rename
with store.output_storage_lock():
    asyncio.run(store.save_provider_output_artifact(
        "https://cdn.fashn.ai/result.png", "job-crash", "task-crash-1"))
'''
    env = dict(os.environ)
    env["PYTHONPATH"] = str(project)
    env["OUTPUT_DIR"] = str(tmp_path)
    proc = subprocess.run([sys.executable, "-c", code], cwd=project, env=env, timeout=10)
    assert proc.returncode == 73

    temp_files = list(tmp_path.glob(".job-crash.*.tmp"))
    assert len(temp_files) == 1
    old = time.time() - 7200
    os.utime(temp_files[0], (old, old))

    from app import config
    from app.output_store import cleanup_orphaned_attempt_outputs, output_storage_lock
    original = config.OUTPUT_DIR
    config.OUTPUT_DIR = tmp_path
    try:
        with output_storage_lock(exclusive=True):
            dry_run = cleanup_orphaned_attempt_outputs(
                set(), older_than_seconds=3600, now=time.time(), apply=False)
            assert temp_files[0].name in dry_run
            assert temp_files[0].exists(), "dry-run must not mutate crash residue"
            deleted = cleanup_orphaned_attempt_outputs(
                set(), older_than_seconds=3600, now=time.time(), apply=True)
        assert temp_files[0].name in deleted
        assert not temp_files[0].exists()
    finally:
        config.OUTPUT_DIR = original


def test_fresh_temp_file_is_not_collected(tmp_path, monkeypatch):
    from app import config
    from app.output_store import cleanup_orphaned_attempt_outputs
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    fresh = tmp_path / ".job-fresh.123.tmp"
    fresh.write_bytes(b"in progress")
    assert cleanup_orphaned_attempt_outputs(
        set(), older_than_seconds=3600, now=time.time(), apply=True) == []
    assert fresh.exists()


def test_unrelated_hidden_temp_file_is_not_collected(tmp_path, monkeypatch):
    from app import config
    from app.output_store import cleanup_orphaned_attempt_outputs
    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    unrelated = tmp_path / ".operator-notes.tmp"
    unrelated.write_bytes(b"keep")
    old = time.time() - 7200
    os.utime(unrelated, (old, old))
    assert cleanup_orphaned_attempt_outputs(
        set(), older_than_seconds=3600, now=time.time(), apply=True) == []
    assert unrelated.exists()
