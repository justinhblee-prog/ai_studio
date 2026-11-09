"""Application-facing Output repository contract."""
from __future__ import annotations
from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class OutputRepository(Protocol):
    def get(self, job_id: str) -> dict[str, Any] | None: ...
    def record(self, job_id: str, storage_key: str, media_type: str, size_bytes: int) -> dict[str, Any]: ...
    def finalize_success(self, task_id: str, worker_id: str, job_id: str, **kwargs: Any) -> bool: ...
