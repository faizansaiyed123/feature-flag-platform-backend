import os
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-secret-32-bytes-long-minimum-!")

from fastapi.testclient import TestClient

from app.main import app


def test_health() -> None:
    with TestClient(app) as client:
        response = client.get("/api/v1/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_cors_allows_feature_evaluation_header() -> None:
    with TestClient(app) as client:
        response = client.options(
            "/api/v1/evaluate/production/example",
            headers={
                "Origin": "http://localhost:3000",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "content-type,x-feature-key",
            },
        )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:3000"
    assert "X-Feature-Key" in response.headers["access-control-allow-headers"]
