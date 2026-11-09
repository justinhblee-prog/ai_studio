# BUILD-00127 Release Notes

- Adds custom Product Variant option entry in Product Catalog UI, beyond the built-in color and size fields.
- Supports adding, editing and removing custom option key/value pairs while preserving existing custom options during Variant edits.
- Client validation mirrors backend rules: lowercase alphanumeric/underscore keys (1–40 chars), values (1–80 chars), reserved `color`/`size` keys, unique keys and at most 12 total options.
- No backend routes, API schemas, dependency versions or database schema changed.
