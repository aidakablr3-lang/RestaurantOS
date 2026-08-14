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

    async def get_by_id_for_update(self, tenant_id: str, bill_id: str) -> Bill | None:
        """Same as ``get_by_id``, but takes a row lock (``SELECT ... FOR
        UPDATE``) held for the rest of the caller's transaction.

        Use for any read-modify-write sequence against a bill's paid
        state (e.g. the overpayment guard in ``RecordPaymentUseCase``) so
        concurrent requests against the same bill serialize instead of
        each reading a stale snapshot and both passing a guard that only
        one of them should.
        """
        ...

    async def get_by_order_id(self, tenant_id: str, order_id: str) -> Bill | None: ...

    async def create(self, bill: Bill) -> Bill: ...

    async def update(self, bill: Bill) -> Bill: ...

    async def add_tax_line(self, tax_line: OrderTaxLine) -> OrderTaxLine: ...

    async def get_tax_lines_for_order(
        self, tenant_id: str, order_id: str
    ) -> list[OrderTaxLine]: ...

    async def add_adjustment(self, adjustment: BillAdjustment) -> BillAdjustment: ...

    async def get_adjustments(self, tenant_id: str, bill_id: str) -> list[BillAdjustment]: ...
