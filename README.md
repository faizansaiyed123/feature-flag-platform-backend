# Feature Flag Platform — Backend

FastAPI backend for the Feature Flag Platform. It provides versioned HTTP endpoints for account and organization membership, projects and environments, feature flags and targeting, server-side evaluation, rollout simulation, project overviews, and audit history.

**Product walkthrough:** [View the Flagship product walkthrough](https://github.com/faizansaiyed123/feature-flag-platform-frontend/blob/main/docs/testing/VISUAL-TEST-WALKTHROUGH.md)

## Key features

- **Identity and access:** Account signup, login, logout, session refresh, organization memberships, and role-based access controls.
- **Projects and environments:** Organization-scoped projects, protected environments, and environment-specific configuration.
- **Feature flags:** Typed flag definitions, environment-specific enablement and default values, and versioned environment state.
- **Targeting:** Conditional rules, reusable audience segments, and deterministic percentage-based rollouts.
- **Evaluation:** Single-flag and batch evaluation endpoints, plus an API endpoint for simulating targeting decisions.
- **SDK credentials:** Environment-scoped SDK key creation and rotation, with hashed key storage.
- **Operational visibility:** Project overview data, audit logs, liveness checks, and database-backed readiness checks.

## Tech stack and architecture

- Python 3.13+
- FastAPI and Uvicorn
- SQLAlchemy with asynchronous database access
- PostgreSQL and psycopg
- Alembic database migrations
- Pydantic Settings
- PyJWT and Argon2 password hashing

The application separates API routers, services, SQLAlchemy models, Pydantic schemas, database access, and security utilities. The default API prefix is `/api/v1`, configurable through `API_PREFIX`.

Authentication uses HTTP-only access and refresh cookies. Refresh sessions are stored server-side and support rotation and revocation. SDK keys are stored as hashes rather than as reusable plaintext credentials.

The application includes configurable authentication rate limits, allowed-host validation, CORS configuration, origin checks for mutating requests, request-size checks, and security response headers.

The backend does not require Redis, Celery, RabbitMQ, or a separate worker process.

## Companion repository

The frontend is maintained separately:

[Feature Flag Platform — Frontend](https://github.com/faizansaiyed123/feature-flag-platform-frontend)

The companion repository contains the product walkthrough and screenshots covering signup, workspace setup, feature flags, targeting, evaluation, audit history, team access, and mobile navigation.

## Quick start

### Prerequisites

- Python 3.13 or later
- Docker and the Docker Compose plugin for the provided launcher
- PostgreSQL 17 when using the included local Compose stack

### Local development

Create a local environment file:

```bash
cp .env.example .env
```

Generate a development secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Set the generated secret as `AUTH_SECRET_KEY` in `.env`. Do not reuse development secrets in production.

Start the backend and local PostgreSQL:

```bash
python run.py
```

Alternatively:

```bash
docker compose up --build
```

The local API defaults to port 8000.

- Liveness: `GET /api/v1/health`
- Readiness: `GET /api/v1/ready`

### Production deployment

The application image does not run migrations automatically at container startup. Apply migrations as a separate release step with the database connection configured:

```bash
alembic upgrade head
```

Start the API directly with Uvicorn:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For Docker with a managed or external PostgreSQL database:

```bash
docker compose -f docker-compose.production.yml up --build -d
```

Production configuration must use an appropriate authentication secret, explicit allowed hosts, and exact HTTPS CORS origins.

### Database operations

```bash
alembic upgrade head
alembic current
alembic heads
```

Production PostgreSQL should use managed backups and a tested restore procedure. A Docker volume is not a backup.

## Environment variables

The following names come from `.env.example`. Values and defaults are intentionally omitted.

| Variable | Purpose |
| --- | --- |
| `APP_NAME` | Application name |
| `APP_ENV` | Runtime environment selection |
| `LOG_LEVEL` | Logging level |
| `API_PREFIX` | API route prefix |
| `DATABASE_URL` | Database connection |
| `AUTH_SECRET_KEY` | Authentication token signing secret |
| `ACCESS_TOKEN_EXPIRE_MINUTES` | Access-token lifetime |
| `REFRESH_TOKEN_EXPIRE_DAYS` | Refresh-token lifetime |
| `CORS_ORIGINS` | Allowed browser origins |
| `AUTH_COOKIE_SAMESITE` | Cookie SameSite policy |
| `ALLOWED_HOSTS` | Permitted request hostnames |
| `MAX_REQUEST_BODY_BYTES` | Request body size limit |
| `DB_POOL_SIZE` | Database connection pool size |
| `DB_MAX_OVERFLOW` | Additional database connections |
| `DB_POOL_TIMEOUT` | Connection pool wait timeout |
| `DB_POOL_RECYCLE` | Connection recycle interval |
| `TRUST_PROXY_HEADERS` | Whether to trust configured proxy headers |
| `AUTH_LOGIN_RATE_LIMIT` | Login rate limit |
| `AUTH_SIGNUP_RATE_LIMIT` | Signup rate limit |
| `AUTH_REFRESH_RATE_LIMIT` | Refresh rate limit |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | Authentication rate-limit window |

The Compose configuration also recognizes `POSTGRES_USER`, `POSTGRES_PASSWORD`, `POSTGRES_DB`, and `BACKEND_PORT`.

## Tests

Install the project and the development tools used by CI:

```bash
python -m pip install --upgrade pip
pip install .
pip install "pytest>=8.3,<10" "pytest-asyncio>=1,<2" "ruff>=0.13,<1"
```

Run the backend tests and quality checks:

```bash
pytest -q
ruff check app migrations tests
python -m compileall app tests
alembic heads
```

The GitHub Actions workflow at `.github/workflows/ci.yml` runs these checks on pushes to `main` and pull requests.

The test suite covers authentication cookies and sessions, configuration validation, flag evaluation, authorization, health and origin handling, route ordering, audit response validation, password hashing, and token handling.

## Project structure

```text
app/
├── api/
│   ├── deps.py
│   └── v1/           # Versioned API route handlers
├── db/               # Database engine and sessions
├── models/            # SQLAlchemy models
├── schemas/           # Pydantic request and response schemas
├── security/          # Passwords, tokens, rate limiting
├── services/          # Authentication, credentials, evaluation, audit
├── config.py          # Application settings
└── main.py            # FastAPI application and middleware

migrations/
└── versions/          # Versioned database migrations

tests/                 # Backend test suite
.github/workflows/     # GitHub Actions CI
run.py                 # Local Docker Compose launcher
```

## Documentation

- [Development status](DEVELOPMENT_STATUS.md)
- [Backend CI workflow](.github/workflows/ci.yml)
- [Feature Flag Platform frontend](https://github.com/faizansaiyed123/feature-flag-platform-frontend)
- [Product walkthrough and screenshots](https://github.com/faizansaiyed123/feature-flag-platform-frontend/blob/main/docs/testing/VISUAL-TEST-WALKTHROUGH.md)
