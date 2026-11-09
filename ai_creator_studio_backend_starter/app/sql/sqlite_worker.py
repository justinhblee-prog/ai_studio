"""SQLite worker SQL statements, isolated from application orchestration.

This module is intentionally SQLite-only. PostgreSQL equivalents must be added
and integration-tested before a PostgreSQL runtime can be selected.
"""

OUTBOX_EXPIRED = """SELECT event_id,job_id FROM generation_outbox
WHERE status='processing' AND lease_expires_at < ?"""
OUTBOX_EXPIRE_MARK = """UPDATE generation_outbox SET status='needs_reconciliation',last_error=?,lease_expires_at=NULL
WHERE event_id=?"""
OUTBOX_EXPIRE_JOB = """UPDATE generation_jobs SET error_code='PROVIDER_START_UNKNOWN',message=?,updated_at=?,version=version+1
WHERE job_id=? AND status='queued'"""
OUTBOX_EXPIRE_EXECUTION = """UPDATE generation_executions SET status='unknown',error_code='PROVIDER_START_UNKNOWN'
WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)"""
OUTBOX_SELECT_READY = """SELECT * FROM generation_outbox WHERE status='pending' AND available_at<=?
ORDER BY created_at,event_id LIMIT 1"""
OUTBOX_CLAIM = """UPDATE generation_outbox SET status='processing',attempts=attempts+1,claimed_by=?,claimed_at=?,lease_expires_at=?
WHERE event_id=? AND status='pending'"""

POLL_REQUEUE_EXPIRED = """UPDATE generation_poll_tasks SET status='pending',claimed_by=NULL,claimed_at=NULL,
lease_expires_at=NULL,available_at=?,last_error='Poll worker lease expired; safe GET/output task requeued.',updated_at=?
WHERE status='processing' AND lease_expires_at < ?"""
POLL_SELECT_READY = """SELECT * FROM generation_poll_tasks WHERE status='pending' AND available_at<=?
ORDER BY available_at,created_at LIMIT 1"""
POLL_CLAIM = """UPDATE generation_poll_tasks SET status='processing',attempts=attempts+1,claimed_by=?,claimed_at=?,
lease_expires_at=?,updated_at=? WHERE task_id=? AND status='pending'"""

# Output finalization is executed as one SQLite transaction by the repository.
# Keep these statements named here to make the engine-specific write contract visible.
OUTPUT_UPSERT = """INSERT INTO generation_outputs
(output_id,job_id,storage_key,media_type,size_bytes,created_at,checksum_sha256) VALUES(?,?,?,?,?,?,?)
ON CONFLICT(job_id) DO UPDATE SET storage_key=excluded.storage_key,
media_type=excluded.media_type,size_bytes=excluded.size_bytes,checksum_sha256=COALESCE(excluded.checksum_sha256,generation_outputs.checksum_sha256)"""
OUTPUT_JOB_SUCCEED = """UPDATE generation_jobs SET status='succeeded',output_url=?,
provider_output_url=NULL,error_code=NULL,message=?,updated_at=?,version=version+1 WHERE job_id=?"""
OUTPUT_EXECUTION_SUCCEED = """UPDATE generation_executions SET status='succeeded',finished_at=?,error_code=NULL
WHERE job_id=? AND attempt_no=(SELECT MAX(attempt_no) FROM generation_executions WHERE job_id=?)"""
OUTPUT_POLL_COMPLETE = """UPDATE generation_poll_tasks SET status='completed',claimed_by=NULL,
claimed_at=NULL,lease_expires_at=NULL,last_error=NULL,completed_at=?,updated_at=?
WHERE task_id=? AND status='processing' AND claimed_by=?"""


POLL_LEASE_RENEW = """UPDATE generation_poll_tasks SET lease_expires_at=?,updated_at=?
WHERE task_id=? AND status='processing' AND phase='persist_output'
AND claimed_by=? AND lease_expires_at>=?"""
