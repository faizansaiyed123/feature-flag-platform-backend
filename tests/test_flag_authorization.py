from types import SimpleNamespace
from unittest.mock import AsyncMock
from uuid import uuid4

import pytest
from fastapi import HTTPException

import app.api.v1.feature_flags as feature_flags
from app.models.organization import MembershipRole
from app.schemas.feature_flags import FeatureFlagUpdate


@pytest.mark.asyncio
async def test_member_cannot_change_flag_archive_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    membership = SimpleNamespace(role=MembershipRole.MEMBER)
    monkeypatch.setattr(
        feature_flags,
        "_flag_access",
        AsyncMock(return_value=(SimpleNamespace(), SimpleNamespace(), membership)),
    )

    with pytest.raises(HTTPException) as exc:
        await feature_flags.update_flag(
            flag_id=uuid4(),
            payload=FeatureFlagUpdate(is_archived=True),
            user=SimpleNamespace(id=uuid4()),
            db=SimpleNamespace(),
        )

    assert exc.value.status_code == 403
    assert exc.value.detail == "Insufficient organization role"
