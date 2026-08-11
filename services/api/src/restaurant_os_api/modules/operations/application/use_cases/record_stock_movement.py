"""RecordStockMovementUseCase.

Flat ``POST /api/v1/inventory-items/{id}/stock-movements`` -- same
coarse/fine authorization split as every other flat Operations route:
the router gates a coarse ``require_permission_at_any_scope("inventory.manage")``,
this use case loads the item and calls ``resolve_and_authorize_branch``
against its real ``branch_id``.

Only ``adjustment``/``waste``/``transfer`` are accepted here (enforced
by the presentation schema's own ``Literal`` type, not repeated as a
domain check) -- ``sale_deduction`` is system-internal (written by a
future order-close integration, not built in this step -- see
``stock_movement.py``'s own docstring) and ``receipt`` belongs to Step
6 (Purchasing)'s ``GoodsReceipt`` confirmation flow.

``movement_type='adjustment'`` always creates a linked
``StockAdjustment`` row requiring ``reason``/``approved_by_user_id``
(``StockAdjustmentRequiresReasonError`` otherwise) -- ``waste``/
``transfer`` do not (the architecture doc ties ``StockAdjustment``
specifically to the ``adjustment`` movement type, not every manual
movement). ``waste`` deltas are server-forced negative (waste only
ever removes stock) -- the same "never trust caller-supplied sign"
discipline ``ApplyBillAdjustmentUseCase`` established for
discount/comp/write-off vs. service-charge/tip.

Before inserting, this use case replicates the ``stock_movements``
trigger's own ``COALESCE(item_override, branch_allows_negative, false)``
negative-inventory check (see ``InsufficientStockError``'s own
docstring) purely to raise a clean, typed error -- the trigger remains
the actual enforcement, re-checked at insert time regardless.
``quantity_on_hand`` is always re-read from a fresh repository load
after the insert (never computed client-side), since the trigger --
not this use case -- is what actually updates it.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.operations.application.dto import (
    RecordStockMovementRequestDTO,
    StockMovementDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._inventory_mapper import (
    stock_movement_to_dto,
)
from restaurant_os_api.modules.operations.domain.entities import (
    StockAdjustment,
    StockMovement,
    StockMovementType,
)
from restaurant_os_api.modules.operations.domain.events import LowStockDetected
from restaurant_os_api.modules.operations.domain.exceptions import (
    InsufficientStockError,
    InventoryItemNotFoundError,
    StockAdjustmentRequiresReasonError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    InventoryItemRepository,
    StockMovementRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "inventory.manage"


class RecordStockMovementUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        stock_movement_repository_factory: Callable[[AsyncSession], StockMovementRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._stock_movement_repository_factory = stock_movement_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: RecordStockMovementRequestDTO
    ) -> StockMovementDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            item_repo = self._inventory_item_repository_factory(uow.session)
            movement_repo = self._stock_movement_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            item = await item_repo.get_by_id(tenant_id, request.inventory_item_id)
            if item is None:
                raise InventoryItemNotFoundError(request.inventory_item_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            branch = await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=item.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            movement_type = StockMovementType(request.movement_type)
            quantity_delta = request.quantity_delta
            if movement_type is StockMovementType.WASTE:
                quantity_delta = -abs(quantity_delta)

            if movement_type is StockMovementType.ADJUSTMENT and (
                not request.reason or not request.approved_by_user_id
            ):
                raise StockAdjustmentRequiresReasonError()

            previous_quantity = item.quantity_on_hand
            resulting_quantity = previous_quantity + quantity_delta
            if resulting_quantity < 0:
                allowed = (
                    item.allow_negative_stock_override
                    if item.allow_negative_stock_override is not None
                    else branch.allow_negative_stock
                )
                if not allowed:
                    raise InsufficientStockError(
                        item.id, str(previous_quantity), str(quantity_delta)
                    )

            movement = await movement_repo.create_movement(
                StockMovement(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=item.branch_id,
                    inventory_item_id=item.id,
                    movement_type=movement_type,
                    quantity_delta=quantity_delta,
                    occurred_at=now,
                    created_at=now,
                    reference_type=request.reference_type,
                    reference_id=request.reference_id,
                )
            )

            if movement_type is StockMovementType.ADJUSTMENT:
                assert request.reason is not None
                assert request.approved_by_user_id is not None
                await movement_repo.create_adjustment(
                    StockAdjustment(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        branch_id=item.branch_id,
                        inventory_item_id=item.id,
                        reason=request.reason,
                        approved_by_user_id=request.approved_by_user_id,
                        created_at=now,
                        stock_movement_id=movement.id,
                    )
                )

            refreshed_item = await item_repo.get_by_id(tenant_id, item.id)
            assert refreshed_item is not None
            if (
                refreshed_item.reorder_point is not None
                and previous_quantity > refreshed_item.reorder_point
                and refreshed_item.quantity_on_hand <= refreshed_item.reorder_point
            ):
                await outbox.publish(
                    tenant_id,
                    LowStockDetected(
                        inventory_item_id=item.id,
                        branch_id=item.branch_id,
                        quantity_on_hand=str(refreshed_item.quantity_on_hand),
                        reorder_point=str(refreshed_item.reorder_point),
                        occurred_at=now,
                    ),
                )

        return stock_movement_to_dto(movement)
