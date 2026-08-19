"""GetRoleByNameUseCase.

Role-name resolution existed only as a direct ``RoleRepository.get_by_name``
call from ``scripts/create_user.py``, an out-of-band operator script —
no use case wrapped it. Added for Phase 1 design doc §A.7's staff-creation
steps (``create_manager``/``create_waiters``/``create_kitchen_staff``),
which need to resolve "Branch Manager"/"Waiter"/"Kitchen Staff" to a
``role_id`` before calling ``AssignUserRoleUseCase`` — the step layer
must call a use case, never a repository directly, the same rule that
motivated adding ``GetUserUseCase`` (§E step 3) rather than reaching
into ``UserRepository`` from application code outside the identity
module. Same ``Get*UseCase`` convention as ``GetRoleUseCase``, keyed by
name instead of id.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import RoleDTO
from restaurant_os_api.modules.identity.application.use_cases._role_mapper import role_to_dto
from restaurant_os_api.modules.identity.domain.exceptions import RoleNotFoundError
from restaurant_os_api.modules.identity.domain.ports import RoleRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetRoleByNameUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
    ) -> None:
        self._session_factory = session_factory
        self._role_repository_factory = role_repository_factory

    async def execute(self, tenant_id: str, name: str) -> RoleDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            role = await role_repo.get_by_name(tenant_id, name)
        if role is None:
            raise RoleNotFoundError(name)
        return role_to_dto(role)
