from app.api.v1.feature_flags import router as feature_flags_router


def test_batch_evaluation_route_precedes_single_evaluation_route() -> None:
    paths = [route.path for route in feature_flags_router.routes if hasattr(route, "path")]
    batch = "/evaluate/batch/{environment_key}"
    single = "/evaluate/{environment_key}/{flag_key}"

    assert batch in paths
    assert single in paths
    assert paths.index(batch) < paths.index(single)

from datetime import datetime, timezone
from uuid import uuid4

from app.models.feature_flags import AuditLog
from app.schemas.overview import AuditLogResponse


def test_audit_log_response_accepts_sqlalchemy_model() -> None:
    audit = AuditLog(
        id=uuid4(),
        organization_id=uuid4(),
        project_id=uuid4(),
        action="flag.created",
        entity_type="feature_flag",
        entity_id=str(uuid4()),
        details={"key": "checkout-redesign"},
        actor_user_id=uuid4(),
        created_at=datetime.now(timezone.utc),
    )

    result = AuditLogResponse.model_validate(audit)

    assert result.action == "flag.created"
    assert result.details == {"key": "checkout-redesign"}
