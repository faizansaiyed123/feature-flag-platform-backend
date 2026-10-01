# Feature Flag Platform — Backend

FastAPI backend for the Feature Flag Platform backed by PostgreSQL.

## Stack

- Python 3.13+
- FastAPI
- Uvicorn
- SQLAlchemy async
- psycopg
- Alembic
- PostgreSQL

Redis, Celery, RabbitMQ, background workers, queues, and schedulers are not used by this repository.

## Prerequisites

For local native development, install Python 3.13+ and provide a PostgreSQL instance.

For the Docker workflow, install Docker with the Docker Compose plugin. Docker Compose starts PostgreSQL automatically, so a separate local PostgreSQL installation is not required for the Docker workflow.

## Docker startup

Start the backend and its PostgreSQL service independently:

\`\`\`bash
docker compose up --build
\`\`\`

The API is available at \`http://localhost:8000\` by default.

The backend container installs the dependencies declared in \`pyproject.toml\`, runs the existing Alembic migrations with \`alembic upgrade head\`, and then starts the existing FastAPI application with Uvicorn.

PostgreSQL is exposed to the backend container through the Compose service network. The Docker database uses:

- database: \`feature_flags\`
- user: \`feature_flags\`
- password: \`feature_flags\`
- container host: \`db\`
- port: \`5432\`

The host API port can be changed with \`BACKEND_PORT\` without changing the application port inside the container.

## API port

Default host/API port:

\`\`\`text
8000
\`\`\`

The application itself listens on container port \`8000\`.

## Environment variables

The application loads \`.env\` using \`pydantic-settings\`. The supported settings are:

| Variable | Required | Purpose |
| --- | --- | --- |
| \`APP_NAME\` | No | API application name. |
| \`APP_ENV\` | No | Environment name; defaults to \`development\`. |
| \`LOG_LEVEL\` | No | Logging level; defaults to \`INFO\`. |
| \`API_PREFIX\` | No | API prefix; defaults to \`/api/v1\`. |
| \`DATABASE_URL\` | Yes for native setup | PostgreSQL SQLAlchemy URL. |
| \`AUTH_SECRET_KEY\` | Yes | Secret used to sign access and refresh tokens; use at least 32 characters. |
| \`ACCESS_TOKEN_EXPIRE_MINUTES\` | No | Access-token lifetime. |
| \`REFRESH_TOKEN_EXPIRE_DAYS\` | No | Refresh-token lifetime. |
| \`CORS_ORIGINS\` | No | Comma-separated browser origins; defaults to \`http://localhost:3000\`. |
| \`AUTH_COOKIE_SAMESITE\` | No | Cookie SameSite policy: \`lax\`, \`strict\`, or \`none\`. |

For Docker Compose, \`DATABASE_URL\` is set to the internal PostgreSQL service automatically. \`AUTH_SECRET_KEY\` and \`CORS_ORIGINS\` have local-development defaults and can be overridden with environment variables. Never commit real secrets.

## Database and migrations

PostgreSQL is required by the application. The repository contains Alembic migrations under \`migrations/\`.

With Docker Compose, the database becomes healthy before the API starts, and the API container runs:

\`\`\`bash
alembic upgrade head
\`\`\`

before starting Uvicorn.

For native development, start PostgreSQL separately, set \`DATABASE_URL\` in \`.env\`, and run the migration command before starting the API:

\`\`\`bash
alembic upgrade head
python -m uvicorn app.main:app --reload --host 127.0.0.1 --port 8000
\`\`\`

## Health check

The liveness endpoint is:

\`\`\`text
GET /api/v1/health
\`\`\`

By default it is available at \`http://localhost:8000/api/v1/health\`.

## Stop

\`\`\`bash
docker compose down
\`\`\`

The PostgreSQL named volume is retained by \`docker compose down\`, so database data survives normal container teardown. Remove the volume explicitly when a clean local database is required.

## Rebuild

\`\`\`bash
docker compose up --build
\`\`\`

## Manual setup

Native development still requires a running PostgreSQL instance and a configured \`DATABASE_URL\`. No Redis or other supporting service is required.

The full-stack \`python run.py\` entry point lives in the frontend repository; it discovers this backend repository and starts this Docker Compose stack automatically.
