"""Repository port for the Bill aggregate (Bill + BillAdjustment +
OrderTaxLine -- everything involved in generating and adjusting one
Order's or Tab's bill)."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import (
    Bill,
    BillAdjustment,
    OrderTaxLine,
)


class BillRepository(Protocol):
    async def get_by_id(self, tenant_id: str, bill_id: str) -> Bill | None: ...

    async def get_by_order_id(self, tenant_id: str, order_id: str) -> Bill | None: ...

    async def create(self, bill: Bill) -> Bill: ...

    async def update(self, bill: Bill) -> Bill: ...

    async def add_tax_line(self, tax_line: OrderTaxLine) -> OrderTaxLine: ...

    async def get_tax_lines_for_order(
        self, tenant_id: str, order_id: str
    ) -> list[OrderTaxLine]: ...

    async def add_adjustment(self, adjustment: BillAdjustment) -> BillAdjustment: ...

    async def get_adjustments(self, tenant_id: str, bill_id: str) -> list[BillAdjustment]: ...
