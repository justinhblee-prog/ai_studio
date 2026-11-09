# BUILD-00128 Release Notes

- Prevents Project edit-form state from reverting a lifecycle action: if the same Project is being edited, the form's status is synchronized after a successful list action.
- Clears stale Product edit and child Variant forms after archiving the corresponding Product; clears a Variant edit form after archiving that Variant.
- Trims and validates custom Variant option values before API submission to match backend non-empty / 80-character constraints.
- No backend/API/schema/dependency/database changes.
