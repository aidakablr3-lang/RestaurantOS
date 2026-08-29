"""Repository port for the per-(tenant, branch, financial year)
invoice number counter.

Deliberately a single atomic method, not a CRUD-shaped port -- the
whole point of this repository is that "read the current value" and
"increment it" are never two separate steps a caller could interleave
with. See the SQLAlchemy implementation for the actual DB-level
guarantee (a single ``INSERT ... ON CONFLICT ... DO UPDATE ...
RETURNING``, not application-level locking).
"""

from __future__ import annotations

from typing import Protocol


class InvoiceNumberCounterRepository(Protocol):
    async def allocate_next(self, tenant_id: str, branch_id: str, financial_year: str) -> int:
        """Atomically returns the next sequence number for this
        (tenant, branch, financial_year), creating the counter at 1 on
        first use. Two concurrent callers for the same key are
        guaranteed distinct, strictly increasing results -- enforced
        by the database, not by this method's own logic."""
        ...
