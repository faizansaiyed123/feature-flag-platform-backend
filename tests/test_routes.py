import os
os.environ.setdefault("AUTH_SECRET_KEY", "test-only-secret-32-bytes-long-minimum-!")

from collections.abc import Iterable

from app.main import app


def _route_paths(routes: Iterable[object]) -> list[str]:
    paths: list[str] = []
    for route in routes:
        path = getattr(route, "path", None)
        if isinstance(path, str):
            paths.append(path)

        nested = getattr(route, "routes", None)
        if nested is not None:
            paths.extend(_route_paths(nested))

    return paths


def test_batch_evaluation_route_precedes_single_evaluation_route() -> None:
    paths = _route_paths(app.routes)
    batch = "/api/v1/evaluate/batch/{environment_key}"
    single = "/api/v1/evaluate/{environment_key}/{flag_key}"

    assert batch in paths
    assert single in paths
    assert paths.index(batch) < paths.index(single)
