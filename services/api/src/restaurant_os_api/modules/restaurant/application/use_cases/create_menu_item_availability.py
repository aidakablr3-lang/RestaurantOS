"""CreateMenuItemAvailabilityUseCase.

Restaurant Platform Architecture SS7's ``PUT /api/v1/menu-items/{id}/
availability`` -- the availability-dimension twin of
``CreateMenuItemBranchPriceUseCase``, identical shape applied to
``is_available`` instead of ``price_amount``.

Publishes ``MenuItemAvailabilityChanged`` with ``branch_id`` set (a
branch-scoped change) -- the event's own ``branch_id`` field is
nullable only for a *global* change, which nothing in this step
produces (the base ``menu_items.is_available`` flag is edited via
``UpdateMenuItemUseCase``/``MenuItemUpdated`` instead, per Step 4.8).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.application.dto import (
    CreateMenuItemAvailabilityRequestDTO,
    MenuItemAvailabilityDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_availability_mapper import (
    menu_item_availability_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuItemAvailability
from restaurant_os_api.modules.restaurant.domain.events import MenuItemAvailabilityChanged
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuItemAvailabilityRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "menu.manage"


class CreateMenuItemAvailabilityUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        menu_item_availability_repository_factory: Callable[
            [AsyncSession], MenuItemAvailabilityRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_availability_repository_factory = menu_item_availability_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: CreateMenuItemAvailabilityRequestDTO
    ) -> MenuItemAvailabilityDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            availability_repo = self._menu_item_availability_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            menu_item = await menu_item_repo.get_by_id(tenant_id, request.menu_item_id)
            if menu_item is None:
                raise MenuItemNotFoundError(request.menu_item_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=request.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            row = await availability_repo.create(
                MenuItemAvailability(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    menu_item_id=request.menu_item_id,
                    is_available=request.is_available,
                    effective_from=request.effective_from,
                    effective_to=request.effective_to,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                MenuItemAvailabilityChanged(
                    menu_item_id=row.menu_item_id,
                    branch_id=row.branch_id,
                    is_available=row.is_available,
                    occurred_at=now,
                ),
            )

        return menu_item_availability_to_dto(row)
