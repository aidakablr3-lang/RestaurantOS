"""ConfirmGoodsReceiptUseCase.

Flat ``POST /api/v1/purchase-orders/{id}/receipts`` -- the largest use
case in this step, mirroring ``RecordPaymentUseCase``'s own shape: it
creates a ``GoodsReceipt`` and immediately confirms it in the same
call (no separate async receiving workflow -- see ``goods_receipt.py``'s
own docstring), and every line item's stock movement posts in the same
transaction as the fact itself.

For each requested line: increments the matching ``PurchaseOrderItem
.quantity_received``, writes a ``StockMovement(movement_type='receipt')``
row against that item's own ``InventoryItem`` (using the inventory
item's own ``branch_id``, not necessarily the PO's -- the same
disclosed Recipe/InventoryItem branch tension carried over here), and
runs the shared ``ensure_not_negative`` pre-check (narrow but real: a
receipt only *adds* stock, but if the balance was already negative via
an override-permitted deduction, a partial receipt can still leave it
negative). **Discrepancy rule, a disclosed simplification, not
inherited from the architecture doc (which only says "discrepancy
flag(s)" without defining one):** a line is flagged as a discrepancy
if this receipt takes its cumulative ``quantity_received`` **above**
``quantity_ordered`` -- an under-receipt is a normal partial delivery
(tracked via the PO's own ``partially_received`` status), not treated
as a discrepancy in itself.

After all lines post, the PO's own status is recomputed from the real
line totals (`apply_receipt_status`) -- never chosen by the caller.
Publishes ``PurchaseOrderReceived``.
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
    ConfirmGoodsReceiptRequestDTO,
    GoodsReceiptDTO,
)
from restaurant_os_api.modules.operations.application.use_cases._purchase_order_mapper import (
    goods_receipt_to_dto,
    purchase_order_to_dto,
)
from restaurant_os_api.modules.operations.application.use_cases._stock_guard import (
    ensure_not_negative,
)
from restaurant_os_api.modules.operations.domain.entities import (
    GoodsReceipt,
    GoodsReceiptStatus,
    StockMovement,
    StockMovementType,
)
from restaurant_os_api.modules.operations.domain.events import PurchaseOrderReceived
from restaurant_os_api.modules.operations.domain.exceptions import (
    InventoryItemNotFoundError,
    PurchaseOrderItemNotFoundError,
    PurchaseOrderNotFoundError,
)
from restaurant_os_api.modules.operations.domain.ports import (
    GoodsReceiptRepository,
    InventoryItemRepository,
    PurchaseOrderRepository,
    StockMovementRepository,
)
from restaurant_os_api.modules.restaurant.application.branch_authorization import (
    resolve_and_authorize_branch,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

PERMISSION_CODE = "purchasing.manage"


class ConfirmGoodsReceiptUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        purchase_order_repository_factory: Callable[[AsyncSession], PurchaseOrderRepository],
        goods_receipt_repository_factory: Callable[[AsyncSession], GoodsReceiptRepository],
        inventory_item_repository_factory: Callable[[AsyncSession], InventoryItemRepository],
        stock_movement_repository_factory: Callable[[AsyncSession], StockMovementRepository],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._purchase_order_repository_factory = purchase_order_repository_factory
        self._goods_receipt_repository_factory = goods_receipt_repository_factory
        self._inventory_item_repository_factory = inventory_item_repository_factory
        self._stock_movement_repository_factory = stock_movement_repository_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(
        self, tenant_id: str, user_id: str, request: ConfirmGoodsReceiptRequestDTO
    ) -> GoodsReceiptDTO:
        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            po_repo = self._purchase_order_repository_factory(uow.session)
            goods_receipt_repo = self._goods_receipt_repository_factory(uow.session)
            inventory_item_repo = self._inventory_item_repository_factory(uow.session)
            movement_repo = self._stock_movement_repository_factory(uow.session)
            branch_repo = self._branch_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            purchase_order = await po_repo.get_by_id(tenant_id, request.purchase_order_id)
            if purchase_order is None:
                raise PurchaseOrderNotFoundError(request.purchase_order_id)

            resolved_permissions = await self._resolve_user_permissions.execute(tenant_id, user_id)
            await resolve_and_authorize_branch(
                branch_repository=branch_repo,
                tenant_id=tenant_id,
                branch_id=purchase_order.branch_id,
                resolved_permissions=resolved_permissions,
                permission_code=PERMISSION_CODE,
            )

            purchase_order.ensure_receivable()

            receipt = await goods_receipt_repo.create(
                GoodsReceipt(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    purchase_order_id=purchase_order.id,
                    status=GoodsReceiptStatus.CREATED,
                    received_at=now,
                    created_at=now,
                )
            )

            all_po_items = {
                item.id: item for item in await po_repo.get_items(tenant_id, purchase_order.id)
            }

            has_discrepancy = False
            for line in request.lines:
                po_item = all_po_items.get(line.purchase_order_item_id)
                if po_item is None or po_item.purchase_order_id != purchase_order.id:
                    raise PurchaseOrderItemNotFoundError(line.purchase_order_item_id)

                inventory_item = await inventory_item_repo.get_by_id(
                    tenant_id, po_item.inventory_item_id
                )
                if inventory_item is None:
                    raise InventoryItemNotFoundError(po_item.inventory_item_id)

                item_branch = await branch_repo.get_by_id(tenant_id, inventory_item.branch_id)
                if item_branch is None:
                    raise BranchNotFoundError(inventory_item.branch_id)

                ensure_not_negative(
                    inventory_item,
                    item_branch,
                    previous_quantity=inventory_item.quantity_on_hand,
                    quantity_delta=line.quantity_received,
                )

                await movement_repo.create_movement(
                    StockMovement(
                        id=generate_ulid(),
                        tenant_id=tenant_id,
                        branch_id=inventory_item.branch_id,
                        inventory_item_id=inventory_item.id,
                        movement_type=StockMovementType.RECEIPT,
                        quantity_delta=line.quantity_received,
                        occurred_at=now,
                        created_at=now,
                        reference_type="goods_receipt",
                        reference_id=receipt.id,
                    )
                )

                po_item.receive(line.quantity_received)
                await po_repo.update_item(po_item)
                all_po_items[po_item.id] = po_item
                if po_item.quantity_received > po_item.quantity_ordered:
                    has_discrepancy = True

            refreshed_items = list(all_po_items.values())
            fully_received = all(
                item.quantity_received >= item.quantity_ordered for item in refreshed_items
            )
            purchase_order.apply_receipt_status(fully_received=fully_received)
            purchase_order = await po_repo.update(purchase_order)

            receipt.has_discrepancy = has_discrepancy
            receipt.confirm()
            receipt = await goods_receipt_repo.update(receipt)

            await outbox.publish(
                tenant_id,
                PurchaseOrderReceived(
                    purchase_order_id=purchase_order.id,
                    goods_receipt_id=receipt.id,
                    has_discrepancy=has_discrepancy,
                    occurred_at=now,
                ),
            )

        return goods_receipt_to_dto(receipt, purchase_order_to_dto(purchase_order, refreshed_items))
