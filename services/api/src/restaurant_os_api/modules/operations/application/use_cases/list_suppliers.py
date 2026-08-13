"""ListSuppliersUseCase. ``GET /api/v1/suppliers``."""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.operations.application.dto import SupplierListResultDTO
from restaurant_os_api.modules.operations.application.use_cases._supplier_mapper import (
    supplier_to_dto,
)
from restaurant_os_api.modules.operations.domain.ports import SupplierRepository
from restaurant_os_api.modules.restaurant.domain.ports import AddressRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListSuppliersUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        supplier_repository_factory: Callable[[AsyncSession], SupplierRepository],
        address_repository_factory: Callable[[AsyncSession], AddressRepository],
    ) -> None:
        self._session_factory = session_factory
        self._supplier_repository_factory = supplier_repository_factory
        self._address_repository_factory = address_repository_factory

    async def execute(self, tenant_id: str, *, offset: int, limit: int) -> SupplierListResultDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            supplier_repo = self._supplier_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)
            suppliers, total = await supplier_repo.list_for_tenant(
                tenant_id, offset=offset, limit=limit
            )
            dtos = []
            for supplier in suppliers:
                address = (
                    await address_repo.get_by_id(tenant_id, supplier.address_id)
                    if supplier.address_id is not None
                    else None
                )
                dtos.append(supplier_to_dto(supplier, address))
        return SupplierListResultDTO(suppliers=dtos, total=total, offset=offset, limit=limit)
