"""Dependency providers wiring concrete Infrastructure to Application ports.

Technical Architecture v2.0 SS5.2: FastAPI's native `Depends()` is the DI
mechanism — cross-cutting singletons (the DB engine, the session factory,
the password hasher, the token service) are constructed once per process
via `functools.lru_cache`; use cases are cheap, stateless objects
constructed fresh per request from those singletons.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header, Path
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from restaurant_os_api.core.config import Settings, get_settings
from restaurant_os_api.modules.identity.application.dto import AuthenticatedPrincipalDTO
from restaurant_os_api.modules.identity.application.interfaces import (
    PasswordHasher,
    TokenService,
)
from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.application.use_cases import (
    AssignUserRoleUseCase,
    CreateRoleUseCase,
    CreateUserUseCase,
    GetRoleUseCase,
    GetSubscriptionStatusUseCase,
    GetTenantQuotaUsageUseCase,
    GetTenantSettingsUseCase,
    GetTenantUseCase,
    ListFeatureFlagsUseCase,
    ListPermissionsUseCase,
    ListRolesUseCase,
    ListTenantsUseCase,
    ListUsersUseCase,
    LoginUserUseCase,
    LogoutUserUseCase,
    OffboardTenantUseCase,
    OnboardTenantUseCase,
    ReactivateTenantUseCase,
    RefreshAccessTokenUseCase,
    ReplaceRolePermissionsUseCase,
    ResolveUserPermissionsUseCase,
    RevokeUserRoleUseCase,
    SuspendTenantUseCase,
    UpdateTenantSettingsUseCase,
    UpdateTenantUseCase,
    VerifyAccessTokenUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientPrivilegesError,
    InvalidAccessTokenError,
    PermissionDeniedError,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemyPermissionRepository,
    SQLAlchemyRolePermissionRepository,
    SQLAlchemyRoleRepository,
    SQLAlchemySessionRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemySystemSettingRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
    SQLAlchemyUserRoleRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)
from restaurant_os_api.platform.idempotency import PlatformIdempotencyGuard
from restaurant_os_api.platform.outbox.sqlalchemy_outbox_writer import SQLAlchemyOutboxWriter

SettingsDep = Annotated[Settings, Depends(get_settings)]


@lru_cache(maxsize=1)
def get_engine() -> AsyncEngine:
    settings = get_settings()
    return create_async_engine(settings.database.url, pool_size=settings.database.pool_size)


@lru_cache(maxsize=1)
def get_session_factory() -> async_sessionmaker[AsyncSession]:
    return async_sessionmaker(get_engine(), expire_on_commit=False)


SessionFactoryDep = Annotated[async_sessionmaker[AsyncSession], Depends(get_session_factory)]


@lru_cache(maxsize=1)
def get_password_hasher() -> PasswordHasher:
    return Argon2PasswordHasher()


PasswordHasherDep = Annotated[PasswordHasher, Depends(get_password_hasher)]


@lru_cache(maxsize=1)
def get_token_service() -> TokenService:
    settings = get_settings()
    return JWTTokenService(
        private_key=settings.jwt.private_key,
        public_key=settings.jwt.public_key,
        issuer=settings.jwt.issuer,
        access_ttl_seconds=settings.jwt.access_ttl_seconds,
    )


TokenServiceDep = Annotated[TokenService, Depends(get_token_service)]


def get_login_use_case(
    session_factory: SessionFactoryDep,
    password_hasher: PasswordHasherDep,
    token_service: TokenServiceDep,
    settings: SettingsDep,
) -> LoginUserUseCase:
    return LoginUserUseCase(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        session_repository_factory=SQLAlchemySessionRepository,
        password_hasher=password_hasher,
        token_service=token_service,
        access_ttl_seconds=settings.jwt.access_ttl_seconds,
        refresh_ttl_seconds=settings.jwt.refresh_ttl_seconds,
    )


def get_refresh_use_case(
    session_factory: SessionFactoryDep,
    token_service: TokenServiceDep,
    settings: SettingsDep,
) -> RefreshAccessTokenUseCase:
    return RefreshAccessTokenUseCase(
        session_factory=session_factory,
        user_repository_factory=SQLAlchemyUserRepository,
        session_repository_factory=SQLAlchemySessionRepository,
        token_service=token_service,
        access_ttl_seconds=settings.jwt.access_ttl_seconds,
        refresh_ttl_seconds=settings.jwt.refresh_ttl_seconds,
    )


def get_logout_use_case(
    session_factory: SessionFactoryDep,
    token_service: TokenServiceDep,
) -> LogoutUserUseCase:
    return LogoutUserUseCase(
        session_factory=session_factory,
        session_repository_factory=SQLAlchemySessionRepository,
        token_service=token_service,
    )


LoginUseCaseDep = Annotated[LoginUserUseCase, Depends(get_login_use_case)]
RefreshUseCaseDep = Annotated[RefreshAccessTokenUseCase, Depends(get_refresh_use_case)]
LogoutUseCaseDep = Annotated[LogoutUserUseCase, Depends(get_logout_use_case)]


def get_verify_access_token_use_case(
    session_factory: SessionFactoryDep,
    token_service: TokenServiceDep,
) -> VerifyAccessTokenUseCase:
    return VerifyAccessTokenUseCase(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        token_service=token_service,
    )


VerifyAccessTokenUseCaseDep = Annotated[
    VerifyAccessTokenUseCase, Depends(get_verify_access_token_use_case)
]


async def require_authenticated_user(
    verify_access_token: VerifyAccessTokenUseCaseDep,
    authorization: Annotated[str | None, Header()] = None,
) -> AuthenticatedPrincipalDTO:
    """The authentication + tenant-validation dependency every protected
    route depends on (Sprint 4.1's combined check — see
    ``VerifyAccessTokenUseCase``'s docstring for why this is one
    dependency, not two)."""
    if authorization is None or not authorization.startswith("Bearer "):
        raise InvalidAccessTokenError("Missing or malformed Authorization header.")
    raw_token = authorization.removeprefix("Bearer ").strip()
    return await verify_access_token.execute(raw_token)


AuthenticatedPrincipalDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_authenticated_user)
]


async def require_platform_admin(
    principal: AuthenticatedPrincipalDep,
) -> AuthenticatedPrincipalDTO:
    """Gate for tenant-lifecycle mutation endpoints (approved plan's
    Decision C). Deliberately not RBAC — a single boolean flag, checked
    here and nowhere else, until a real permissions system exists (see
    the identity module README's "Not Included" section)."""
    if not principal.is_platform_admin:
        raise InsufficientPrivilegesError()
    return principal


PlatformAdminDep = Annotated[AuthenticatedPrincipalDTO, Depends(require_platform_admin)]


# --- RBAC Foundation (Sprint 5, Step 2) ---------------------------------


def get_resolve_user_permissions_use_case(
    session_factory: SessionFactoryDep,
) -> ResolveUserPermissionsUseCase:
    return ResolveUserPermissionsUseCase(
        session_factory=session_factory,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
    )


ResolveUserPermissionsUseCaseDep = Annotated[
    ResolveUserPermissionsUseCase, Depends(get_resolve_user_permissions_use_case)
]


def require_permission(
    code: str,
) -> Callable[
    [AuthenticatedPrincipalDTO, ResolveUserPermissionsUseCase], Awaitable[AuthenticatedPrincipalDTO]
]:
    """A tenant-wide permission gate (RBAC Foundation Architecture SS8.1) —
    the caller must hold ``code`` tenant-wide, not merely at some
    branch. Use for endpoints with no branch dimension at all (e.g.
    ``POST /restaurants``).

    Deliberately does **not** special-case ``is_platform_admin`` — that
    flag gates RestaurantOS's own operators managing customer tenants
    (the pre-existing Tenant Administration surface); it has nothing to
    do with a tenant's own staff managing their own restaurant, and
    granting it an implicit RBAC bypass here would quietly merge two
    mechanisms this whole effort exists to keep separate (RBAC
    Foundation Architecture SS10.2).
    """

    async def _dependency(
        principal: AuthenticatedPrincipalDep,
        resolve_permissions: ResolveUserPermissionsUseCaseDep,
    ) -> AuthenticatedPrincipalDTO:
        resolved = await resolve_permissions.execute(principal.tenant_id, principal.user_id)
        if not resolved.has(code):
            raise PermissionDeniedError(code)
        return principal

    return _dependency


def require_branch_permission(
    code: str,
) -> Callable[
    [str, AuthenticatedPrincipalDTO, ResolveUserPermissionsUseCase],
    Awaitable[AuthenticatedPrincipalDTO],
]:
    """A branch-scoped permission gate — the caller must hold ``code``
    either tenant-wide or specifically at the request's own
    ``branch_id`` path parameter (RBAC Foundation Architecture SS7/SS8).

    The ``branch_id`` path segment is never trusted as an authorization
    *claim* — it only identifies *which resource* the request targets.
    The actual decision comes entirely from the caller's own resolved
    grants (Commit 3), checked against that target; a caller with no
    grant at that branch is denied regardless of what the URL says, and
    a caller who legitimately holds the permission there is allowed
    regardless of what *other* branches exist. Tenant scope itself is
    never taken from this parameter either — it always comes from
    ``principal.tenant_id``, itself derived from the verified access
    token (never client-supplied), exactly as every other tenant-scoped
    dependency in this module already works.
    """

    async def _dependency(
        branch_id: Annotated[str, Path(min_length=26, max_length=26)],
        principal: AuthenticatedPrincipalDep,
        resolve_permissions: ResolveUserPermissionsUseCaseDep,
    ) -> AuthenticatedPrincipalDTO:
        resolved = await resolve_permissions.execute(principal.tenant_id, principal.user_id)
        if not resolved.has(code, branch_id=branch_id):
            raise PermissionDeniedError(code, branch_id=branch_id)
        return principal

    return _dependency


def require_permission_at_any_scope(
    code: str,
) -> Callable[
    [AuthenticatedPrincipalDTO, ResolveUserPermissionsUseCase], Awaitable[AuthenticatedPrincipalDTO]
]:
    """A coarse "holds this permission *somewhere*" gate — tenant-wide,
    or at any single branch. Fixes the gap RBAC Sprint 5 Step 2's own
    test matrix found (AI_HANDOFF.md SS21, "Finding 2"): a Branch
    Manager holding ``roles.assign`` only at their branch was rejected
    by the plain tenant-wide ``require_permission`` before ever reaching
    ``AssignUserRoleUseCase``/``RevokeUserRoleUseCase`` — even though
    those use cases' own ``RoleGrantPolicy`` scope ceiling has always
    correctly supported a branch-scoped granter (Commit 5).

    Deliberately does **not** itself decide *which* branch(es) the
    caller may act on, or apply the delegation ceiling — RBAC
    Foundation Architecture SS16.1 states that guard explicitly belongs
    to "the grant use case," not the router: "This is enforced
    server-side in the grant use case, not assumed from frontend
    behavior." This dependency exists only to keep a caller who holds
    ``roles.assign`` **nowhere at all** (Waiter, Cashier, Kitchen Staff)
    out entirely, at the same coarse-grained layer
    ``require_permission``/``require_branch_permission`` already
    operate at. The real, fine-grained decision — which specific branch,
    whether the requested grant's permissions are within the caller's
    own delegation ceiling, whether a tenant-wide grant is being
    attempted by a branch-only holder — is made exactly once, inside
    ``RoleGrantPolicy.ensure_can_grant``/``ensure_can_revoke``, against
    the caller's full resolved permission set and the specific
    ``branch_id`` in the request body (for grant) or the existing
    grant's own ``branch_id`` (for revoke) — neither of which is a URL
    path parameter, which is exactly why this cannot reuse
    ``require_branch_permission`` as-is (that dependency reads
    ``branch_id`` from the URL, and no such URL parameter exists on
    either ``POST /rbac/user-roles`` or
    ``DELETE /rbac/user-roles/{user_role_id}``).

    Role *catalogue* management (creating a role, listing roles,
    replacing a role's permission set) intentionally keeps using the
    plain tenant-wide ``require_permission`` — a ``Role`` row has no
    ``branch_id`` at all in the schema (SS4.1), and
    ``RoleGrantPolicy`` itself applies no scope ceiling to authoring or
    editing a role definition (only to granting/revoking it to a
    specific user at a specific scope). Only the two routes that
    actually create/remove a scoped ``UserRole`` grant need this gate.
    """

    async def _dependency(
        principal: AuthenticatedPrincipalDep,
        resolve_permissions: ResolveUserPermissionsUseCaseDep,
    ) -> AuthenticatedPrincipalDTO:
        resolved = await resolve_permissions.execute(principal.tenant_id, principal.user_id)
        if not resolved.has(code) and not resolved.branch_ids_with(code):
            raise PermissionDeniedError(code)
        return principal

    return _dependency


def get_create_role_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> CreateRoleUseCase:
    return CreateRoleUseCase(
        session_factory=session_factory,
        resolve_user_permissions_use_case=resolve_permissions,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_get_role_use_case(session_factory: SessionFactoryDep) -> GetRoleUseCase:
    return GetRoleUseCase(
        session_factory=session_factory, role_repository_factory=SQLAlchemyRoleRepository
    )


def get_list_roles_use_case(session_factory: SessionFactoryDep) -> ListRolesUseCase:
    return ListRolesUseCase(
        session_factory=session_factory, role_repository_factory=SQLAlchemyRoleRepository
    )


def get_replace_role_permissions_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ReplaceRolePermissionsUseCase:
    return ReplaceRolePermissionsUseCase(
        session_factory=session_factory,
        resolve_user_permissions_use_case=resolve_permissions,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
    )


def get_list_permissions_use_case(session_factory: SessionFactoryDep) -> ListPermissionsUseCase:
    return ListPermissionsUseCase(
        session_factory=session_factory,
        permission_repository_factory=SQLAlchemyPermissionRepository,
    )


def get_assign_user_role_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> AssignUserRoleUseCase:
    return AssignUserRoleUseCase(
        session_factory=session_factory,
        resolve_user_permissions_use_case=resolve_permissions,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_revoke_user_role_use_case(
    session_factory: SessionFactoryDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> RevokeUserRoleUseCase:
    return RevokeUserRoleUseCase(
        session_factory=session_factory,
        resolve_user_permissions_use_case=resolve_permissions,
        user_role_repository_factory=SQLAlchemyUserRoleRepository,
        user_repository_factory=SQLAlchemyUserRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_create_user_use_case(
    session_factory: SessionFactoryDep,
    password_hasher: PasswordHasherDep,
) -> CreateUserUseCase:
    return CreateUserUseCase(
        session_factory=session_factory,
        user_repository_factory=SQLAlchemyUserRepository,
        password_hasher=password_hasher,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_list_users_use_case(session_factory: SessionFactoryDep) -> ListUsersUseCase:
    return ListUsersUseCase(
        session_factory=session_factory, user_repository_factory=SQLAlchemyUserRepository
    )


CreateUserUseCaseDep = Annotated[CreateUserUseCase, Depends(get_create_user_use_case)]
ListUsersUseCaseDep = Annotated[ListUsersUseCase, Depends(get_list_users_use_case)]

CreateRoleUseCaseDep = Annotated[CreateRoleUseCase, Depends(get_create_role_use_case)]
GetRoleUseCaseDep = Annotated[GetRoleUseCase, Depends(get_get_role_use_case)]
ListRolesUseCaseDep = Annotated[ListRolesUseCase, Depends(get_list_roles_use_case)]
ReplaceRolePermissionsUseCaseDep = Annotated[
    ReplaceRolePermissionsUseCase, Depends(get_replace_role_permissions_use_case)
]
ListPermissionsUseCaseDep = Annotated[
    ListPermissionsUseCase, Depends(get_list_permissions_use_case)
]
AssignUserRoleUseCaseDep = Annotated[AssignUserRoleUseCase, Depends(get_assign_user_role_use_case)]
RevokeUserRoleUseCaseDep = Annotated[RevokeUserRoleUseCase, Depends(get_revoke_user_role_use_case)]


# --- Tenant Platform (Sprint 4.1) ---------------------------------------


def get_tenant_provisioning_service(
    session_factory: SessionFactoryDep,
) -> TenantProvisioningService:
    return TenantProvisioningService(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        role_repository_factory=SQLAlchemyRoleRepository,
        role_permission_repository_factory=SQLAlchemyRolePermissionRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


TenantProvisioningServiceDep = Annotated[
    TenantProvisioningService, Depends(get_tenant_provisioning_service)
]


def get_onboard_tenant_use_case(
    provisioning_service: TenantProvisioningServiceDep,
) -> OnboardTenantUseCase:
    return OnboardTenantUseCase(provisioning_service=provisioning_service)


def get_get_tenant_use_case(session_factory: SessionFactoryDep) -> GetTenantUseCase:
    return GetTenantUseCase(
        session_factory=session_factory, tenant_repository_factory=SQLAlchemyTenantRepository
    )


def get_list_tenants_use_case(session_factory: SessionFactoryDep) -> ListTenantsUseCase:
    return ListTenantsUseCase(
        session_factory=session_factory, tenant_repository_factory=SQLAlchemyTenantRepository
    )


def get_update_tenant_use_case(session_factory: SessionFactoryDep) -> UpdateTenantUseCase:
    return UpdateTenantUseCase(
        session_factory=session_factory, tenant_repository_factory=SQLAlchemyTenantRepository
    )


def get_suspend_tenant_use_case(session_factory: SessionFactoryDep) -> SuspendTenantUseCase:
    return SuspendTenantUseCase(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        session_repository_factory=SQLAlchemySessionRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_reactivate_tenant_use_case(
    session_factory: SessionFactoryDep,
) -> ReactivateTenantUseCase:
    return ReactivateTenantUseCase(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_offboard_tenant_use_case(session_factory: SessionFactoryDep) -> OffboardTenantUseCase:
    return OffboardTenantUseCase(
        session_factory=session_factory,
        tenant_repository_factory=SQLAlchemyTenantRepository,
        session_repository_factory=SQLAlchemySessionRepository,
        directory_repository_factory=SQLAlchemyTenantDirectoryRepository,
        outbox_writer_factory=SQLAlchemyOutboxWriter,
    )


def get_subscription_status_use_case(
    session_factory: SessionFactoryDep,
) -> GetSubscriptionStatusUseCase:
    return GetSubscriptionStatusUseCase(
        session_factory=session_factory,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
    )


def get_tenant_quota_usage_use_case(
    session_factory: SessionFactoryDep,
) -> GetTenantQuotaUsageUseCase:
    return GetTenantQuotaUsageUseCase(
        session_factory=session_factory,
        subscription_repository_factory=SQLAlchemySubscriptionRepository,
        user_repository_factory=SQLAlchemyUserRepository,
    )


def get_tenant_settings_use_case(session_factory: SessionFactoryDep) -> GetTenantSettingsUseCase:
    return GetTenantSettingsUseCase(
        session_factory=session_factory,
        system_setting_repository_factory=SQLAlchemySystemSettingRepository,
    )


def get_update_tenant_settings_use_case(
    session_factory: SessionFactoryDep,
) -> UpdateTenantSettingsUseCase:
    return UpdateTenantSettingsUseCase(
        session_factory=session_factory,
        system_setting_repository_factory=SQLAlchemySystemSettingRepository,
    )


def get_list_feature_flags_use_case(session_factory: SessionFactoryDep) -> ListFeatureFlagsUseCase:
    return ListFeatureFlagsUseCase(
        session_factory=session_factory,
        feature_flag_repository_factory=SQLAlchemyFeatureFlagRepository,
    )


OnboardTenantUseCaseDep = Annotated[OnboardTenantUseCase, Depends(get_onboard_tenant_use_case)]
GetTenantUseCaseDep = Annotated[GetTenantUseCase, Depends(get_get_tenant_use_case)]
ListTenantsUseCaseDep = Annotated[ListTenantsUseCase, Depends(get_list_tenants_use_case)]
UpdateTenantUseCaseDep = Annotated[UpdateTenantUseCase, Depends(get_update_tenant_use_case)]
SuspendTenantUseCaseDep = Annotated[SuspendTenantUseCase, Depends(get_suspend_tenant_use_case)]
ReactivateTenantUseCaseDep = Annotated[
    ReactivateTenantUseCase, Depends(get_reactivate_tenant_use_case)
]
OffboardTenantUseCaseDep = Annotated[OffboardTenantUseCase, Depends(get_offboard_tenant_use_case)]
GetSubscriptionStatusUseCaseDep = Annotated[
    GetSubscriptionStatusUseCase, Depends(get_subscription_status_use_case)
]
GetTenantQuotaUsageUseCaseDep = Annotated[
    GetTenantQuotaUsageUseCase, Depends(get_tenant_quota_usage_use_case)
]
GetTenantSettingsUseCaseDep = Annotated[
    GetTenantSettingsUseCase, Depends(get_tenant_settings_use_case)
]
UpdateTenantSettingsUseCaseDep = Annotated[
    UpdateTenantSettingsUseCase, Depends(get_update_tenant_settings_use_case)
]
ListFeatureFlagsUseCaseDep = Annotated[
    ListFeatureFlagsUseCase, Depends(get_list_feature_flags_use_case)
]


def get_platform_idempotency_guard(session_factory: SessionFactoryDep) -> PlatformIdempotencyGuard:
    return PlatformIdempotencyGuard(session_factory)


PlatformIdempotencyGuardDep = Annotated[
    PlatformIdempotencyGuard, Depends(get_platform_idempotency_guard)
]
