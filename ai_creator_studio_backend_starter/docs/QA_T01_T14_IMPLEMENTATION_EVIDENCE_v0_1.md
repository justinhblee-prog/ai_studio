# AI CREATOR STUDIO — T-01~T-14 Implementation Evidence Crosswalk v0.1

- 기준: `AI_CREATOR_STUDIO_requirements_traceability_matrix_v1_0.md`
- 코드 기준: BUILD-00086
- 검증 실행: Backend pytest 272 passed (BUILD-00086 local SQLite test run)
- 목적: 기존 QA ID의 의미를 변경하지 않고 현재 자동화 테스트가 증명하는 범위와 미증명 범위를 구분한다.
- 주의: 이 문서는 전체 QA Gate PASS 선언이 아니다. 테스트 함수의 존재와 SQLite 단위/통합 테스트 PASS는 실 Provider, 실 PostgreSQL, 브라우저 E2E, 프로세스 종료 장애 또는 PO 승인 증거를 대체하지 않는다.

## 1. Original QA ID status

| Original ID | Scenario (preserved) | Current code/test evidence | Evidence status | Remaining proof / blocker |
|---|---|---|---|---|
| T-01 | Login then Organization/Workspace access | `tests/test_api.py`: `test_generation_requires_authentication`, `test_generation_requires_workspace_membership`, `test_viewer_cannot_create_generation_job`, `test_job_read_is_workspace_scoped`; `tests/test_assets_api.py`: role/access tests | PARTIAL | Organization membership / org-level isolation and full identity integration are not established by this test set. |
| T-02 | Valid image upload and completion | `tests/test_assets_api.py`: `test_upload_metadata_preview_and_delete`; current verified fixture is a GLB model asset | PARTIAL / NOT EQUIVALENT | Original image upload scenario, image formats, image-specific metadata and complete original acceptance criteria need dedicated tests. |
| T-03 | Invalid MIME/signature/oversized upload | `tests/test_asset_validation.py`: fake GLB signature, unsupported extension, oversized bytes; `tests/test_assets_api.py`: bad GLB and upload size limit | PARTIAL | Explicit MIME-vs-content signature mismatch matrix for the original image upload scenario remains unproven. |
| T-04 | Request another Organization's asset/job ID | Workspace isolation tests return 404/deny cross-workspace access | PARTIAL | Cross-Organization access requires Organization model/membership fixtures and explicit org-boundary assertions. |
| T-05 | Create Job after valid Quote | Job creation, idempotency and Outbox tests exist; Credit Quote/RESERVE does not | NOT IMPLEMENTED / BLOCKED | Credit Quote, account policy, RESERVE and same-transaction Job/Execution/Outbox/Ledger are absent. |
| T-06 | Create Job with insufficient credits | No authoritative Credit Ledger or insufficient-credit path exists | NOT IMPLEMENTED / BLOCKED | Need Credit Account, quote, ledger, account-scope/unit policy and insufficient-balance test. |
| T-07 | Provider success and result persistence | `tests/test_api.py`: fake-provider success, poll success, private output and output persistence recovery tests; `tests/test_concurrent_claims.py`: atomic output finalization | PARTIAL | No live Provider call has been executed; the cost-gated sandbox harness is available but awaits explicit cost authorization, FASHN credentials and authorized test assets. Production rights/cost evidence, AssetVersion linkage, and Credit CAPTURE remain absent. |
| T-08 | Repeat request with same Idempotency Key | `test_idempotency_replays_same_body`, `test_idempotency_rejects_different_body`, `test_idempotency_is_workspace_scoped`, durable SQLite replay/concurrency tests | PARTIAL | Job idempotency is tested; duplicate Credit RESERVE/ledger effects cannot be verified until Credit Ledger exists. |
| T-09 | Provider timeout and unknown outcome | `test_worker_dispatch_failure_is_not_automatically_retried`, lease-expiry quarantine, manual reconciliation tests, Outbox rollback tests | PARTIAL | No real network timeout/remote acceptance ambiguity or provider-side lookup contract test. Current mock/fake tests do not prove remote Provider behavior. |
| T-10 | Cancel while execution is running | Provider capability schema mentions cancellation support, but no Job cancel API/workflow or cancel tests were found | NOT IMPLEMENTED / BLOCKED | Need internal-vs-Provider cancellation state machine, race tests, audit Event, and credit compensation rules. |
| T-11 | Compare original and generated result | Asset upload/preview/delete and Output persistence exist; no original/result comparison workflow or AssetVersion relation test was found | NOT IMPLEMENTED / BLOCKED | Need immutable original + generated AssetVersion linkage and comparison UI/API evidence. |
| T-12 | Inspect failure/retry/fallback history | Poll retry/backoff, retry budget exhaustion, operator review, manual reconciliation, Provider policy tests exist | PARTIAL | No complete retry/fallback history for live providers; AUTO routing is disabled and MANUAL must not silently fallback. |
| T-13 | Failure after DB commit but before Queue publish | Job/Idempotency/Outbox same-transaction failure injection and durable Outbox worker tests exist | PARTIAL | Current design polls durable SQLite Outbox; no external Queue publish boundary/process-kill test for commit-success/publish-not-done. |
| T-14 | Provider success followed by output storage failure | `test_t14_output_persistence_failure_keeps_job_pending_then_recovers`; atomic Output finalization success/failure rollback tests | PARTIAL | No real provider process crash/storage host failure and no Credit CAPTURE/settlement reconciliation. |

## 2. Test evidence added after v0.52

| Version | Added verification | Backend pytest total |
|---|---|---:|
| v0.53 | Prometheus metrics label escaping and empty snapshot | 178 |
| v0.54 | Operations Worker bypasses legacy alert evaluation | 179 |
| v0.55 | Operations API health/metrics/alerts use dedicated DI | 180 |
| v0.56 | Alert + delivery insert rollback together | 181 |
| v0.57 | Outbox/Poll heartbeat bypass legacy facade | 182 |
| v0.58 | Health and diagnostics repository DI; broad Job `__getattr__` bridge removed | 184 |
| v0.59 | Legacy Job facade has no embedded SQL | 186 |
| v0.60 | Compatibility repository composes aggregate ports | 187 |
| v0.61 | Default Job/Event UoW reconciliation uses Outbox Admin repository | 188 |
| v0.62 | Runtime import boundary cleanup | 189 |
| v0.63 | Full `app/` legacy import audit | 190 |
| v0.64 | Repository Protocol return types aligned | 191 |
| v0.65 | Outbox submit/unknown-outcome Event failure rollback | 193 |
| v0.66 | Poll success handoff Event failure rollback | 194 |
| v0.67 | Both manual reconciliation actions Event failure rollback | 196 |
| v0.68 | Poll retry-exhaustion Event failure rollback | 197 |

| BUILD-00084 | Subprocess hard-exit before Output atomic rename; stale hidden temp dry-run/apply recovery and unrelated-temp preservation | 257 |
| BUILD-00085 | Cost-gated opt-in live FASHN smoke harness preflight; no Provider call executed in this environment | 261 |
| BUILD-00086 | Project RBAC CRUD and workspace-scoped paginated Job listing; product/API scope audit | 272 |

## 3. Gate status — not promoted by this report

| Gate | Status | Reason |
|---|---|---|
| G0 | PARTIAL / EVIDENCE PENDING | Archive/source tests exist, but complete repository/branch/commit provenance and required G0 evidence package are not established here. |
| G1 | NOT VERIFIED | Viewer static source validation 19/19 is not GLB 3-model browser runtime, scene save/restore, performance or responsive evidence. |
| G2 | NOT VERIFIED | No live Provider request/response, request ID, output quality, cost/latency, or rights evidence. The opt-in harness is a preparation tool only and has not been run. |
| G3 | NOT VERIFIED | Credit Quote/Ledger and several original T scenarios (T-05, T-06, T-10, T-11) remain incomplete. |
| G4 | NOT VERIFIED | Independent Photo Engine quality/cost/rights dataset and evaluation not run. |
| G5 | NOT VERIFIED | No paid pilot/customer contract, local legal/rights/support/refund evidence. |

## 4. Constraints retained

- T-01 through T-14 identifiers and scenario meanings are unchanged.
- No Gate is marked PASS by this code-level test audit.
- Backend pytest totals are local SQLite test evidence only; they do not prove PostgreSQL, multi-host or production behavior.
- PostgreSQL runtime adapter remains unimplemented and backend selection fails closed.
- Credit Quote/Ledger remains unimplemented; the DB-neutral Credit Ledger spec has unresolved PO decisions (Organization vs Workspace account scope, unit precision, expiry/lot policy, partial capture, and refund semantics).
- Provider UNKNOWN must remain quarantined for reconciliation; no blind replay or release.
- Job SUCCEEDED remains gated on persisted Output and DB reference; Credit CAPTURE is not yet implemented.
