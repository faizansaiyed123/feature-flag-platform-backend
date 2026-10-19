# Feature Flag Platform — Backend

Production-oriented FastAPI backend for the Feature Flag Platform.

## Stack

- Python 3.13+
- FastAPI
- Uvicorn
- SQLAlchemy async
- psycopg
- Alembic
- PostgreSQL

The backend does not require Redis, Celery, RabbitMQ, or a worker process.

## Local development

Create a local environment file:

```bash
cp .env.example .env
```

Generate a development secret:

```bash
python -c "import secrets; print(secrets.token_urlsafe(32))"
```

Put the generated value in `AUTH_SECRET_KEY`.

Start the backend and local PostgreSQL:

```bash
python run.py
```

Or:

```bash
docker compose up --build
```

Liveness: `GET /api/v1/health`  
Readiness: `GET /api/v1/ready`

## Authentication and security

Authentication uses Argon2 password hashing, signed short-lived access cookies, rotating server-side refresh sessions, explicit CORS origins, browser-origin validation for browser mutations, security headers, request-size protection, and bounded authentication rate limits.

Never reuse development secrets in production.

## Production deployment

The application image does **not** run migrations during container startup. Apply migrations as a release step:

```bash
alembic upgrade head
```

Then start the API:

```bash
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

For Docker with a managed/external PostgreSQL database:

```bash
docker compose -f docker-compose.production.yml up --build -d
```

Required production variables:

| Variable | Purpose |
| --- | --- |
| `APP_ENV=production` | Enables secure production behavior. |
| `DATABASE_URL` | PostgreSQL connection string. |
| `AUTH_SECRET_KEY` | JWT signing secret. |
| `CORS_ORIGINS` | Exact frontend origins. |
| `ALLOWED_HOSTS` | Exact public API hosts. |
| `AUTH_COOKIE_SAMESITE` | Prefer `lax` for same-site deployments. |
| `DB_POOL_SIZE` | SQLAlchemy pool size. |
| `DB_MAX_OVERFLOW` | Maximum extra connections. |
| `DB_POOL_TIMEOUT` | Pool wait timeout. |
| `DB_POOL_RECYCLE` | Connection recycle interval. |
| `TRUST_PROXY_HEADERS` | Set true only when a trusted reverse proxy strips and sets `X-Forwarded-For`. |
| `AUTH_LOGIN_RATE_LIMIT` | Login requests per client per rate-limit window. |
| `AUTH_SIGNUP_RATE_LIMIT` | Signup requests per client per rate-limit window. |
| `AUTH_REFRESH_RATE_LIMIT` | Refresh requests per client per rate-limit window. |
| `AUTH_RATE_LIMIT_WINDOW_SECONDS` | Authentication rate-limit window length. |

The frontend public API URL belongs in the frontend repository as `NEXT_PUBLIC_API_BASE_URL`.

## Database operations

```bash
alembic upgrade head
alembic current
alembic heads
```

Production PostgreSQL must use managed backups and a tested restore procedure. A Docker volume is not a backup.

## Verification

```bash
pytest
python -m compileall app tests
alembic heads
ruff check .
```

For production release, also run the frontend build and full staging E2E/authorization tests.
