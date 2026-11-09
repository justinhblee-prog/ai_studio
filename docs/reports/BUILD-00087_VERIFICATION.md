# BUILD-00087 Verification Report

| Check | Result | Boundary / notes |
|---|---|---|
| Backend pytest | PASS — 276 passed | SQLite/local filesystem; includes four queued-cancellation tests |
| Python compileall | PASS | `app`, `scripts`, `tests` |
| Viewer structural validation | PASS — 19/19 | Source-level checks only; not browser/WebGL runtime evidence |
| OpenAPI route inventory | PASS — audit executed, exact match false | Design-only 5, runtime-only 17, method gaps 3; cancellation route now matches |
| Queued cancellation API | PASS | Pre-dispatch pending outbox only; RBAC, atomic Job/Execution/Outbox/Event updates and 409 race guard tested |
| Live FASHN generation | NOT RUN | API key, authorized input URLs and explicit cost consent absent |
| TypeScript typecheck / browser / Android E2E | NOT VERIFIED | npm dependency install previously timed out; no browser runtime evidence |
| PostgreSQL / multi-host | NOT IMPLEMENTED / NOT VERIFIED | SQLite remains the only runtime adapter |
| G0–G5 | NOT PASSED | No gate promoted based on this build |

## Cancellation semantic boundary

The cancellation endpoint returns a terminal Job represented as `failed` with `error_code=JOB_CANCELLED`, preserving the current SQLite CHECK constraint. It only succeeds while the Job is `queued` and its latest `SUBMIT_GENERATION` Outbox event is still `pending`. If a worker has claimed dispatch, cancellation is rejected with HTTP 409. Remote Provider cancellation and credit compensation are not implemented.
