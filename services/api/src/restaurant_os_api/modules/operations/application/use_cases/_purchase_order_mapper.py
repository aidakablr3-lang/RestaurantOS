from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import (
    GoodsReceiptDTO,
    PurchaseOrderDTO,
    PurchaseOrderItemDTO,
)
from restaurant_os_api.modules.operations.domain.entities import (
    GoodsReceipt,
    PurchaseOrder,
    PurchaseOrderItem,
)


def purchase_order_item_to_dto(item: PurchaseOrderItem) -> PurchaseOrderItemDTO:
    return PurchaseOrderItemDTO(
        id=item.id,
        purchase_order_id=item.purchase_order_id,
        inventory_item_id=item.inventory_item_id,
        quantity_ordered=item.quantity_ordered,
        quantity_received=item.quantity_received,
        created_at=item.created_at,
    )


def purchase_order_to_dto(
    purchase_order: PurchaseOrder, items: list[PurchaseOrderItem]
) -> PurchaseOrderDTO:
    return PurchaseOrderDTO(
        id=purchase_order.id,
        tenant_id=purchase_order.tenant_id,
        branch_id=purchase_order.branch_id,
        supplier_id=purchase_order.supplier_id,
        status=purchase_order.status.value,
        created_at=purchase_order.created_at,
        items=[purchase_order_item_to_dto(i) for i in items],
    )


def goods_receipt_to_dto(
    goods_receipt: GoodsReceipt, purchase_order: PurchaseOrderDTO
) -> GoodsReceiptDTO:
    return GoodsReceiptDTO(
        id=goods_receipt.id,
        tenant_id=goods_receipt.tenant_id,
        purchase_order_id=goods_receipt.purchase_order_id,
        status=goods_receipt.status.value,
        received_at=goods_receipt.received_at,
        created_at=goods_receipt.created_at,
        has_discrepancy=goods_receipt.has_discrepancy,
        purchase_order=purchase_order,
    )
