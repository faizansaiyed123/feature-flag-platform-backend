FROM python:3.13-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml README.md ./
COPY alembic.ini ./
COPY app ./app
COPY migrations ./migrations

RUN addgroup --system app && adduser --system --ingroup app app \
    && pip install --no-cache-dir .

USER app

EXPOSE 8000

HEALTHCHECK --interval=10s --timeout=5s --start-period=15s --retries=12 \
  CMD python -c "import os, urllib.request; urllib.request.urlopen('http://127.0.0.1:8000' + os.getenv('API_PREFIX', '/api/v1') + '/ready').read()"

CMD ["python", "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
