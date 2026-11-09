# BUILD-00138 — Project Lifecycle UI Synchronization

- Added a dependency-free same-tab project lifecycle event helper shared by Project Workspace, Project Product Assignment and Lookbook Draft workspaces.
- Successful project edits and status transitions now publish a workspace-scoped lifecycle notification.
- Project Product Assignment refreshes its active-project catalog when a matching workspace event arrives; if the selected project is no longer active, its assignment selection/history is cleared and the next active project is selected.
- Lookbook Draft refreshes its active project list after lifecycle changes and clears a selected project that is no longer active, preventing a stale project reference from being submitted in a new draft.
- Added latest-request sequencing to Lookbook workspace hydration and reordered stale-request checks so obsolete failures cannot surface after a newer lifecycle refresh.
- Added 7 structural assertions and 4 executable event-helper assertions.
- No backend route/schema/migration, external dependency, provider behavior, credit behavior, publication or rights behavior changed.
