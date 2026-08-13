"""Regression lock for VerifyAccessTokenUseCase's permission_version
check (Technical Architecture v2.0 Group C, verify_access_token.py:72).

**Why this file exists.** RBAC Foundation Sprint 5 Step 2's own test
matrix (Commit 8) discovered -- by testing the real system rather than
assuming -- that this check is *strict equality*, not "live version is
at least the token's version": granting or revoking a role does not
make the change visible to the caller's *existing* token on its next
request, it immediately stales that token (401
``INVALID_ACCESS_TOKEN``), forcing re-authentication. The user reviewed
this finding and explicitly approved it as intentional security
behavior, with instructions to lock it against regression at the
fastest layer (no database, no HTTP) rather than relying solely on the
slower integration-level proof in test_rbac_router.py.
"""

from __future__ import annotations

import pytest

from restaurant_os_api.modules.identity.application.interfaces import (
    AccessTokenClaims,
    TokenDecodeError,
)
from restaurant_os_api.modules.identity.application.use_cases import VerifyAccessTokenUseCase
from restaurant_os_api.modules.identity.domain.entities import TenantStatus, UserStatus
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidAccessTokenError,
    TenantNotActiveError,
    UserNotActiveError,
)
from tests.unit.modules.identity.fakes import InMemoryTenantRepository, InMemoryUserRepository
from tests.unit.modules.identity.use_cases.conftest import TENANT_ID, USER_ID

RAW_TOKEN = "irrelevant-opaque-string"


def _make_use_case(session_factory, tenant_repository, user_repository, token_service):
    return VerifyAccessTokenUseCase(
        session_factory=session_factory,
        tenant_repository_factory=lambda _s: tenant_repository,
        user_repository_factory=lambda _s: user_repository,
        token_service=token_service,
    )


def _claims(*, permission_version: int) -> AccessTokenClaims:
    return AccessTokenClaims(
        subject_user_id=USER_ID,
        tenant_id=TENANT_ID,
        session_id="session-1",
        device_id=None,
        permission_version=permission_version,
    )


async def test_a_token_whose_permission_version_matches_the_live_value_succeeds(
    session_factory, tenant_repository, user_repository, token_service, fake_session
) -> None:
    token_service.decode_result = _claims(permission_version=1)  # active_user starts at 1
    use_case = _make_use_case(session_factory, tenant_repository, user_repository, token_service)

    principal = await use_case.execute(RAW_TOKEN)

    assert principal.user_id == USER_ID
    assert principal.tenant_id == TENANT_ID


async def test_a_token_with_a_lower_permission_version_than_live_is_rejected(
    session_factory, tenant_repository, user_repository, active_user, token_service, fake_session
) -> None:
    """The common real-world case: a role was granted/revoked after this
    token was issued, live version is now ahead of the token's."""
    active_user.permission_version = 2
    token_service.decode_result = _claims(permission_version=1)
    use_case = _make_use_case(session_factory, tenant_repository, user_repository, token_service)

    with pytest.raises(InvalidAccessTokenError) as exc_info:
        await use_case.execute(RAW_TOKEN)
    assert exc_info.value.error_code == "INVALID_ACCESS_TOKEN"


async def test_a_token_with_a_higher_permission_version_than_live_is_also_rejected(
    session_factory, tenant_repository, user_repository, token_service, fake_session
) -> None:
    """Regression guard for the *strict-equality* nature of the check --
    not merely ``live < token`` being rejected while ``live > token`` is
    waved through. A live value of 1 (active_user's default) against a
    token claiming version 5 must still fail: this can't happen through
    any real flow, but the check must not silently accept it either,
    since that would mean it's actually a ``>=`` check in disguise."""
    token_service.decode_result = _claims(permission_version=5)
    use_case = _make_use_case(session_factory, tenant_repository, user_repository, token_service)

    with pytest.raises(InvalidAccessTokenError):
        await use_case.execute(RAW_TOKEN)


async def test_a_stale_token_error_carries_the_invalid_access_token_error_code(
    session_factory, tenant_repository, user_repository, active_user, token_service, fake_session
) -> None:
    """This is the exact contract apps/admin-web's api-client.ts keys
    off (TOKEN_INVALID_ERROR_CODES) to decide whether to clear the
    session and redirect to /login -- pinned explicitly here so a
    change to this error code would fail a fast unit test, not only be
    discovered via a slower end-to-end run."""
    active_user.permission_version = 99
    token_service.decode_result = _claims(permission_version=1)
    use_case = _make_use_case(session_factory, tenant_repository, user_repository, token_service)

    with pytest.raises(InvalidAccessTokenError) as exc_info:
        await use_case.execute(RAW_TOKEN)
    assert exc_info.value.error_code == "INVALID_ACCESS_TOKEN"


async def test_a_malformed_or_expired_token_is_rejected_before_any_lookup(
    session_factory, token_service
) -> None:
    token_service.decode_result = TokenDecodeError("bad signature")
    use_case = _make_use_case(
        session_factory, InMemoryTenantRepository({}), InMemoryUserRepository({}), token_service
    )

    with pytest.raises(InvalidAccessTokenError):
        await use_case.execute(RAW_TOKEN)


async def test_a_token_for_an_unknown_tenant_is_rejected(
    session_factory, user_repository, token_service, fake_session
) -> None:
    token_service.decode_result = _claims(permission_version=1)
    use_case = _make_use_case(
        session_factory, InMemoryTenantRepository({}), user_repository, token_service
    )

    with pytest.raises(InvalidAccessTokenError):
        await use_case.execute(RAW_TOKEN)


async def test_a_token_for_a_suspended_tenant_is_rejected(
    session_factory, active_tenant, user_repository, token_service, fake_session
) -> None:
    active_tenant.status = TenantStatus.SUSPENDED
    token_service.decode_result = _claims(permission_version=1)
    use_case = _make_use_case(
        session_factory,
        InMemoryTenantRepository({active_tenant.id: active_tenant}),
        user_repository,
        token_service,
    )

    with pytest.raises(TenantNotActiveError):
        await use_case.execute(RAW_TOKEN)


async def test_a_token_for_an_unknown_user_is_rejected(
    session_factory, tenant_repository, token_service, fake_session
) -> None:
    token_service.decode_result = _claims(permission_version=1)
    use_case = _make_use_case(
        session_factory, tenant_repository, InMemoryUserRepository({}), token_service
    )

    with pytest.raises(InvalidAccessTokenError):
        await use_case.execute(RAW_TOKEN)


async def test_a_token_for_a_deactivated_user_is_rejected_even_with_a_matching_version(
    session_factory, tenant_repository, active_user, token_service, fake_session
) -> None:
    active_user.status = UserStatus.DEACTIVATED
    token_service.decode_result = _claims(permission_version=active_user.permission_version)
    use_case = _make_use_case(
        session_factory,
        tenant_repository,
        InMemoryUserRepository({active_user.id: active_user}),
        token_service,
    )

    with pytest.raises(UserNotActiveError):
        await use_case.execute(RAW_TOKEN)
