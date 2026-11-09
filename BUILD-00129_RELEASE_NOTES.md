# BUILD-00129 Release Notes

- ProjectWorkspace and ProductCatalogWorkspace abort initial effect-owned network requests when unmounted or when workspace/access token changes.
- Added last-request-wins sequence guards and workspace/token identity checks before applying asynchronous list results, preventing stale workspace data from replacing the current view.
- No backend/API/schema/dependency/database changes.
