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
"""

from __future__ import annotations

from restaurant_os_api.modules.restaurant.domain.entities import TableStatus
from restaurant_os_api.modules.restaurant.domain.ports import TableRepository


async def release_table_if_occupied(
    table_repository: TableRepository, tenant_id: str, table_id: str
) -> None:
    table = await table_repository.get_by_id(tenant_id, table_id)
    if table is not None and table.status == TableStatus.OCCUPIED:
        table.status = TableStatus.AVAILABLE
        await table_repository.update(table)
