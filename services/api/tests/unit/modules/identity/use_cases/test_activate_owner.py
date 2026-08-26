"""Unit tests for ActivateOwnerUseCase (Phase 1 design doc SSA.4).

Covers: a valid token activates the user (password set, status flips to
active); unknown, expired, and already-consumed tokens all raise the
exact same InvalidOwnerActivationTokenError -- the identical-response
requirement is a property of the use case raising one exception for all
three, not of anything the router does.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from restaurant_os_api.modules.identity.application.dto import ActivateOwnerRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import ActivateOwnerUseCase
from restaurant_os_api.modules.identity.domain.entities import OwnerActivationToken, UserStatus
from restaurant_os_api.modules.identity.domain.exceptions import InvalidOwnerActivationTokenError
from tests.unit.modules.identity.fakes import (
    FakePasswordHasher,
    FakeTokenService,
    InMemoryOwnerActivationTokenRepository,
    InMemoryUserRepository,
)
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID

RAW_TOKEN = "raw-activation-token"


class _Fixture:
    def __init__(self, *, user_repository, token_service: FakeTokenService) -> None:
        self.user_repo = user_repository
        self.token_repo = InMemoryOwnerActivationTokenRepository()
        self.password_hasher = FakePasswordHasher()
        self.token_service = token_service

    def use_case(self, session_factory) -> ActivateOwnerUseCase:
        return ActivateOwnerUseCase(
            session_factory=session_factory,
            owner_activation_token_repository_factory=lambda _s: self.token_repo,
            user_repository_factory=lambda _s: self.user_repo,
            password_hasher=self.password_hasher,
            token_service=self.token_service,
        )

    async def seed_token(self, *, expires_at: datetime, used_at: datetime | None = None) -> None:
        await self.token_repo.create(
            OwnerActivationToken(
                id="01ARZ3NDEKTSV4RRFFQ6TOKEN0",
                tenant_id=TENANT_ID,
                user_id=USER_ID,
                token_hash=self.token_service.hash_refresh_token(RAW_TOKEN),
                issued_at=datetime.now(UTC),
                expires_at=expires_at,
                used_at=used_at,
            )
        )


@pytest.fixture
def invited_user_repository():
    from restaurant_os_api.modules.identity.domain.entities import User

    user = User(
        id=USER_ID,
        tenant_id=TENANT_ID,
        email="owner@example.com",
        phone=None,
        password_hash=None,
        pin_hash=None,
        permission_version=1,
        status=UserStatus.INVITED,
        created_at=datetime.now(UTC),
    )
    return InMemoryUserRepository({user.id: user})


@pytest.fixture
def fixture(invited_user_repository, token_service: FakeTokenService) -> _Fixture:
    return _Fixture(user_repository=invited_user_repository, token_service=token_service)


async def test_a_valid_token_activates_the_owner(fixture: _Fixture, session_factory) -> None:
    await fixture.seed_token(expires_at=datetime.now(UTC) + timedelta(hours=1))
    use_case = fixture.use_case(session_factory)

    await use_case.execute(ActivateOwnerRequestDTO(token=RAW_TOKEN, new_password="new password 1"))

    stored = await fixture.user_repo.get_by_id(TENANT_ID, USER_ID)
    assert stored is not None
    assert stored.status == UserStatus.ACTIVE
    assert fixture.password_hasher.verify("new password 1", stored.password_hash)


async def test_an_unknown_token_is_rejected(fixture: _Fixture, session_factory) -> None:
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InvalidOwnerActivationTokenError):
        await use_case.execute(
            ActivateOwnerRequestDTO(token="never-issued", new_password="new password 1")
        )


async def test_an_expired_token_is_rejected(fixture: _Fixture, session_factory) -> None:
    await fixture.seed_token(expires_at=datetime.now(UTC) - timedelta(hours=1))
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InvalidOwnerActivationTokenError):
        await use_case.execute(
            ActivateOwnerRequestDTO(token=RAW_TOKEN, new_password="new password 1")
        )


async def test_an_already_consumed_token_is_rejected(fixture: _Fixture, session_factory) -> None:
    await fixture.seed_token(
        expires_at=datetime.now(UTC) + timedelta(hours=1), used_at=datetime.now(UTC)
    )
    use_case = fixture.use_case(session_factory)

    with pytest.raises(InvalidOwnerActivationTokenError):
        await use_case.execute(
            ActivateOwnerRequestDTO(token=RAW_TOKEN, new_password="new password 1")
        )


async def test_the_three_rejection_reasons_raise_the_identical_exception_type_and_message(
    fixture: _Fixture, session_factory
) -> None:
    """The identical-response requirement (Phase 1 design doc SSA.4's
    amendment) is enforced here, not in the router: all three failure
    conditions must be indistinguishable at the exception level."""
    use_case = fixture.use_case(session_factory)

    errors = []
    with pytest.raises(InvalidOwnerActivationTokenError) as exc_info:
        await use_case.execute(
            ActivateOwnerRequestDTO(token="never-issued", new_password="new password 1")
        )
    errors.append(exc_info.value)

    await fixture.seed_token(expires_at=datetime.now(UTC) - timedelta(hours=1))
    with pytest.raises(InvalidOwnerActivationTokenError) as exc_info:
        await use_case.execute(
            ActivateOwnerRequestDTO(token=RAW_TOKEN, new_password="new password 1")
        )
    errors.append(exc_info.value)

    messages = {str(e) for e in errors}
    codes = {e.error_code for e in errors}
    assert len(messages) == 1
    assert len(codes) == 1
