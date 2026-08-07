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

from fastapi import Depends
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from restaurant_os_api.core.config import Settings, get_settings
from restaurant_os_api.modules.identity.application.interfaces import (
    PasswordHasher,
    TokenService,
)
from restaurant_os_api.modules.identity.application.use_cases import (
    LoginUserUseCase,
    LogoutUserUseCase,
    RefreshAccessTokenUseCase,
)
from restaurant_os_api.modules.identity.infrastructure.database.repositories import (
    SQLAlchemySessionRepository,
    SQLAlchemyTenantRepository,
    SQLAlchemyUserRepository,
)
from restaurant_os_api.modules.identity.infrastructure.security import (
    Argon2PasswordHasher,
    JWTTokenService,
)

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
