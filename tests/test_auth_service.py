from unittest.mock import AsyncMock, Mock

import pytest

from app.models.identity import User
from app.models.organization import Membership, Organization
from app.services.auth import signup


@pytest.mark.asyncio
async def test_signup_does_not_commit_its_own_transaction() -> None:
    db = Mock()
    db.scalar = AsyncMock(side_effect=[None, None])
    db.flush = AsyncMock()
    db.add = Mock()
    db.commit = AsyncMock()
    db.rollback = AsyncMock()

    user = await signup(
        db=db,
        email="  Feature.Owner@Example.com ",
        password="a-long-enough-test-password",
        display_name="Feature Owner",
        organization_name=" Example Workspace ",
    )

    assert isinstance(user, User)
    assert user.email == "feature.owner@example.com"
    assert user.display_name == "Feature Owner"
    db.commit.assert_not_awaited()
    db.rollback.assert_not_awaited()

    staged = [call.args[0] for call in db.add.call_args_list]
    assert any(isinstance(item, User) for item in staged)
    assert any(isinstance(item, Organization) for item in staged)
    assert any(isinstance(item, Membership) for item in staged)

def test_membership_role_database_values_match_migration() -> None:
    role_type = Membership.__table__.c.role.type
    assert list(role_type.enums) == ["owner", "admin", "member", "viewer"]

