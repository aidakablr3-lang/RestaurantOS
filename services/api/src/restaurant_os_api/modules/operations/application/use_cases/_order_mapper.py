from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import OrderDTO, OrderItemDTO
from restaurant_os_api.modules.operations.domain.entities import Order, OrderItem


def order_item_to_dto(item: OrderItem) -> OrderItemDTO:
    return OrderItemDTO(
        id=item.id,
        order_id=item.order_id,
        menu_item_id=item.menu_item_id,
        quantity=item.quantity,
        unit_price_amount=item.unit_price_amount,
        line_status=item.line_status.value,
        created_at=item.created_at,
        modifiers_snapshot=item.modifiers_snapshot,
        recipe_cost_snapshot=item.recipe_cost_snapshot,
    )


def order_to_dto(order: Order, items: list[OrderItem]) -> OrderDTO:
    return OrderDTO(
        id=order.id,
        tenant_id=order.tenant_id,
        branch_id=order.branch_id,
        order_source=order.order_source.value,
        status=order.status.value,
        subtotal_amount=order.subtotal_amount,
        tax_amount=order.tax_amount,
        total_amount=order.subtotal_amount + order.tax_amount,
        currency_code=order.currency_code,
        opened_at=order.opened_at,
        created_at=order.created_at,
        items=[order_item_to_dto(item) for item in items],
        table_id=order.table_id,
        tab_id=order.tab_id,
        customer_id=order.customer_id,
        closed_at=order.closed_at,
        origin_device_id=order.origin_device_id,
    )
