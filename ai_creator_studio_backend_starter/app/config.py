import os
from pathlib import Path

PROVIDER_MODE = os.getenv("PROVIDER_MODE", "mock").strip().lower()
PROVIDER_ROUTING_MODE = os.getenv("PROVIDER_ROUTING_MODE", "MANUAL").strip().upper()
FASHN_API_KEY = os.getenv("FASHN_API_KEY", "")
FASHN_BASE_URL = os.getenv("FASHN_BASE_URL", "https://api.fashn.ai").rstrip("/")
FASHN_MODEL = os.getenv("FASHN_MODEL", "tryon-v1.6").strip().lower()
HTTP_TIMEOUT_SECONDS = float(os.getenv("HTTP_TIMEOUT_SECONDS", "30"))
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "./outputs")).resolve()
MAX_OUTPUT_BYTES = int(os.getenv("MAX_OUTPUT_BYTES", str(25 * 1024 * 1024)))
# Exact host allowlist. Add a host only after verifying it is an official provider output host.
FASHN_OUTPUT_HOSTS = tuple(
    host.strip().lower() for host in os.getenv("FASHN_OUTPUT_HOSTS", "cdn.fashn.ai,media.fashn.ai").split(",") if host.strip()
)
ASSET_STORAGE_DIR = Path(os.getenv("ASSET_STORAGE_DIR", "./private_assets")).resolve()
ASSET_DATABASE_PATH = Path(os.getenv("ASSET_DATABASE_PATH", "./assets.sqlite3")).resolve()
GENERATION_DATABASE_PATH = Path(os.getenv("GENERATION_DATABASE_PATH")).resolve() if os.getenv("GENERATION_DATABASE_PATH") else None
ASSET_MAX_UPLOAD_BYTES = int(os.getenv("ASSET_MAX_UPLOAD_BYTES", str(100 * 1024 * 1024)))
ASSET_PREVIEW_TTL_SECONDS = int(os.getenv("ASSET_PREVIEW_TTL_SECONDS", "300"))
ASSET_SIGNING_SECRET = os.getenv("ASSET_SIGNING_SECRET", "")
# L-04 / D2: image uploads must declare rights (and likeness consent if a person is shown). ON by default; set ASSET_REQUIRE_RIGHTS_CONFIRMATION=0 only for old clients.
def env_flag(value: str | None) -> bool:
    """True only for an explicit opt-in value; unset, empty or unknown text is False."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


def env_flag_default_on(value: str | None) -> bool:
    """True unless the value is an explicit off ("0", "false", "no", "off"); unset or unknown text keeps it ON (fail safe)."""
    return str("1" if value is None else value).strip().lower() not in {"0", "false", "no", "off"}


ASSET_REQUIRE_RIGHTS_CONFIRMATION = env_flag_default_on(os.getenv("ASSET_REQUIRE_RIGHTS_CONFIRMATION"))
# L-02: when true, an authenticated user who has not accepted the current legal document versions is refused (403
# LEGAL_ACCEPTANCE_REQUIRED) on every route except the ones needed to accept, withdraw consent or request deletion. Default off.
LEGAL_REQUIRE_ACCEPTANCE = env_flag(os.getenv("LEGAL_REQUIRE_ACCEPTANCE"))

def asset_api_tokens() -> dict[str, str]:
    """Return configured bearer-token -> user-id mappings; no development token is implicit."""
    result: dict[str, str] = {}
    for entry in os.getenv("ASSET_API_TOKENS", "").split(","):
        if ":" not in entry:
            continue
        token, user_id = entry.split(":", 1)
        if token.strip() and user_id.strip():
            result[token.strip()] = user_id.strip()
    return result

APP_CORS_ORIGINS = tuple(origin.strip() for origin in os.getenv("APP_CORS_ORIGINS", "").split(",") if origin.strip())

# Supabase Auth user endpoint is used to validate browser access tokens. The
# publishable/anon key is safe for this server-side validation call; service-role
# keys are never accepted by the browser application.
SUPABASE_URL = os.getenv("SUPABASE_URL", "").strip().rstrip("/")
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY", "").strip()

def _non_negative_int(name: str, default: int) -> int:
    raw = os.getenv(name, str(default)).strip()
    if raw == "":
        return default
    try:
        value = int(raw)
    except ValueError as exc:
        raise ValueError(f"{name} must be a non-negative integer, got {raw!r}") from exc
    if value < 0:
        raise ValueError(f"{name} must be a non-negative integer, got {raw!r}")
    return value


# Cost control: maximum generation jobs a workspace may create per UTC day. 0 = unlimited (default, backward compatible).
GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE = _non_negative_int("GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE", 0)

# Deep health thresholds (GET /internal/ops/health). BACKUP_DIR is optional: where backup_restore.py writes backups.
HEALTH_DISK_WARN_FREE_PERCENT = _non_negative_int("HEALTH_DISK_WARN_FREE_PERCENT", 15)
HEALTH_DISK_FAIL_FREE_PERCENT = _non_negative_int("HEALTH_DISK_FAIL_FREE_PERCENT", 5)
HEALTH_BACKUP_MAX_AGE_HOURS = _non_negative_int("HEALTH_BACKUP_MAX_AGE_HOURS", 26)
BACKUP_DIR = Path(os.getenv("BACKUP_DIR")).resolve() if os.getenv("BACKUP_DIR", "").strip() else None
# Access log (L-05). ACCESS_LOG_DIR set -> a daily-rotating file kept for ACCESS_LOG_RETENTION_DAYS days; unset -> stdout.
# The retention default is a placeholder, not a legal decision. ACCESS_LOG_ACTOR: hash (default) | plain | none.
ACCESS_LOG_ENABLED = os.getenv("ACCESS_LOG_ENABLED", "true").strip().lower() not in {"0", "false", "no", "off"}
ACCESS_LOG_DIR = Path(os.getenv("ACCESS_LOG_DIR")).resolve() if os.getenv("ACCESS_LOG_DIR", "").strip() else None
ACCESS_LOG_RETENTION_DAYS = _non_negative_int("ACCESS_LOG_RETENTION_DAYS", 30)
if ACCESS_LOG_DIR is not None and ACCESS_LOG_RETENTION_DAYS < 1:
    raise ValueError("ACCESS_LOG_RETENTION_DAYS must be at least 1 when ACCESS_LOG_DIR is set (0 would keep every file forever)")
ACCESS_LOG_ACTOR = os.getenv("ACCESS_LOG_ACTOR", "hash").strip().lower()
if ACCESS_LOG_ACTOR not in {"hash", "plain", "none"}:
    raise ValueError("ACCESS_LOG_ACTOR must be hash, plain or none")
ACCESS_LOG_CLIENT_IP = env_flag(os.getenv("ACCESS_LOG_CLIENT_IP"))

WORKER_STALE_AFTER_SECONDS = int(os.getenv("WORKER_STALE_AFTER_SECONDS", "30"))

# Durable provider polling worker controls. Backoff is bounded; Retry-After is honored only from verified response headers.
POLL_WORKER_POLL_SECONDS = float(os.getenv("POLL_WORKER_POLL_SECONDS", "1.0"))
POLL_WORKER_LEASE_SECONDS = int(os.getenv("POLL_WORKER_LEASE_SECONDS", "90"))
POLL_RETRY_BASE_SECONDS = float(os.getenv("POLL_RETRY_BASE_SECONDS", "2"))
POLL_RETRY_MAX_SECONDS = float(os.getenv("POLL_RETRY_MAX_SECONDS", "300"))
POLL_RETRY_MAX_ATTEMPTS = int(os.getenv("POLL_RETRY_MAX_ATTEMPTS", "12"))
POLL_RETRY_AFTER_MAX_SECONDS = float(os.getenv("POLL_RETRY_AFTER_MAX_SECONDS", "900"))

# Operations monitor / alerting. Webhook delivery is disabled unless an HTTPS URL is configured.
OPS_MONITOR_POLL_SECONDS = float(os.getenv("OPS_MONITOR_POLL_SECONDS", "5"))
OPS_ALERT_WORKER_STALE_SECONDS = int(os.getenv("OPS_ALERT_WORKER_STALE_SECONDS", "45"))
OPS_ALERT_QUEUE_AGE_SECONDS = int(os.getenv("OPS_ALERT_QUEUE_AGE_SECONDS", "120"))
OPS_ALERT_WEBHOOK_URL = os.getenv("OPS_ALERT_WEBHOOK_URL", "").strip()
OPS_ALERT_WEBHOOK_TOKEN = os.getenv("OPS_ALERT_WEBHOOK_TOKEN", "").strip()
OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS = float(os.getenv("OPS_ALERT_WEBHOOK_TIMEOUT_SECONDS", "5"))
OPS_ALERT_WEBHOOK_MAX_ATTEMPTS = int(os.getenv("OPS_ALERT_WEBHOOK_MAX_ATTEMPTS", "8"))
REQUIRED_WORKER_TYPES = tuple(x.strip() for x in os.getenv("REQUIRED_WORKER_TYPES", "outbox,provider_poll,output_asset_link").split(",") if x.strip())

# Explicit platform-level operator allowlist. Empty by default; tenant admins are not global ops admins.
OPS_ADMIN_USER_IDS = tuple(x.strip() for x in os.getenv("OPS_ADMIN_USER_IDS", "").split(",") if x.strip())

# Runtime storage selection is explicit. PostgreSQL remains disabled until its
# adapter passes the live integration gate; no DSN-based implicit switching.
DATABASE_BACKEND = os.getenv("DATABASE_BACKEND", "sqlite").strip().lower()
DATABASE_URL = os.getenv("DATABASE_URL", "").strip()
