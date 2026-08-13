"""Repository port for CashDrawer."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal
from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import CashDrawer


class CashDrawerRepository(Protocol):
    async def get_by_id(self, tenant_id: str, cash_drawer_id: str) -> CashDrawer | None: ...

    async def get_open_for_branch(self, tenant_id: str, branch_id: str) -> CashDrawer | None: ...

    async def create(self, cash_drawer: CashDrawer) -> CashDrawer: ...

    async def update(self, cash_drawer: CashDrawer) -> CashDrawer: ...

    async def sum_settled_cash_payments(
        self, tenant_id: str, branch_id: str, *, since: datetime
    ) -> Decimal:
        """The Decimal sum of settled cash Payments for this branch
        since the drawer opened -- the reconciliation figure
        ``CloseCashDrawerUseCase`` compares against the counted amount."""
        ...
