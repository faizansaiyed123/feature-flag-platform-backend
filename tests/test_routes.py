from app.api.v1.feature_flags import router as feature_flags_router


def test_batch_evaluation_route_precedes_single_evaluation_route() -> None:
    paths = [route.path for route in feature_flags_router.routes if hasattr(route, "path")]
    batch = "/evaluate/batch/{environment_key}"
    single = "/evaluate/{environment_key}/{flag_key}"

    assert batch in paths
    assert single in paths
    assert paths.index(batch) < paths.index(single)
