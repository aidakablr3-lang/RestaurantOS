"""GetOwnerActivationTokenStatusUseCase.

No use case existed to read an ``OwnerActivationToken``'s status back by
who it belongs to (only ``ActivateOwnerUseCase``'s own unauthenticated
lookup-by-hash existed) -- added for Phase 1 design doc §A.4's
``ProvisionTenantStep.verify()``, which needs to confirm the just-issued
token is still unexpired and unused, the same ``Get*UseCase`` convention
as ``GetUserUseCase``. Returns a bare ``bool`` (not a DTO) — matching
§A.4's own pseudocode (``if not token_active:``) — since the only thing
any caller has ever needed from this is "is there one right now that
would still work," never the token's other fields (its hash is never
exposed past the repository, its id has no other use).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.domain.ports import OwnerActivationTokenRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetOwnerActivationTokenStatusUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        owner_activation_token_repository_factory: Callable[
            [AsyncSession], OwnerActivationTokenRepository
        ],
    ) -> None:
        self._session_factory = session_factory
        self._owner_activation_token_repository_factory = owner_activation_token_repository_factory

    async def execute(self, tenant_id: str, user_id: str) -> bool:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            token_repo = self._owner_activation_token_repository_factory(uow.session)
            token = await token_repo.get_latest_for_user(tenant_id, user_id)
        return token is not None and token.is_usable()
