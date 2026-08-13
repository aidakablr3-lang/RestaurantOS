"""Repository port for Payment + Refund -- everything involved in
money movement against one Bill."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from restaurant_os_api.modules.operations.domain.entities import Payment, Refund


class PaymentRepository(Protocol):
    async def get_by_id(self, tenant_id: str, payment_id: str) -> Payment | None: ...

    async def create(self, payment: Payment) -> Payment: ...

    async def update(self, payment: Payment) -> Payment: ...

    async def list_for_bill(self, tenant_id: str, bill_id: str) -> list[Payment]: ...

    async def list_settled_for_branch_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Payment]: ...

    async def get_refund_by_id(self, tenant_id: str, refund_id: str) -> Refund | None: ...

    async def create_refund(self, refund: Refund) -> Refund: ...

    async def update_refund(self, refund: Refund) -> Refund: ...

    async def list_refunds_for_payment(self, tenant_id: str, payment_id: str) -> list[Refund]: ...

    async def list_processed_refunds_for_branch_between(
        self, tenant_id: str, branch_id: str, start: datetime, end: datetime
    ) -> list[Refund]: ...
