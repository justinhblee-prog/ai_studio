"""Seed a finished generation output for E2E (run with the backend's environment, from the backend directory).

The built-in mock provider never produces an image, so a job cannot finish through the workers. This does what the
backend unit tests do: put a PNG in the output folder and finalize the job through the repository, then the asset-link
worker turns it into a verified immutable AssetVersion. The real provider path is NOT exercised by this.
"""
import hashlib
import io
import sys
from datetime import datetime, timedelta, timezone

from PIL import Image

from app import config, job_repository
from app.output_asset_link_worker import process_one as link

job_id = sys.argv[1]
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
buffer = io.BytesIO()
Image.new("RGB", (48, 48), (50, 120, 210)).save(buffer, format="PNG")
content = buffer.getvalue()
storage_key = f"{job_id}.attempt-e2e-001.png"
(config.OUTPUT_DIR / storage_key).write_bytes(content)
now = datetime.now(timezone.utc)
task_id = f"poll_e2e_seed_{job_id}"  # unique per job so more than one job can be seeded in a run
with job_repository._connect() as db:
    db.execute("UPDATE generation_jobs SET status='post_processing' WHERE job_id=?", (job_id,))
    db.execute("UPDATE generation_executions SET status='post_processing' WHERE job_id=?", (job_id,))
    db.execute("""INSERT INTO generation_poll_tasks(task_id,job_id,phase,status,attempts,available_at,claimed_by,
        claimed_at,lease_expires_at,created_at,updated_at) VALUES(?,?,'persist_output','processing',1,?,?,?,?,?,?)""",
               (task_id, job_id, now.isoformat(), "poller", now.isoformat(), (now + timedelta(minutes=5)).isoformat(), now.isoformat(), now.isoformat()))
ok = job_repository.finalize_output_success(task_id, "poller", job_id, storage_key=storage_key, media_type="image/png",
                                            size_bytes=len(content), output_url=f"/v1/generation-jobs/{job_id}/output",
                                            checksum_sha256=hashlib.sha256(content).hexdigest())
assert ok is True, "finalize_output_success refused"
assert link(worker_id="e2e-link") is True, "asset link worker had nothing to link"
print("seeded", job_id)
