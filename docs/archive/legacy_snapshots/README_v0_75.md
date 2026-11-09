# AI CREATOR STUDIO v0.75

PostgreSQL runtime readiness gate.

- Added a non-invasive capability probe for PostgreSQL drivers and local provisioners.
- Added tests for ready and blocked environment combinations.
- Current environment is not ready: no PostgreSQL driver and no native/container provisioner.
- No DB connection, service startup, PostgreSQL adapter, or live integration test was performed.
