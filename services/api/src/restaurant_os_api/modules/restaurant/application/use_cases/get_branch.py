"""GetBranchUseCase.

Returns ``BranchDetailDTO`` -- Branch + Address + OperatingHours
together, matching Architecture SS8's "Branch Details" screen exactly
("Data: Branch + Address + OperatingHours"). SS7 defines no dedicated
``GET .../operating-hours`` endpoint, so operating hours are nested
here (Step 4.3) rather than requiring a second call.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.restaurant.application.dto import BranchDetailDTO
from restaurant_os_api.modules.restaurant.application.use_cases._branch_mapper import (
    address_to_dto,
)
from restaurant_os_api.modules.restaurant.application.use_cases._operating_hours_mapper import (
    operating_hours_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    AddressRepository,
    BranchRepository,
    OperatingHoursRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class GetBranchUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        address_repository_factory: Callable[[AsyncSession], AddressRepository],
        operating_hours_repository_factory: Callable[[AsyncSession], OperatingHoursRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._address_repository_factory = address_repository_factory
        self._operating_hours_repository_factory = operating_hours_repository_factory

    async def execute(self, tenant_id: str, branch_id: str) -> BranchDetailDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)
            operating_hours_repo = self._operating_hours_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, branch_id)
            if branch is None:
                raise BranchNotFoundError(branch_id)

            address = None
            if branch.address_id is not None:
                address = await address_repo.get_by_id(tenant_id, branch.address_id)

            operating_hours = await operating_hours_repo.list_for_branch(tenant_id, branch_id)

        return BranchDetailDTO(
            id=branch.id,
            tenant_id=branch.tenant_id,
            restaurant_id=branch.restaurant_id,
            name=branch.name,
            status=branch.status.value,
            address=address_to_dto(address) if address is not None else None,
            created_at=branch.created_at,
            operating_hours=[operating_hours_to_dto(entry) for entry in operating_hours],
        )
