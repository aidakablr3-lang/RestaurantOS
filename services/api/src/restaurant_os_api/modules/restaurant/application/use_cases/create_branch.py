"""CreateBranchUseCase.

Restaurant Platform Architecture SS7's ``POST /api/v1/restaurants/
{restaurant_id}/branches``. ``restaurant_id`` is loaded scoped to the
caller's own tenant before anything else -- a restaurant that exists
but belongs to another tenant is treated identically to one that does
not exist at all (``RestaurantNotFoundError``, never a distinguishable
403), the same "belt and suspenders" pattern
``resolve_and_authorize_branch`` already established for a
body-supplied ``branch_id`` (Step 4.0, Decision 3) -- here applied to
the body-*path*-supplied ``restaurant_id`` a branch is created under.

Address is optional (SS3.1: "a Branch can exist with a placeholder
address during setup") -- created only if the request includes one.
The new branch is constructed in ``BranchStatus.OPENED`` and
immediately transitioned via ``Branch.activate()`` before persisting,
exercising the domain's own guarded ``opened -> active`` transition
rather than setting the field directly -- SS7 names no separate
``POST /branches/{id}/activate`` endpoint, so a newly created branch
is immediately usable (``active``) by the time this call returns,
matching how ``CreateRestaurantUseCase`` already returns a
newly-created Restaurant directly in its own active state.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import BranchDTO, CreateBranchRequestDTO
from restaurant_os_api.modules.restaurant.application.use_cases._branch_mapper import (
    branch_to_dto,
)
from restaurant_os_api.modules.restaurant.application.use_cases._invoice_prefix import (
    default_invoice_prefix,
)
from restaurant_os_api.modules.restaurant.domain.entities import Address, Branch, BranchStatus
from restaurant_os_api.modules.restaurant.domain.events import BranchCreated
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNameConflictError,
    InvoicePrefixConflictError,
    RestaurantNotFoundError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    AddressRepository,
    BranchRepository,
    RestaurantRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateBranchUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        restaurant_repository_factory: Callable[[AsyncSession], RestaurantRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        address_repository_factory: Callable[[AsyncSession], AddressRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._restaurant_repository_factory = restaurant_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._address_repository_factory = address_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateBranchRequestDTO) -> BranchDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            restaurant_repo = self._restaurant_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            address_repo = self._address_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            restaurant = await restaurant_repo.get_by_id(tenant_id, request.restaurant_id)
            if restaurant is None:
                raise RestaurantNotFoundError(request.restaurant_id)

            existing = await branch_repo.get_by_restaurant_id_and_name(
                tenant_id, request.restaurant_id, request.name
            )
            if existing is not None:
                raise BranchNameConflictError(request.restaurant_id, request.name)

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

            branch_id = generate_ulid()
            invoice_prefix = request.invoice_prefix or default_invoice_prefix(
                request.name, branch_id
            )
            if request.gstin is not None:
                conflict = await branch_repo.get_by_gstin_and_invoice_prefix(
                    tenant_id, request.gstin, invoice_prefix
                )
                if conflict is not None:
                    raise InvoicePrefixConflictError(request.gstin, invoice_prefix)

            branch = Branch(
                id=branch_id,
                tenant_id=tenant_id,
                restaurant_id=request.restaurant_id,
                name=request.name,
                status=BranchStatus.OPENED,
                created_at=now,
                address_id=address_id,
                gstin=request.gstin,
                invoice_prefix=invoice_prefix,
            )
            branch.activate()
            branch = await branch_repo.create(branch)

            await outbox.publish(
                tenant_id,
                BranchCreated(
                    branch_id=branch.id,
                    restaurant_id=branch.restaurant_id,
                    name=branch.name,
                    occurred_at=now,
                ),
            )

        return branch_to_dto(branch, address)
