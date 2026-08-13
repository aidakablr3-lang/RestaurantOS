"""Shared negative-inventory pre-check, extracted so
``RecordStockMovementUseCase`` and ``ConfirmGoodsReceiptUseCase`` (Step
6) don't each duplicate the same replica of the ``stock_movements``
trigger's own ``COALESCE(item_override, branch_allows_negative,
false)`` precedence. See ``InsufficientStockError``'s own docstring for
why this pre-check exists at all alongside the trigger."""

from __future__ import annotations

from decimal import Decimal

from restaurant_os_api.modules.operations.domain.entities import InventoryItem
from restaurant_os_api.modules.operations.domain.exceptions import InsufficientStockError
from restaurant_os_api.modules.restaurant.domain.entities import Branch


def ensure_not_negative(
    item: InventoryItem, branch: Branch, *, previous_quantity: Decimal, quantity_delta: Decimal
) -> None:
    resulting_quantity = previous_quantity + quantity_delta
    if resulting_quantity < 0:
        allowed = (
            item.allow_negative_stock_override
            if item.allow_negative_stock_override is not None
            else branch.allow_negative_stock
        )
        if not allowed:
            raise InsufficientStockError(item.id, str(previous_quantity), str(quantity_delta))
