"""GetUserUseCase.

No single-user read existed anywhere in ``modules/identity`` before this
(``list_users.py`` lists a tenant's whole roster; nothing took a
``user_id`` and returned one) -- added for Phase 1 design doc §A.4's
``ProvisionTenantStep.verify()``, which needs to read the just-created
Owner back by id, the same ``Get*UseCase`` convention as
``GetRestaurantUseCase``/``GetBranchUseCase``.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import UserDTO
from restaurant_os_api.modules.identity.application.use_cases._user_mapper import user_to_dto
from restaurant_os_api.modules.identity.domain.exceptions import UserNotFoundError
from restaurant_os_api.modules.identity.domain.ports import UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetUserUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
    ) -> None:
        self._session_factory = session_factory
        self._user_repository_factory = user_repository_factory

    async def execute(self, tenant_id: str, user_id: str) -> UserDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            user_repo = self._user_repository_factory(uow.session)
            user = await user_repo.get_by_id(tenant_id, user_id)
        if user is None:
            raise UserNotFoundError(user_id)
        return user_to_dto(user)
