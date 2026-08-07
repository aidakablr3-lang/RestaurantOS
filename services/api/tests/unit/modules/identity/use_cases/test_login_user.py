from __future__ import annotations

import pytest

from restaurant_os_api.modules.identity.application.dto import LoginRequestDTO
from restaurant_os_api.modules.identity.application.use_cases import LoginUserUseCase
from restaurant_os_api.modules.identity.domain.entities import TenantStatus, UserStatus
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidCredentialsError,
    TenantNotActiveError,
    TenantNotFoundError,
    UserNotActiveError,
)
from tests.unit.modules.identity.use_cases.conftest import (
    TENANT_ID,
    USER_EMAIL,
    USER_ID,
    USER_PASSWORD,
)


def _make_use_case(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> LoginUserUseCase:
    return LoginUserUseCase(
        session_factory=session_factory,
        tenant_repository_factory=lambda _session: tenant_repository,
        user_repository_factory=lambda _session: user_repository,
        session_repository_factory=lambda _session: session_repository,
        password_hasher=password_hasher,
        token_service=token_service,
        access_ttl_seconds=900,
        refresh_ttl_seconds=2_592_000,
    )


async def test_login_succeeds_with_correct_credentials(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
    fake_session,
) -> None:
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    result = await use_case.execute(
        LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
    )

    assert result.token_type == "bearer"
    assert result.expires_in == 900
    assert result.access_token == f"access-token::{USER_ID}::" + next(
        iter(session_repository.sessions)
    )
    assert len(session_repository.sessions) == 1
    assert fake_session.committed is True


async def test_login_issues_access_token_with_identity_claims_only(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    """Technical Architecture v2.0 Group C: no roles/permissions in the token."""
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    await use_case.execute(
        LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
    )

    assert len(token_service.issued_claims) == 1
    claims = token_service.issued_claims[0]
    assert claims.subject_user_id == USER_ID
    assert claims.tenant_id == TENANT_ID
    assert claims.permission_version == 1
    assert not hasattr(claims, "roles")
    assert not hasattr(claims, "permissions")


async def test_login_fails_with_wrong_password(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password="wrong password")
        )
    assert session_repository.sessions == {}


async def test_login_fails_with_unknown_email_using_same_error_as_wrong_password(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    """Regression guard: must not distinguish 'no such user' from 'wrong
    password' — doing so would let a caller enumerate valid accounts."""
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email="nobody@example.com", password=USER_PASSWORD)
        )


async def test_login_fails_when_tenant_does_not_exist(
    session_factory,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    from tests.unit.modules.identity.fakes import InMemoryTenantRepository

    use_case = _make_use_case(
        session_factory,
        InMemoryTenantRepository({}),
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(TenantNotFoundError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
        )


async def test_login_fails_when_tenant_is_suspended(
    session_factory,
    active_tenant,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    from tests.unit.modules.identity.fakes import InMemoryTenantRepository

    active_tenant.status = TenantStatus.SUSPENDED
    use_case = _make_use_case(
        session_factory,
        InMemoryTenantRepository({active_tenant.id: active_tenant}),
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(TenantNotActiveError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
        )


async def test_login_fails_when_user_is_deactivated(
    session_factory,
    tenant_repository,
    active_user,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    from tests.unit.modules.identity.fakes import InMemoryUserRepository

    active_user.status = UserStatus.DEACTIVATED
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        InMemoryUserRepository({active_user.id: active_user}),
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(UserNotActiveError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
        )


async def test_login_fails_for_pin_only_account_with_no_password(
    session_factory,
    tenant_repository,
    active_user,
    session_repository,
    password_hasher,
    token_service,
) -> None:
    from tests.unit.modules.identity.fakes import InMemoryUserRepository

    active_user.password_hash = None
    active_user.pin_hash = "hashed::1234"
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        InMemoryUserRepository({active_user.id: active_user}),
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password=USER_PASSWORD)
        )


async def test_login_rolls_back_transaction_on_failure(
    session_factory,
    tenant_repository,
    user_repository,
    session_repository,
    password_hasher,
    token_service,
    fake_session,
) -> None:
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        user_repository,
        session_repository,
        password_hasher,
        token_service,
    )

    with pytest.raises(InvalidCredentialsError):
        await use_case.execute(
            LoginRequestDTO(tenant_id=TENANT_ID, email=USER_EMAIL, password="wrong")
        )

    assert fake_session.rolled_back is True
    assert fake_session.committed is False
