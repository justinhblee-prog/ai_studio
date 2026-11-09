# BUILD-00132 Release Notes

## Focus: Selection-level async race protection

### Changes
- Asset Workspace now aborts superseded preview/version reads and rejects late responses after selection changes, API/auth/workspace scope changes, asset deletion, or component unmount.
- Asset version-history reads share the active selection's AbortSignal so preview and version history cannot become detached from the selected model.
- Lookbook output-assembly reads now use a monotonic request sequence keyed to the latest selected draft. Older draft loads cannot overwrite the latest selected draft's attached outputs, approved Photo runs, review state, previews, or busy/error state.
- Lookbook planning-manifest reads now reject older draft selections and invalidate on workspace/auth/API scope changes.
- Structural validation expanded from 103 to 107 assertions.

### Compatibility and safety
- No backend routes, schemas, database migrations, dependencies, public component props, Provider behavior, credit behavior, or publication/rights behavior changed.
- No live Provider, paid API, credit, publication, rights grant, production data, or deployment action was performed.
