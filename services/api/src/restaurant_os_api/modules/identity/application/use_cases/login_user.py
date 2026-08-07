"""LoginUserUseCase — email + password authentication.

Technical Architecture v2.0 SS2.2: orchestrates Domain entities and
Infrastructure ports; contains no SQL, no HTTP, no JWT-library calls of
its own — those live behind the ports it depends on.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import LoginRequestDTO, TokenPairDTO
from restaurant_os_api.modules.identity.application.interfaces import (
    AccessTokenClaims,
    PasswordHasher,
    TokenService,
)
from restaurant_os_api.modules.identity.domain.entities import Session as DomainSession
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidCredentialsError,
    TenantNotFoundError,
)
from restaurant_os_api.modules.identity.domain.ports import (
    SessionRepository,
    TenantRepository,
    UserRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

# A statically pre-computed Argon2id hash of a fixed, non-secret value.
# Verified against on the "user not found" path so that path takes
# approximately the same time as the "wrong password" path — otherwise
# an attacker could distinguish "no such account" from "wrong password"
# purely by response latency and enumerate valid accounts.
_DUMMY_PASSWORD_HASH = (
    "$argon2id$v=19$m=65536,t=3,p=4$EkwOp2AiAt4QQnkTOz22SQ$"
    "Or0S9pd86HV4ZOrzfxssV2/9cPYaymb7YFYBSTmAu2A"
)


class LoginUserUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        session_repository_factory: Callable[[AsyncSession], SessionRepository],
        password_hasher: PasswordHasher,
        token_service: TokenService,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._user_repository_factory = user_repository_factory
        self._session_repository_factory = session_repository_factory
        self._password_hasher = password_hasher
        self._token_service = token_service
        self._access_ttl_seconds = access_ttl_seconds
        self._refresh_ttl_seconds = refresh_ttl_seconds

    async def execute(self, request: LoginRequestDTO) -> TokenPairDTO:
        async with UnitOfWork(self._session_factory, TenantContext(request.tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)
            session_repo = self._session_repository_factory(uow.session)

            tenant = await tenant_repo.get_by_id(request.tenant_id)
            if tenant is None:
                raise TenantNotFoundError(request.tenant_id)
            tenant.ensure_can_authenticate()

            user = await user_repo.get_by_email(request.tenant_id, request.email)
            if user is None or not user.has_password_credential():
                # Run a verification anyway, against a fixed dummy hash, so
                # this path costs the same as a real-but-wrong-password
                # attempt (see _DUMMY_PASSWORD_HASH above).
                self._password_hasher.verify(request.password, _DUMMY_PASSWORD_HASH)
                raise InvalidCredentialsError()

            user.ensure_can_authenticate()

            assert user.password_hash is not None  # guaranteed by has_password_credential()
            if not self._password_hasher.verify(request.password, user.password_hash):
                raise InvalidCredentialsError()

            raw_refresh_token = self._token_service.generate_refresh_token()
            now = datetime.now(UTC)
            new_session = DomainSession(
                id=generate_ulid(),
                tenant_id=request.tenant_id,
                user_id=user.id,
                device_id=request.device_id,
                refresh_token_hash=self._token_service.hash_refresh_token(raw_refresh_token),
                issued_at=now,
                expires_at=now + timedelta(seconds=self._refresh_ttl_seconds),
                revoked_at=None,
            )
            created_session = await session_repo.create(new_session)

            access_token = self._token_service.issue_access_token(
                AccessTokenClaims(
                    subject_user_id=user.id,
                    tenant_id=request.tenant_id,
                    session_id=created_session.id,
                    device_id=request.device_id,
                    permission_version=user.permission_version,
                )
            )

        return TokenPairDTO(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=self._access_ttl_seconds,
        )
