from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from restaurant_os_api.modules.identity.application.dto import RefreshRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import RefreshAccessTokenUseCase
from restaurant_os_api.modules.identity.domain.entities import Session, UserStatus
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidRefreshTokenError,
    SessionRevokedError,
    UserNotActiveError,
    UserNotFoundError,
)
from tests.unit.modules.identity.fakes import InMemorySessionRepository, InMemoryUserRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID


def _make_use_case(
    session_factory, user_repository, session_repository, token_service
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        session_factory=session_factory,
        user_repository_factory=lambda _session: user_repository,
        session_repository_factory=lambda _session: session_repository,
        token_service=token_service,
        access_ttl_seconds=900,
        refresh_ttl_seconds=2_592_000,
    )


async def _seed_session(
    session_repository: InMemorySessionRepository,
    token_service,
    *,
    raw_token: str = "valid-refresh-token",
    expires_in: timedelta = timedelta(days=30),
    revoked: bool = False,
) -> Session:
    now = datetime.now(UTC)
    session = Session(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAX",
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        device_id=None,
        refresh_token_hash=token_service.hash_refresh_token(raw_token),
        issued_at=now,
        expires_at=now + expires_in,
        revoked_at=now if revoked else None,
    )
    await session_repository.create(session)
    return session


async def test_refresh_succeeds_and_rotates_the_session(
    session_factory,
    user_repository,
    session_repository,
    token_service,
) -> None:
    await _seed_session(session_repository, token_service)
    use_case = _make_use_case(session_factory, user_repository, session_repository, token_service)

    result = await use_case.execute(
        RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="valid-refresh-token")
    )

    assert result.token_type == "bearer"
    old_session = session_repository.sessions["01ARZ3NDEKTSV4RRFFQ69G5FAX"]
    assert old_session.revoked_at is not None, "old session must be revoked on rotation"

    new_sessions = [s for s in session_repository.sessions.values() if s.revoked_at is None]
    assert len(new_sessions) == 1
    assert new_sessions[0].id != old_session.id


async def test_refresh_fails_with_unknown_token(
    session_factory,
    user_repository,
    session_repository,
    token_service,
) -> None:
    use_case = _make_use_case(session_factory, user_repository, session_repository, token_service)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="never-issued"))


async def test_refresh_fails_with_revoked_session(
    session_factory,
    user_repository,
    session_repository,
    token_service,
) -> None:
    await _seed_session(session_repository, token_service, revoked=True)
    use_case = _make_use_case(session_factory, user_repository, session_repository, token_service)

    with pytest.raises(SessionRevokedError):
        await use_case.execute(
            RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="valid-refresh-token")
        )


async def test_refresh_fails_with_expired_session(
    session_factory,
    user_repository,
    session_repository,
    token_service,
) -> None:
    await _seed_session(session_repository, token_service, expires_in=timedelta(seconds=-1))
    use_case = _make_use_case(session_factory, user_repository, session_repository, token_service)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(
            RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="valid-refresh-token")
        )


async def test_refresh_fails_when_tenant_id_does_not_match_the_session(
    session_factory,
    user_repository,
    session_repository,
    token_service,
) -> None:
    """A refresh token issued for tenant A must not be usable by claiming
    tenant B — the lookup is scoped by tenant_id (Data Architecture v2.0
    SS4.1), so a mismatched claim simply finds no row."""
    await _seed_session(session_repository, token_service)
    use_case = _make_use_case(session_factory, user_repository, session_repository, token_service)

    with pytest.raises(InvalidRefreshTokenError):
        await use_case.execute(
            RefreshRequestDTO(
                tenant_id="01ARZ3NDEKTSV4RRFFQ69G5FAZ", refresh_token="valid-refresh-token"
            )
        )


async def test_refresh_fails_when_user_no_longer_exists(
    session_factory,
    session_repository,
    token_service,
) -> None:
    await _seed_session(session_repository, token_service)
    use_case = _make_use_case(
        session_factory, InMemoryUserRepository({}), session_repository, token_service
    )

    with pytest.raises(UserNotFoundError):
        await use_case.execute(
            RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="valid-refresh-token")
        )


async def test_refresh_fails_when_user_was_deactivated_since_login(
    session_factory,
    user_repository,
    session_repository,
    token_service,
    active_user,
) -> None:
    active_user.status = UserStatus.DEACTIVATED
    await _seed_session(session_repository, token_service)
    use_case = _make_use_case(
        session_factory,
        InMemoryUserRepository({active_user.id: active_user}),
        session_repository,
        token_service,
    )

    with pytest.raises(UserNotActiveError):
        await use_case.execute(
            RefreshRequestDTO(tenant_id=TENANT_ID, refresh_token="valid-refresh-token")
        )
