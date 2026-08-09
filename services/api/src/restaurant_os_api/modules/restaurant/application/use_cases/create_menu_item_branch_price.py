"""CreateMenuItemBranchPriceUseCase.

Restaurant Platform Architecture SS7's ``PUT /api/v1/menu-items/{id}/
branch-price`` -- creates a new override row (the repository has no
``update()``; a new row simply supersedes an older one by
``effective_from`` ordering, matching the architecture's own "multiple
historical override windows are legitimate" framing).

``branch_id`` arrives in the request body, not the URL path -- exactly
the shape ``resolve_and_authorize_branch`` (Step 4.0 Decision 3) was
generalized for, its own docstring naming "branch price, availability"
explicitly as future call sites. ``menu_item_id`` is loaded first
(tenant-scoped only, ``MenuItemNotFoundError`` if missing/cross-tenant),
then the body's ``branch_id`` is resolved and authorized against the
caller's own resolved grants -- the same "coarse router gate,
fine-grained use-case decision" split ``ChangeTableStatusUseCase``
already established for its own flat, no-branch-in-URL route.

Publishes ``MenuItemBranchPriceChanged`` (SS11 names this event
explicitly).
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
    CreateMenuItemBranchPriceRequestDTO,
    MenuItemBranchPriceDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._menu_item_branch_price_mapper import (
    menu_item_branch_price_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import MenuItemBranchPrice
from restaurant_os_api.modules.restaurant.domain.events import MenuItemBranchPriceChanged
from restaurant_os_api.modules.restaurant.domain.exceptions import MenuItemNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    MenuItemBranchPriceRepository,
    MenuItemRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "menu.manage"


class CreateMenuItemBranchPriceUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        menu_item_repository_factory: Callable[[AsyncSession], MenuItemRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        menu_item_branch_price_repository_factory: Callable[
            [AsyncSession], MenuItemBranchPriceRepository
        ],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._menu_item_repository_factory = menu_item_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._menu_item_branch_price_repository_factory = menu_item_branch_price_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: CreateMenuItemBranchPriceRequestDTO
    ) -> MenuItemBranchPriceDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            menu_item_repo = self._menu_item_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            price_repo = self._menu_item_branch_price_repository_factory(uow.session)
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

            row = await price_repo.create(
                MenuItemBranchPrice(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    menu_item_id=request.menu_item_id,
                    price_amount=request.price_amount,
                    effective_from=request.effective_from,
                    effective_to=request.effective_to,
                    created_at=now,
                )
            )

            await outbox.publish(
                tenant_id,
                MenuItemBranchPriceChanged(
                    menu_item_id=row.menu_item_id,
                    branch_id=row.branch_id,
                    price_amount=row.price_amount,
                    effective_from=row.effective_from,
                    occurred_at=now,
                ),
            )

        return menu_item_branch_price_to_dto(row)
