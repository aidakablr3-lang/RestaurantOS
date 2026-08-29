"""Bill entity. Closes out either exactly one Order or an entire Tab
(Data Architecture v2.0 Group E's XOR, enforced at the DB level by
migration 0007's ``ck_bills_order_xor_tab`` CHECK constraint -- this
entity's own constructor does not re-validate it, trusting the caller
the same way ``Order``/``Tab`` trust theirs).

``amount_due``/``amount_paid`` are **not** stored fields -- Bill
carries no monetary total of its own (Architecture doc SS9); they are
computed by the use case layer from the underlying Order's totals plus
this bill's own adjustments and settled payments, then passed into this
entity's transition methods rather than recomputed here (the entity has
no repository access to compute them itself).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.operations.domain.exceptions import BillAlreadyClosedError


class BillStatus(StrEnum):
    OPEN = "open"
    PARTIALLY_PAID = "partially_paid"
    CLOSED = "closed"


@dataclass(slots=True)
class Bill:
    id: str
    tenant_id: str
    branch_id: str
    status: BillStatus
    created_at: datetime
    order_id: str | None = None
    tab_id: str | None = None
    # A GST-compliant, financial-year-scoped sequential number
    # ("{branch.invoice_prefix}/{FY}/{seq}"), allocated once at bill
    # generation and frozen here forever after -- never recomputed
    # live from the branch's current invoice_prefix. NULL when the
    # branch had no gstin on file at generation time: an invoice
    # number implies a real GST registration, and fabricating one for
    # a branch that isn't (yet, or ever) registered would misrepresent
    # a registration that doesn't exist. See GenerateBillUseCase.
    invoice_number: str | None = None

    def apply_payment_status(self, *, fully_paid: bool) -> None:
        if self.status == BillStatus.CLOSED:
            raise BillAlreadyClosedError(self.id)
        self.status = BillStatus.CLOSED if fully_paid else BillStatus.PARTIALLY_PAID
