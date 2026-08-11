"""UpdateSupplierUseCase. ``PATCH /api/v1/suppliers/{id}`` -- full-replace
over ``name``/``status``/``address``, mirroring ``UpdateBranchUseCase``'s
own address-merge shape (a request that omits ``address`` leaves the
existing relationship untouched; one that includes it updates the
existing row in place or creates a new one). ``status`` is set directly
-- see ``supplier.py``'s own docstring for why Supplier skips the
dedicated-action-route precedent other status-bearing entities use."""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.operations.application.dto import (
    SupplierDTO,
    UpdateSupplierRequestDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._supplier_mapper import (
    supplier_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import SupplierStatus
from restaurant_os_api.modules.operations.domain.exceptions import (
    SupplierNameConflictError,
    SupplierNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import SupplierRepository
from restaurant_os_api.modules.restaurant.domain.entities import Address
from restaurant_os_api.modules.restaurant.domain.ports import AddressRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateSupplierUseCase:
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

    async def execute(self, tenant_id: str, request: UpdateSupplierRequestDTO) -> SupplierDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            supplier_repo = self._supplier_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)

            supplier = await supplier_repo.get_by_id(tenant_id, request.supplier_id)
            if supplier is None:
                raise SupplierNotFoundError(request.supplier_id)

            if request.name != supplier.name:
                existing = await supplier_repo.get_by_tenant_id_and_name(tenant_id, request.name)
                if existing is not None and existing.id != supplier.id:
                    raise SupplierNameConflictError(request.name)
                supplier.name = request.name

            supplier.status = SupplierStatus(request.status)

            address: Address | None = None
            if request.address is not None:
                if supplier.address_id is not None:
                    address = await address_repo.get_by_id(tenant_id, supplier.address_id)
                    assert address is not None, "supplier.address_id references a live address row"
                    address.line1 = request.address.line1
                    address.city = request.address.city
                    address.country_code = request.address.country_code
                    address.postal_code = request.address.postal_code
                    address = await address_repo.update(address)
                else:
                    address = await address_repo.create(
                        Address(
                            id=generate_ulid(),
                            tenant_id=tenant_id,
                            created_at=now,
                            line1=request.address.line1,
                            city=request.address.city,
                            country_code=request.address.country_code,
                            postal_code=request.address.postal_code,
                        )
                    )
                    supplier.address_id = address.id
            elif supplier.address_id is not None:
                address = await address_repo.get_by_id(tenant_id, supplier.address_id)

            supplier = await supplier_repo.update(supplier)
        return supplier_to_dto(supplier, address)
