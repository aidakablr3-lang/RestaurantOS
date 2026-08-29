"""UpdateBranchUseCase.

Restaurant Platform Architecture SS7/SS8's ``PATCH /api/v1/branches/
{id}``, matching the Blueprint's Branch Details screen ("address,
hours, status" edited together). Only ``name``, ``address``, and
``gstin`` are editable here -- ``restaurant_id``/``tenant_id`` are
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

``gstin`` and ``invoice_prefix`` both follow the same
omission-preserves convention: a request that omits either (or sends
``null``) leaves whatever is already stored untouched. Like address,
there is no way to explicitly clear an already-set value through this
endpoint today -- an existing limitation this mirrors, not a new one.

Whenever either changes, this re-checks the partial ``UNIQUE (gstin,
invoice_prefix) WHERE gstin IS NOT NULL`` constraint against the
branch's *effective* post-update values, not just the one field that
changed -- setting a new gstin can collide with an already-set prefix
just as easily as setting a new prefix can collide with an
already-set gstin.
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
    InvoicePrefixConflictError,
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

            # Same omission-preserves convention as address just below:
            # a PATCH that only sends name must not silently wipe a
            # previously-set gstin/invoice_prefix. Like address, there
            # is currently no way to explicitly clear either through
            # this endpoint -- an existing limitation this mirrors, not
            # a new one.
            gstin_or_prefix_changed = (
                request.gstin is not None or request.invoice_prefix is not None
            )
            if request.gstin is not None:
                branch.gstin = request.gstin
            if request.invoice_prefix is not None:
                branch.invoice_prefix = request.invoice_prefix

            if (
                gstin_or_prefix_changed
                and branch.gstin is not None
                and branch.invoice_prefix is not None
            ):
                conflict = await branch_repo.get_by_gstin_and_invoice_prefix(
                    tenant_id, branch.gstin, branch.invoice_prefix, exclude_branch_id=branch.id
                )
                if conflict is not None:
                    raise InvoicePrefixConflictError(branch.gstin, branch.invoice_prefix)

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
