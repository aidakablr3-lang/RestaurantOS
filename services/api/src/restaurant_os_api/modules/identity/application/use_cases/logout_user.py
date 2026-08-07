"""LogoutUserUseCase — revoke a single session by its refresh token.

Idempotent by design: logging out an already-revoked or unknown refresh
token is not an error — the caller's desired end state ("this token can
no longer be used") already holds either way.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import LogoutRequestDTO
from restaurant_os_api.modules.identity.application.interfaces import TokenService
from restaurant_os_api.modules.identity.domain.ports import SessionRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class LogoutUserUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        session_repository_factory: Callable[[AsyncSession], SessionRepository],
        token_service: TokenService,
    ) -> None:
        self._session_factory = session_factory
        self._session_repository_factory = session_repository_factory
        self._token_service = token_service

    async def execute(self, request: LogoutRequestDTO) -> None:
        refresh_token_hash = self._token_service.hash_refresh_token(request.refresh_token)

        async with UnitOfWork(self._session_factory, TenantContext(request.tenant_id)) as uow:
            session_repo = self._session_repository_factory(uow.session)
            existing_session = await session_repo.get_by_refresh_token_hash(
                request.tenant_id, refresh_token_hash
            )
            if existing_session is not None and existing_session.revoked_at is None:
                await session_repo.revoke(existing_session.id)
