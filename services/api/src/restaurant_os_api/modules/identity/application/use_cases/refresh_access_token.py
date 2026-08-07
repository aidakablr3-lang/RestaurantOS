"""RefreshAccessTokenUseCase — rotate a refresh token, mint a new access token.

Technical Architecture v2.0 SS8.3: refresh token rotation — every refresh
issues a brand-new refresh token and revokes the old one; reuse of an
already-rotated (stale) refresh token is treated as a signal of possible
theft.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import RefreshRequestDTO, TokenPairDTO
from restaurant_os_api.modules.identity.application.interfaces import (
    AccessTokenClaims,
    TokenService,
)
from restaurant_os_api.modules.identity.domain.entities import Session as DomainSession
from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidRefreshTokenError,
    UserNotFoundError,
)
from restaurant_os_api.modules.identity.domain.ports import SessionRepository, UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class RefreshAccessTokenUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        session_repository_factory: Callable[[AsyncSession], SessionRepository],
        token_service: TokenService,
        access_ttl_seconds: int,
        refresh_ttl_seconds: int,
    ) -> None:
        self._session_factory = session_factory
        self._user_repository_factory = user_repository_factory
        self._session_repository_factory = session_repository_factory
        self._token_service = token_service
        self._access_ttl_seconds = access_ttl_seconds
        self._refresh_ttl_seconds = refresh_ttl_seconds

    async def execute(self, request: RefreshRequestDTO) -> TokenPairDTO:
        refresh_token_hash = self._token_service.hash_refresh_token(request.refresh_token)

        async with UnitOfWork(self._session_factory, TenantContext(request.tenant_id)) as uow:
            user_repo = self._user_repository_factory(uow.session)
            session_repo = self._session_repository_factory(uow.session)

            existing_session = await session_repo.get_by_refresh_token_hash(
                request.tenant_id, refresh_token_hash
            )
            if existing_session is None:
                raise InvalidRefreshTokenError()

            # Raises SessionRevokedError / InvalidRefreshTokenError as
            # appropriate; a revoked-and-reused token is exactly the
            # "possible theft" signal noted in this module's docstring.
            # A follow-up PR wires this to also call
            # `revoke_all_for_user` when reuse of an *already-rotated*
            # token is detected — this PR implements the base rotation
            # flow that detection builds on.
            existing_session.ensure_valid_for_refresh()

            user = await user_repo.get_by_id(request.tenant_id, existing_session.user_id)
            if user is None:
                raise UserNotFoundError(existing_session.user_id)
            user.ensure_can_authenticate()

            await session_repo.revoke(existing_session.id)

            raw_refresh_token = self._token_service.generate_refresh_token()
            now = datetime.now(UTC)
            new_session = DomainSession(
                id=generate_ulid(),
                tenant_id=request.tenant_id,
                user_id=user.id,
                device_id=request.device_id or existing_session.device_id,
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
                    device_id=new_session.device_id,
                    permission_version=user.permission_version,
                )
            )

        return TokenPairDTO(
            access_token=access_token,
            refresh_token=raw_refresh_token,
            expires_in=self._access_ttl_seconds,
        )
