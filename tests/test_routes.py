import os
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-secret-32-bytes-long-minimum-!")

from app.main import app

def test_batch_evaluation_route_precedes_single_evaluation_route() -> None:
    paths = [route.path for route in app.routes]
    batch = "/api/v1/evaluate/batch/{environment_key}"
    single = "/api/v1/evaluate/{environment_key}/{flag_key}"
    assert batch in paths
    assert single in paths
    assert paths.index(batch) < paths.index(single)
