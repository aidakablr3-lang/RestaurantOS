"""UpdateBranchUseCase.

Restaurant Platform Architecture SS7/SS8's ``PATCH /api/v1/branches/
{id}``, matching the Blueprint's Branch Details screen ("address,
hours, status" edited together). Only ``name`` and (optionally)
``address`` are editable here -- ``restaurant_id``/``tenant_id`` are
immutable (no settable field for either exists on
``UpdateBranchRequestDTO``), and ``status`` changes go through
``CloseBranchUseCase``/``ReopenBranchUseCase``'s own calls to
``Branch``'s guarded transitions, never a generic field set, mirroring
``UpdateRestaurantUseCase``'s own precedent.

Address handling (Step 4.2 clarification): a request that omits
``address`` leaves the branch's existing address relationship
untouched. A request that includes one either updates the existing
``Address`` row in place (if the branch already has one) or creates a
new one and links it (if the branch had none yet) -- never
implicitly clears an address by omission.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import BranchDTO, UpdateBranchRequestDTO
from restaurant_os_api.modules.restaurant.application.use_cases._branch_mapper import (
    branch_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import Address
from restaurant_os_api.modules.restaurant.domain.events import BranchUpdated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNameConflictError,
    BranchNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import AddressRepository, BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class UpdateBranchUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        address_repository_factory: Callable[[AsyncSession], AddressRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._address_repository_factory = address_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: UpdateBranchRequestDTO) -> BranchDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            if request.name != branch.name:
                existing = await branch_repo.get_by_restaurant_id_and_name(
                    tenant_id, branch.restaurant_id, request.name
                )
                if existing is not None and existing.id != branch.id:
                    raise BranchNameConflictError(branch.restaurant_id, request.name)
                branch.name = request.name

            address: Address | None = None
            if request.address is not None:
                if branch.address_id is not None:
                    address = await address_repo.get_by_id(tenant_id, branch.address_id)
                    assert address is not None, "branch.address_id references a live address row"
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
                    branch.address_id = address.id
            elif branch.address_id is not None:
                address = await address_repo.get_by_id(tenant_id, branch.address_id)

            branch = await branch_repo.update(branch)

            await outbox.publish(tenant_id, BranchUpdated(branch_id=branch.id, occurred_at=now))

        return branch_to_dto(branch, address)
