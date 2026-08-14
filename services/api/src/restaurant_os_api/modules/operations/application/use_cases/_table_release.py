"""Shared table-release helper.

Extracted so ``CloseOrderUseCase``, ``VoidOrderUseCase``, and
``RecordPaymentUseCase`` (once a payment fully settles a bill) all
release a dine-in order's table the same way, rather than each
duplicating the guard -- the same "extracted, not duplicated" shape
``_stock_guard.py`` already established between Inventory and
Purchasing.

Only ever claims the transition it itself makes: a table a staff
member has since moved to ``cleaning``/``reserved`` themselves is left
alone.

A table stays ``occupied`` as long as ANY other order against it is
still active (status not ``closed``/``voided``) -- e.g. a second
round ordered onto the same table before the first round's bill is
paid. Only the settlement/void/close of the LAST remaining active
order actually flips the table to ``available`` (Phase 2.1 defect
remediation: previously this released the table on every single
order's own settlement, regardless of siblings).
"""

from __future__ import annotations

from restaurant_os_api.modules.operations.domain.ports import OrderRepository
from restaurant_os_api.modules.restaurant.domain.entities import TableStatus
from restaurant_os_api.modules.restaurant.domain.ports import TableRepository


async def release_table_if_occupied(
    table_repository: TableRepository,
    order_repository: OrderRepository,
    tenant_id: str,
    table_id: str,
) -> None:
    table = await table_repository.get_by_id(tenant_id, table_id)
    if table is None or table.status != TableStatus.OCCUPIED:
        return
    if await order_repository.has_active_orders_for_table(tenant_id, table_id):
        return
    table.status = TableStatus.AVAILABLE
    await table_repository.update(table)
