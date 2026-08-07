from __future__ import annotations

from datetime import UTC, datetime, timedelta

from restaurant_os_api.modules.identity.application.dto import LogoutRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import LogoutUserUseCase
from restaurant_os_api.modules.identity.domain.entities import Session
from tests.unit.modules.identity.fakes import InMemorySessionRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID


def _make_use_case(session_factory, session_repository, token_service) -> LogoutUserUseCase:
    return LogoutUserUseCase(
        session_factory=session_factory,
        session_repository_factory=lambda _session: session_repository,
        token_service=token_service,
    )


async def _seed_session(
    session_repository: InMemorySessionRepository, token_service, raw_token: str
) -> Session:
    now = datetime.now(UTC)
    session = Session(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAX",
        tenant_id=TENANT_ID,
        user_id=USER_ID,
        device_id=None,
        refresh_token_hash=token_service.hash_refresh_token(raw_token),
        issued_at=now,
        expires_at=now + timedelta(days=30),
        revoked_at=None,
    )
    await session_repository.create(session)
    return session


async def test_logout_revokes_an_active_session(
    session_factory, session_repository, token_service
) -> None:
    session = await _seed_session(session_repository, token_service, "my-refresh-token")
    use_case = _make_use_case(session_factory, session_repository, token_service)

    await use_case.execute(LogoutRequestDTO(tenant_id=TENANT_ID, refresh_token="my-refresh-token"))

    assert session_repository.sessions[session.id].revoked_at is not None


async def test_logout_is_idempotent_for_an_unknown_token(
    session_factory, session_repository, token_service
) -> None:
    use_case = _make_use_case(session_factory, session_repository, token_service)

    # Must not raise.
    await use_case.execute(LogoutRequestDTO(tenant_id=TENANT_ID, refresh_token="never-issued"))


async def test_logout_is_idempotent_for_an_already_revoked_token(
    session_factory, session_repository, token_service
) -> None:
    session = await _seed_session(session_repository, token_service, "my-refresh-token")
    session.revoke()
    first_revocation_time = session.revoked_at
    use_case = _make_use_case(session_factory, session_repository, token_service)

    # Must not raise, and must not disturb the original revocation time.
    await use_case.execute(LogoutRequestDTO(tenant_id=TENANT_ID, refresh_token="my-refresh-token"))

    assert session_repository.sessions[session.id].revoked_at == first_revocation_time
