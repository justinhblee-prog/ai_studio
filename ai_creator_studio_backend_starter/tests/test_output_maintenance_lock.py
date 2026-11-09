import os
import subprocess
import sys
import time
from pathlib import Path


def test_exclusive_cleanup_lock_waits_for_active_worker_shared_lock(tmp_path, monkeypatch):
    import app.config as config
    from app.output_store import output_storage_lock

    monkeypatch.setattr(config, "OUTPUT_DIR", tmp_path)
    marker = tmp_path / "exclusive-acquired.txt"
    code = "\n".join([
        "from pathlib import Path",
        "from app.output_store import output_storage_lock",
        "import sys",
        "with output_storage_lock(exclusive=True):",
        "    Path(sys.argv[1]).write_text('ok')",
    ])
    env = dict(os.environ)
    env["PYTHONPATH"] = str(Path(__file__).resolve().parents[1])
    env["OUTPUT_DIR"] = str(tmp_path)

    with output_storage_lock():
        process = subprocess.Popen(
            [sys.executable, "-c", code, str(marker)],
            cwd=Path(__file__).resolve().parents[1], env=env,
        )
        time.sleep(0.2)
        assert not marker.exists(), "exclusive maintenance must wait for active worker lock"

    assert process.wait(timeout=5) == 0
    assert marker.read_text() == "ok"
