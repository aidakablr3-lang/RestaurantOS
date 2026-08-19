"""ActivateOwnerUseCase — lets an INVITED owner set their first password.

Phase 1 design doc SSA.4. The counterpart to
``TenantProvisioningService.provision()``'s atomic Owner creation: a
provisioned Owner has ``password_hash=None``/``status=INVITED`` and is
otherwise permanently unreachable (``ensure_can_authenticate`` already
rejects non-``ACTIVE`` users at login) until this use case runs.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import ActivateOwnerRequestDTO
from restaurant_os_api.modules.identity.application.interfaces import PasswordHasher, TokenService
from restaurant_os_api.modules.identity.domain.exceptions import InvalidOwnerActivationTokenError
from restaurant_os_api.modules.identity.domain.ports import (
    OwnerActivationTokenRepository,
    UserRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ActivateOwnerUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        owner_activation_token_repository_factory: Callable[
            [AsyncSession], OwnerActivationTokenRepository
        ],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        password_hasher: PasswordHasher,
        token_service: TokenService,
    ) -> None:
        self._session_factory = session_factory
        self._token_repository_factory = owner_activation_token_repository_factory
        self._user_repository_factory = user_repository_factory
        self._password_hasher = password_hasher
        self._token_service = token_service

    async def execute(self, request: ActivateOwnerRequestDTO) -> None:
        token_hash = self._token_service.hash_refresh_token(request.token)

        # Phase 1: find the token with no tenant context -- there is
        # none to supply yet; discovering it is what this lookup is for
        # (see OwnerActivationTokenRepository.get_by_token_hash's own
        # docstring). Read-only, so a "not found" exit here leaves
        # nothing to roll back.
        async with UnitOfWork(self._session_factory) as uow:
            token_repo = self._token_repository_factory(uow.session)
            token = await token_repo.get_by_token_hash(token_hash)

        if token is None or not token.is_usable():
            raise InvalidOwnerActivationTokenError()

        # Phase 2: the tenant is now known -- re-verify inside its own
        # tenant-scoped transaction (closes the race where a concurrent
        # activation consumed the token between phase 1 and here) and
        # perform both writes together.
        async with UnitOfWork(self._session_factory, TenantContext(token.tenant_id)) as uow:
            token_repo = self._token_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)

            fresh_token = await token_repo.get_by_token_hash(token_hash)
            if fresh_token is None or not fresh_token.is_usable():
                raise InvalidOwnerActivationTokenError()

            password_hash = self._password_hasher.hash(request.new_password)
            await user_repo.activate(token.tenant_id, token.user_id, password_hash=password_hash)
            await token_repo.mark_used(fresh_token.id, used_at=datetime.now(UTC))
