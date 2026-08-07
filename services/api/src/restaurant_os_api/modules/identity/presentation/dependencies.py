"""Dependency providers wiring concrete Infrastructure to Application ports.

Technical Architecture v2.0 SS5.2: FastAPI's native `Depends()` is the DI
mechanism — cross-cutting singletons (the DB engine, the session factory,
the password hasher, the token service) are constructed once per process
via `functools.lru_cache`; use cases are cheap, stateless objects
constructed fresh per request from those singletons.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Annotated

from fastapi import Depends, Header
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
    GetSubscriptionStatusUseCase,
    GetTenantQuotaUsageUseCase,
    GetTenantSettingsUseCase,
    GetTenantUseCase,
    ListFeatureFlagsUseCase,
    ListTenantsUseCase,
    LoginUserUseCase,
    LogoutUserUseCase,
    OffboardTenantUseCase,
    OnboardTenantUseCase,
    ReactivateTenantUseCase,
    RefreshAccessTokenUseCase,
    SuspendTenantUseCase,
    UpdateTenantSettingsUseCase,
    UpdateTenantUseCase,
    VerifyAccessTokenUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import (
    InsufficientPrivilegesError,
    InvalidAccessTokenError,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemyFeatureFlagRepository,
    SQLAlchemySessionRepository,
    SQLAlchemySubscriptionRepository,
    SQLAlchemySystemSettingRepository,
    SQLAlchemyTenantDirectoryRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)
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
