from __future__ import annotations

from decimal import Decimal

from restaurant_os_api.modules.operations.application.dto import CashDrawerDTO
from restaurant_os_api.modules.operations.domain.entities import CashDrawer


def cash_drawer_to_dto(
    cash_drawer: CashDrawer,
    *,
    expected_cash_amount: Decimal | None = None,
) -> CashDrawerDTO:
    variance = None
    if expected_cash_amount is not None and cash_drawer.closing_counted_amount is not None:
        variance = cash_drawer.closing_counted_amount - expected_cash_amount
    return CashDrawerDTO(
        id=cash_drawer.id,
        tenant_id=cash_drawer.tenant_id,
        branch_id=cash_drawer.branch_id,
        status=cash_drawer.status.value,
        opening_float_amount=cash_drawer.opening_float_amount,
        opened_at=cash_drawer.opened_at,
        created_at=cash_drawer.created_at,
        terminal_id=cash_drawer.terminal_id,
        closing_counted_amount=cash_drawer.closing_counted_amount,
        closed_at=cash_drawer.closed_at,
        expected_cash_amount=expected_cash_amount,
        variance_amount=variance,
    )
