# Development Status

The backend is organized around four boundaries:

- identity and workspace membership
- project/environment configuration
- feature-flag authoring and targeting
- runtime evaluation and operational auditability

## Implemented

- FastAPI application and versioned API router
- PostgreSQL/SQLAlchemy async data layer
- Alembic migrations
- Argon2 password hashing
- signed access/refresh cookies
- organizations and RBAC memberships
- projects and protected environments
- environment-scoped SDK keys with rotation and hashed storage
- typed feature flags
- environment flag state and versioning
- targeting rules and reusable segments
- deterministic rollout evaluation
- single and batch evaluation endpoints
- rollout simulator
- audit log and project overview endpoints
- browser CORS support for runtime evaluation headers
- unit and route-registration regression coverage

## API contract

All application endpoints live below `/api/v1`.

Runtime evaluation is intentionally environment-key based and expects the SDK credential in `X-Feature-Key`.

## Verification

The backend has passed the full CI quality gate against PostgreSQL, including linting, tests, Python compilation, and Alembic migration-head validation. The full-stack browser workflow also starts this backend, applies migrations, and exercises the real UI-to-API-to-database flows.

A staging deployment still needs environment-specific smoke testing because production infrastructure, domains, cookies, and browser policy can differ from CI.
