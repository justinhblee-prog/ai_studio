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
# L-04: when true, image uploads must declare rights (and likeness consent if a person is shown). Default off keeps old clients working.
def env_flag(value: str | None) -> bool:
    """True only for an explicit opt-in value; unset, empty or unknown text is False."""
    return str(value or "").strip().lower() in {"1", "true", "yes", "on"}


ASSET_REQUIRE_RIGHTS_CONFIRMATION = env_flag(os.getenv("ASSET_REQUIRE_RIGHTS_CONFIRMATION"))

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
