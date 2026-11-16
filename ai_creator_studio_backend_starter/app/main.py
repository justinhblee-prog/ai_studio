import hashlib
import json
import uuid
from typing import Any
from app.viewer_responses import ManifestExportResponse
from fastapi import Depends, FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, PlainTextResponse
from app.private_file_response import PrivateFileError, open_private_file_response
from pydantic import BaseModel, ConfigDict, Field
from app import config, job_repository
from app.repositories.job_limits import DailyJobLimitExceeded
from app.access_log import AccessLogMiddleware, configure_access_log
from app.ai_disclosure import disclose_job_outputs, is_ai_generated_provider
from app.deep_health import run_deep_health
from app.schemas import CreateTryOnJob, JobResponse, EngineInfo, ReconcileProviderSubmission, RetryPollTaskRequest, CancelGenerationJobRequest
from app.providers.mock import MockProvider
from app.providers.fashn import FashnProvider
from app.provider_registry import list_capabilities, resolve_manual, resolve_routing, ProviderPolicyError
from app.output_store import save_provider_output, get_stored_output, OutputStoreError
from app.job_state import InvalidJobTransition
from app.dependencies import (get_job_repository, get_event_repository, get_job_lifecycle_service,
    get_poll_task_admin_repository, get_outbox_admin_repository, get_worker_health_repository,
    get_operations_monitoring_repository, get_operations_alert_read_repository,
    get_job_diagnostics_repository)
from app.repositories.job import JobRepository
from app.repositories.event import EventRepository
from app.assets.routes import router as assets_router, current_user, require_role
from app.moderation import router as moderation_router
from app.workspaces import router as workspaces_router
from app.characters import router as characters_router
from app.projects import router as projects_router
from app.legal import router as legal_router
from app.library_routes import router as library_router
from app.features_routes import router as features_router
from app.external_notice import router as external_notice_router
from app.usage import router as usage_router
from app.ops_overview import router as ops_overview_router
from app.photo_engine import router as photo_drafts_router
from app.photo_steps_routes import router as photo_steps_router
from app.photo_presets import router as photo_presets_router
from app.workspace_library import router as workspace_library_router
from app.model_drafts import router as model_drafts_router
from app.lookbook import router as lookbook_drafts_router
from app.products import router as products_router
from app.project_products import router as project_products_router
from app.platform_readiness import build_platform_readiness

class OutputAssetLinkRetryInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    reason: str = Field(min_length=1, max_length=2000)


class OutputReviewInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)
    comment: str = Field(default="", max_length=2000)


class GeneratedOutputItemResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    id: str
    job_id: str
    mime_type: str
    size_bytes: int
    created_at: str
    checksum_sha256: str | None = None
    asset_link_status: str
    asset_id: str | None = None
    asset_version_id: str | None = None
    provenance_record_id: str | None = None
    is_ai_generated: bool | None = None
    provider: str | None = None
    model: str | None = None


class GeneratedOutputListResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    data: list[GeneratedOutputItemResponse]
    meta: dict[str, Any]


class GeneratedOutputReviewEventResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    event_id: str
    output_id: str
    job_id: str
    actor_id: str
    decision: str
    comment: str
    asset_id: str
    asset_version_id: str
    provenance_id: str
    checksum_sha256: str
    created_at: str


class GeneratedOutputReviewDetailResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    output_id: str
    job_id: str
    media_type: str
    size_bytes: int
    created_at: str
    provider: str | None = None
    model: str | None = None
    asset_link_status: str
    asset_id: str | None = None
    asset_version_id: str | None = None
    provenance_id: str | None = None
    checksum_sha256: str | None = None
    is_ai_generated: bool | None = None


class GeneratedOutputReviewResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    output: GeneratedOutputReviewDetailResponse
    status: str
    latest_decision: GeneratedOutputReviewEventResponse | None = None
    events: list[GeneratedOutputReviewEventResponse]
    job_status: str


app = FastAPI(title="AI CREATOR STUDIO API", version="0.7.0")
configure_access_log()
app.add_middleware(AccessLogMiddleware)
app.include_router(assets_router)
app.include_router(workspaces_router)
app.include_router(characters_router)
app.include_router(projects_router)
app.include_router(legal_router)
app.include_router(library_router)
app.include_router(features_router)
app.include_router(external_notice_router)
app.include_router(usage_router)
app.include_router(ops_overview_router)
app.include_router(moderation_router)
app.include_router(photo_drafts_router)
app.include_router(photo_steps_router)
app.include_router(photo_presets_router)
app.include_router(workspace_library_router)
app.include_router(model_drafts_router)
app.include_router(lookbook_drafts_router)
app.include_router(products_router)
app.include_router(project_products_router)
if config.APP_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(config.APP_CORS_ORIGINS),
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "Idempotency-Key"],
        expose_headers=["Content-Disposition"],
    )
# Durable SQLite persistence for jobs/executions/events/output metadata/idempotency.
# Workspace membership and asset metadata remain in their existing asset store.
jobs: dict[str, dict[str, Any]] = {}  # compatibility shim for older local tooling; not authoritative
idempotency: dict[str, str] = {}      # compatibility shim; not authoritative
get_job_repository().initialize()
config.OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

def get_provider():
    provider_id = config.PROVIDER_MODE
    model_id = "mock-tryon" if provider_id == "mock" else config.FASHN_MODEL
    try:
        # Mock remains available for flow verification only. Real providers are
        # blocked until their capability reaches production eligibility.
        if provider_id == "mock":
            if config.PROVIDER_ROUTING_MODE != "MANUAL":
                resolve_routing(config.PROVIDER_ROUTING_MODE, provider_id, model_id)
            resolve_manual(provider_id, model_id, purpose="test")
            return MockProvider()
        resolve_routing(config.PROVIDER_ROUTING_MODE, provider_id, model_id)
        if provider_id == "fashn":
            return FashnProvider()
        raise ProviderPolicyError("UNSUPPORTED_PROVIDER", "Unsupported provider.", 422)
    except ProviderPolicyError as exc:
        raise HTTPException(status_code=exc.status_code, detail={"code": exc.code, "message": str(exc)}) from exc
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail="Provider is not configured.") from exc



def get_provider_for_job(job: dict[str, Any]):
    """Resolve the exact provider/model persisted on the Job; never silently reroute."""
    selected_provider = config.PROVIDER_MODE
    selected_model = "mock-tryon" if selected_provider == "mock" else config.FASHN_MODEL
    if job.get("provider") != selected_provider or job.get("model") != selected_model:
        raise RuntimeError("Worker provider/model configuration does not match the persisted Job.")
    return get_provider()


def public_job(job: dict[str, Any]) -> JobResponse:
    return JobResponse(**{k: v for k, v in job.items() if k in JobResponse.model_fields})


def require_platform_ops(user_id: str) -> None:
    if user_id not in config.OPS_ADMIN_USER_IDS:
        raise HTTPException(status_code=403, detail="Platform operations role required")

@app.get("/health")
async def health():
    """Public liveness endpoint; operational topology and queue details stay private."""
    return {"ok": True, "version": app.version}


@app.get("/v1/auth/me")
async def authenticated_identity(user_id: str = Depends(current_user)):
    """Return the identity validated by the configured authentication provider."""
    return {"user_id": user_id}

@app.get("/v1/engines/capabilities")
async def list_provider_capabilities():
    return {"registry_version": "2026-11-02.1", "routing_mode": config.PROVIDER_ROUTING_MODE,
            "items": list_capabilities()}

@app.get("/internal/ops/runtime-readiness")
async def runtime_readiness_diagnostics(user_id: str = Depends(current_user)):
    """Read-only integration readiness; restricted to platform operators."""
    require_platform_ops(user_id)
    return build_platform_readiness()


@app.get("/internal/ops/health")
async def deep_health_diagnostics(user_id: str = Depends(current_user)):
    """Deep health (database, storage, disk, workers, backup); 503 when any check fails. Platform operators only."""
    require_platform_ops(user_id)
    report = run_deep_health()
    return JSONResponse(report, status_code=503 if report["status"] == "fail" else 200)


@app.get("/internal/ops/provider-registry")
async def provider_registry_diagnostics(user_id: str = Depends(current_user)):
    require_platform_ops(user_id)
    return {"registry_version": "2026-11-02.1", "routing_mode": config.PROVIDER_ROUTING_MODE,
            "selected_provider": config.PROVIDER_MODE, "items": list_capabilities()}

@app.get("/v1/engines/models", response_model=list[EngineInfo])
async def list_models():
    configured = bool(config.FASHN_API_KEY)
    return [
        EngineInfo(provider="mock", model="mock-tryon", mode="demo", configured=True,
                   note="Flow test only; does not generate an image."),
        EngineInfo(provider="fashn", model="tryon-v1.6", mode="async", configured=configured,
                   note="Lower-latency virtual try-on; model-controlled output resolution."),
        EngineInfo(provider="fashn", model="tryon-max", mode="async", configured=configured,
                   note="Higher-fidelity e-commerce output; supports 1k/2k/4k resolution tiers."),
    ]

@app.post("/v1/generation-jobs", response_model=JobResponse, status_code=202)
async def create_job(body: CreateTryOnJob, idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"), user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    require_role(body.workspace_id, user_id, {"owner", "admin", "editor"})
    payload = body.model_dump(mode="json")
    payload_hash = hashlib.sha256(json.dumps(payload, sort_keys=True).encode()).hexdigest()
    if idempotency_key:
        existing = repository.get_idempotent(body.workspace_id, idempotency_key)
        if existing:
            existing_job, existing_hash = existing
            if existing_hash != payload_hash:
                raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request body.")
            return public_job(existing_job)

    provider = get_provider()
    from app import tryon_inputs
    try:   # R-046: library items are resolved now only to refuse a bad pick at once; the stored payload keeps just the item ids
        checked = tryon_inputs.resolve_payload(payload, for_provider=False, user_id=user_id)
    except tryon_inputs.TryOnInputError as exc:
        raise HTTPException(status_code=exc.status, detail={"code": exc.code, "message": str(exc)}) from exc
    try:
        validator = getattr(provider, "validate_request", None)
        if callable(validator):
            validator(checked)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail={"code": "VALIDATION_ERROR", "message": str(exc)}) from exc
    if provider.name != "mock" and config.EXTERNAL_NOTICE_REQUIRED:
        from app.external_notice import acknowledged
        if not acknowledged(body.workspace_id, user_id, provider.name):
            from app.provider_registry import data_policy
            raise HTTPException(status_code=409, detail={"code": "EXTERNAL_NOTICE_REQUIRED", "provider": provider.name,
                "data_policy": data_policy(provider.name),
                "message": "Acknowledge that photos are sent to the external AI service before starting this job."})
    job_id = "job_" + uuid.uuid4().hex
    job = {
        "job_id": job_id, "workspace_id": body.workspace_id, "owner_id": user_id,
        "status": "queued", "provider": provider.name,
        "model": getattr(provider, "model", "mock-tryon"), "provider_request_id": None,
        "output_url": None, "error_code": None, "message": None,
        "payload_hash": payload_hash, "payload": payload, "provider_output_url": None,
    }
    from app.cost_cap import CostCapExceeded
    try:
        persisted, created = repository.create(job, idempotency_key, daily_job_limit=config.GENERATION_DAILY_JOB_LIMIT_PER_WORKSPACE or None)
    except CostCapExceeded as exc:
        raise HTTPException(status_code=429, detail={"code": exc.code, "message": exc.message, **exc.extra}) from exc
    except DailyJobLimitExceeded as exc:
        raise HTTPException(status_code=429, headers={"Retry-After": str(exc.retry_after_seconds)}, detail={
            "code": "DAILY_JOB_LIMIT_EXCEEDED", "message": str(exc), "limit": exc.limit, "used": exc.used}) from exc
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Job persistence is temporarily unavailable.") from exc
    if not created:
        if persisted["payload_hash"] != payload_hash:
            raise HTTPException(status_code=409, detail="Idempotency-Key was already used with a different request body.")
        return public_job(persisted)
    # The Job + SUBMIT_GENERATION outbox event were committed atomically.
    # A separate worker performs provider dispatch; API requests never launch it inline.
    return public_job(persisted)

@app.get("/v1/generation-jobs", response_model=list[JobResponse])
async def list_generation_jobs(
    workspace_id: str,
    limit: int = 50,
    offset: int = 0,
    user_id: str = Depends(current_user),
    repository: JobRepository = Depends(get_job_repository),
):
    if limit < 1 or limit > 100 or offset < 0:
        raise HTTPException(status_code=422, detail="limit must be 1..100 and offset must be non-negative")
    require_role(workspace_id, user_id, {"owner", "admin", "editor", "viewer"})
    return [public_job(item) for item in repository.list_for_workspace(
        workspace_id, limit=limit, offset=offset
    )]


@app.post("/v1/generation-jobs/{job_id}/cancel", response_model=JobResponse)
async def cancel_generation_job(
    job_id: str,
    body: CancelGenerationJobRequest | None = None,
    user_id: str = Depends(current_user),
    repository: JobRepository = Depends(get_job_repository),
):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor"})
    reason = body.reason if body else None
    try:
        return public_job(repository.cancel_queued(job_id, actor_id=user_id, reason=reason))
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Job not found") from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail="Job cancellation is not supported by this repository") from exc


@app.get("/v1/generation-jobs/{job_id}", response_model=JobResponse)
async def get_job(job_id: str, user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    """Read-only Job status. Provider polling and output persistence run in poll_worker."""
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    return public_job(job)

@app.get("/v1/generation-jobs/{job_id}/executions", operation_id="listGenerationJobExecutions")
async def get_job_executions(job_id: str, limit: int = 20, cursor: str | None = None,
                             user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    if limit < 1 or limit > 100:
        raise HTTPException(status_code=422, detail="limit must be 1..100")
    try:
        return repository.list_executions(job_id, limit=limit, cursor=cursor)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail="Execution history is not supported by this repository") from exc


@app.get("/v1/generation-jobs/{job_id}/outputs", operation_id="listGenerationJobOutputs", response_model=GeneratedOutputListResponse)
async def get_job_outputs(job_id: str,
                          user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    if job.get("status") != "succeeded":
        return {"data": [], "meta": {}}
    try:
        return disclose_job_outputs(repository.list_outputs(job_id), job)
    except NotImplementedError as exc:
        raise HTTPException(status_code=501, detail="Output history is not supported by this repository") from exc


@app.post("/v1/generation-jobs/{job_id}/outputs/{output_id}/asset-link-retry", operation_id="retryGenerationJobOutputAssetLink")
async def retry_job_output_asset_link(job_id: str, output_id: str, body: OutputAssetLinkRetryInput,
                                      user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin"})
    reason = body.reason.strip()
    if not reason:
        raise HTTPException(status_code=422, detail="reason is required")
    from app.repositories.output_asset_link import build_output_asset_link_repository
    link_repository = build_output_asset_link_repository()
    try:
        result = link_repository.retry_failed(job_id, output_id, user_id, reason)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None: raise HTTPException(status_code=404, detail="Output Asset link not found")
    return result


@app.get("/v1/generation-jobs/{job_id}/outputs/{output_id}/asset-link-events", operation_id="listGenerationJobOutputAssetLinkEvents")
async def get_job_output_asset_link_events(job_id: str, output_id: str,
                                           user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job: raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin"})
    from app.repositories.output_asset_link import build_output_asset_link_repository
    link_repository = build_output_asset_link_repository()
    if not link_repository.has_link(job_id, output_id):
        raise HTTPException(status_code=404, detail="Output Asset link not found")
    events = link_repository.list_link_events(job_id, output_id)
    return {"items": events, "total": len(events)}


@app.get("/v1/generation-jobs/{job_id}/outputs/{output_id}/review", operation_id="getGenerationJobOutputReview", response_model=GeneratedOutputReviewResponse)
async def get_job_output_review(job_id: str, output_id: str,
                                user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    from app.repositories.output_review import build_output_review_repository
    result = build_output_review_repository().get_review(job_id, output_id)
    if result is None:
        raise HTTPException(status_code=404, detail="Generated Output not found")
    result.pop("workspace_id", None)
    result["output"]["is_ai_generated"] = is_ai_generated_provider(result["output"].get("provider"))
    return result


async def _decide_job_output_review(job_id: str, output_id: str, body: OutputReviewInput,
                                    decision: str, user_id: str, repository: JobRepository):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin"})
    from app.repositories.output_review import build_output_review_repository
    try:
        result = build_output_review_repository().decide(
            job_id, output_id, job["workspace_id"], user_id, decision, body.comment)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Generated Output not found")
    result.pop("workspace_id", None)
    if decision == "approved":   # R-046: only an APPROVED result is delivered into "my library" (as a render item, origin ai)
        from app.workspace_library import file_generated_output
        file_generated_output(job["workspace_id"], (result.get("output") or {}).get("asset_id"), user_id, f"결과 {job_id[-6:]}")
    return result


@app.post("/v1/generation-jobs/{job_id}/outputs/{output_id}/review/approve", operation_id="approveGenerationJobOutput", response_model=GeneratedOutputReviewResponse)
async def approve_job_output(job_id: str, output_id: str, body: OutputReviewInput,
                             user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    return await _decide_job_output_review(job_id, output_id, body, "approved", user_id, repository)


@app.post("/v1/generation-jobs/{job_id}/outputs/{output_id}/review/request-changes", operation_id="requestGenerationJobOutputChanges", response_model=GeneratedOutputReviewResponse)
async def request_job_output_changes(job_id: str, output_id: str, body: OutputReviewInput,
                                      user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    return await _decide_job_output_review(job_id, output_id, body, "changes_requested", user_id, repository)


@app.post("/v1/generation-jobs/{job_id}/outputs/{output_id}/review/reject", operation_id="rejectGenerationJobOutput", response_model=GeneratedOutputReviewResponse)
async def reject_job_output(job_id: str, output_id: str, body: OutputReviewInput,
                            user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    return await _decide_job_output_review(job_id, output_id, body, "rejected", user_id, repository)


@app.post("/v1/generation-jobs/{job_id}/outputs/export-manifest", operation_id="createGenerationJobOutputExportManifest", response_model=ManifestExportResponse)
async def create_job_output_export_manifest(job_id: str,
                                            user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor"})
    from app.repositories.output_review import build_output_review_repository
    try:
        result = build_output_review_repository().create_export_manifest(job_id, job["workspace_id"], user_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    if result is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return result


@app.get("/v1/generation-jobs/{job_id}/events")
async def get_job_events(job_id: str, user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository), diagnostics = Depends(get_job_diagnostics_repository)):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    return diagnostics.get(job_id)


@app.post("/v1/generation-jobs/{job_id}/reconciliation", response_model=JobResponse)
async def reconcile_provider_submission(job_id: str, body: ReconcileProviderSubmission, user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository), outbox_admin=Depends(get_outbox_admin_repository)):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin"})
    if body.action == "attach_request_id" and not body.provider_request_id:
        raise HTTPException(status_code=422, detail="provider_request_id is required for attach_request_id")
    if body.action == "confirm_not_submitted" and body.provider_request_id:
        raise HTTPException(status_code=422, detail="provider_request_id must be omitted for confirm_not_submitted")
    try:
        resolved = outbox_admin.reconcile_unknown_submission(
            job_id, action=body.action, actor_id=user_id, reason=body.reason,
            provider_request_id=body.provider_request_id)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return public_job(resolved)

@app.get("/internal/ops/poll-tasks")
async def list_workspace_poll_tasks(workspace_id: str, status: str | None = None,
                                    limit: int = 100, user_id: str = Depends(current_user), repository = Depends(get_poll_task_admin_repository)):
    require_role(workspace_id, user_id, {"owner", "admin"})
    allowed_statuses = {"pending", "processing", "completed", "needs_reconciliation"}
    if status is not None and status not in allowed_statuses:
        raise HTTPException(status_code=422, detail="Unsupported poll task status.")
    return {"workspace_id": workspace_id,
            "items": repository.list_for_workspace(workspace_id, status=status, limit=limit)}


@app.post("/internal/ops/poll-tasks/{task_id}/retry")
async def retry_workspace_poll_task(task_id: str, body: RetryPollTaskRequest,
                                    user_id: str = Depends(current_user), repository = Depends(get_poll_task_admin_repository)):
    require_role(body.workspace_id, user_id, {"owner", "admin"})
    try:
        return repository.retry(task_id, body.workspace_id, actor_id=user_id, reason=body.reason)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Poll task not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@app.get("/internal/ops/workers")
async def get_worker_health(user_id: str = Depends(current_user), repository = Depends(get_worker_health_repository)):
    require_platform_ops(user_id)
    return repository.worker_health(config.WORKER_STALE_AFTER_SECONDS)


@app.get("/internal/ops/metrics", response_class=PlainTextResponse)
async def get_operational_metrics(user_id: str = Depends(current_user), repository = Depends(get_operations_monitoring_repository)):
    require_platform_ops(user_id)
    from app.services.prometheus_metrics import render_operational_metrics
    snapshot = repository.snapshot(config.WORKER_STALE_AFTER_SECONDS)
    return PlainTextResponse(render_operational_metrics(snapshot), media_type="text/plain; version=0.0.4; charset=utf-8")


@app.get("/internal/ops/alerts")
async def get_operational_alerts(status: str = "active", limit: int = 100,
                                user_id: str = Depends(current_user),
                                monitoring = Depends(get_operations_monitoring_repository),
                                alerts = Depends(get_operations_alert_read_repository)):
    require_platform_ops(user_id)
    if status not in {"active", "resolved"}:
        raise HTTPException(status_code=422, detail="Unsupported alert status")
    snapshot = monitoring.snapshot(config.OPS_ALERT_WORKER_STALE_SECONDS)
    return {"snapshot": snapshot, "items": alerts.list_alerts(status=status, limit=limit)}

@app.get("/v1/generation-jobs/{job_id}/output")
async def get_job_output(job_id: str, user_id: str = Depends(current_user), repository: JobRepository = Depends(get_job_repository)):
    job = repository.get(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    require_role(job["workspace_id"], user_id, {"owner", "admin", "editor", "viewer"})
    if job.get("status") != "succeeded" or not job.get("output_url"):
        raise HTTPException(status_code=404, detail="Output not found")
    output_record = job_repository.get_output(job_id)
    if not output_record or not output_record.get("storage_key"):
        raise HTTPException(status_code=404, detail="Output not found")
    path = get_stored_output(job_id, output_record["storage_key"])
    if path is None:
        raise HTTPException(status_code=404, detail="Output not found")
    media_type = {".png": "image/png", ".jpg": "image/jpeg", ".webp": "image/webp"}.get(path.suffix, "application/octet-stream")
    try:
        return open_private_file_response(path, media_type=media_type, filename=path.name,
            expected_size=output_record.get("size_bytes"), expected_sha256=output_record.get("checksum_sha256"), inline=True)
    except PrivateFileError as exc:
        raise HTTPException(status_code=409, detail="Output file failed descriptor integrity validation") from exc
