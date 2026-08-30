"""CreateSupplierUseCase. ``POST /api/v1/suppliers`` -- tenant-wide,
mirrors ``CreateBranchUseCase``'s own address-handling shape: an
``Address`` row is created only if the request includes one."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    CreateSupplierRequestDTO,
    SupplierDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._supplier_mapper import (
    supplier_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import Supplier, SupplierStatus
from restaurant_os_api.modules.operations.domain.exceptions import SupplierNameConflictError
from restaurant_os_api.modules.operations.domain.ports import SupplierRepository
from restaurant_os_api.modules.restaurant.domain.entities import Address
from restaurant_os_api.modules.restaurant.domain.ports import AddressRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class CreateSupplierUseCase:
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

    async def execute(self, tenant_id: str, request: CreateSupplierRequestDTO) -> SupplierDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            supplier_repo = self._supplier_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)

            existing = await supplier_repo.get_by_tenant_id_and_name(tenant_id, request.name)
            if existing is not None:
                raise SupplierNameConflictError(request.name)

            address = None
            address_id = None
            if request.address is not None:
                address = await address_repo.create(
                    Address(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        created_at=now,
                        line1=request.address.line1,
                        city=request.address.city,
                        state=request.address.state,
                        country_code=request.address.country_code,
                        postal_code=request.address.postal_code,
                    )
                )
                address_id = address.id

            supplier = await supplier_repo.create(
                Supplier(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    status=SupplierStatus.ACTIVE,
                    created_at=now,
                    address_id=address_id,
                )
            )
        return supplier_to_dto(supplier, address)
