"""VerifyAccessTokenUseCase — the authentication + tenant-validation check
every protected route runs.

Sprint 4.1 (Tenant Platform) is the first PR with protected routes, so
this is the first consumer of the auth-middleware and tenant-validation-
middleware requirements. They are implemented as **one** combined check,
not two independent ones: both need the same tenant-scoped database
round trip (fetch the tenant, fetch the user), and a request whose
tenant is suspended has no meaningful "is the user valid" answer
separate from that — splitting them into two dependencies would mean
either two round trips or awkward shared state between them.

Technical Architecture v2.0 Group C: the token's embedded
``permission_version`` is checked against the *live* value on every
request — this is what bounds a deactivated/downgraded user's access to
this check's latency (a direct DB read in this sprint; TAD v2.0's
Redis-cached version of this check is a follow-up performance
optimization once Redis is actually introduced, per the approved plan's
scope note).

**RBAC interaction, made explicit (RBAC Foundation Architecture SS9,
confirmed by RBAC Sprint 5 Step 2's test matrix and approved by the
user as intentional security behavior — not a bug, not to be
"softened" into eventual propagation):** the check below is *strict
equality* (``!=``), not "is the live version at least the token's
version." Granting or revoking a role bumps the affected user's
``permission_version`` (``AssignUserRoleUseCase``/
``RevokeUserRoleUseCase``), which immediately stales every access token
already issued to that user — the *very next* request with the old
token gets ``InvalidAccessTokenError`` below, forcing re-authentication.
A fresh token obtained after that always carries the current
permission set (permission resolution is never cached — see
``ResolveUserPermissionsUseCase``), but the *old* token does not
"eventually" pick up the change; it simply stops working. This is a
deliberately stronger guarantee than eventual consistency, not a weaker
one. See ``tests/unit/.../test_verify_access_token.py`` for the
regression lock and ``tests/integration/.../test_rbac_router.py`` for
the same contract proven end-to-end over real HTTP.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.application.interfaces import TokenDecodeError, TokenService
from restaurant_os_api.modules.identity.domain.exceptions import InvalidAccessTokenError
from restaurant_os_api.modules.identity.domain.ports import TenantRepository, UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class VerifyAccessTokenUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        token_service: TokenService,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._user_repository_factory = user_repository_factory
        self._token_service = token_service

    async def execute(self, raw_access_token: str) -> AuthenticatedPrincipalDTO:
        try:
            claims = self._token_service.decode_access_token(raw_access_token)
        except TokenDecodeError as exc:
            raise InvalidAccessTokenError() from exc

        async with UnitOfWork(self._session_factory, TenantContext(claims.tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)

            tenant = await tenant_repo.get_by_id(claims.tenant_id)
            if tenant is None:
                raise InvalidAccessTokenError()
            # Raises TenantNotActiveError (mapped to 401, same as an
            # invalid token — Data Architecture v2.0 SS4.5's suspension
            # guarantee: reject immediately, no distinguishing detail
            # leaked to the caller about *why*.
            tenant.ensure_can_authenticate()

            user = await user_repo.get_by_id(claims.tenant_id, claims.subject_user_id)
            if user is None:
                raise InvalidAccessTokenError()
            if user.permission_version != claims.permission_version:
                raise InvalidAccessTokenError("Access token is stale; please sign in again.")
            # Raises UserNotActiveError if deactivated since the token
            # was issued but before permission_version happened to
            # change (defense in depth — deactivation always bumps
            # permission_version today, but this does not assume that
            # invariant holds forever).
            user.ensure_can_authenticate()

        return AuthenticatedPrincipalDTO(
            user_id=user.id,
            tenant_id=user.tenant_id,
            session_id=claims.session_id,
            device_id=claims.device_id,
            is_platform_admin=user.is_platform_admin,
        )
