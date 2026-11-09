# BUILD-00172 Release Notes — stale GLTF parse error isolation

## Change
- Guarded the `GLTFLoader.parse` error callback with the effect's cancellation flag.
- Documented why the guard is required: GLTF parsing is not abortable, so an error callback may arrive after model replacement or component unmount.
- Added source-level regression checks proving the stale callback exits before setting error state or notifying consumers.

## User-visible impact
A failed parse from an obsolete model request can no longer overwrite the loading/ready/error state belonging to a newer model request, nor notify the current consumer after the original effect has been cancelled.

## Scope
No API, database, provider, credit, publication, deployment, dependency-version, or lockfile changes.
