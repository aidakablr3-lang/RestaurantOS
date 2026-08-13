"""Supplier entity -- tenant-level, NOT branch-scoped (Architecture doc
SS3.7: a supplier typically serves every branch of a tenant). Status is
a trivial active/inactive toggle (unlike PurchaseOrder's real workflow
graph), so it is set directly by ``UpdateSupplierUseCase``'s full-replace
PATCH rather than through dedicated guarded transition methods --
disclosed as a deliberate simplification against this codebase's usual
"dedicated action route per transition" precedent (``Branch``,
``PurchaseOrder``), reasonable here because there is no invalid-order
sequencing to guard against."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class SupplierStatus(StrEnum):
    ACTIVE = "active"
    INACTIVE = "inactive"


@dataclass(slots=True)
class Supplier:
    id: str
    tenant_id: str
    name: str
    status: SupplierStatus
    created_at: datetime
    address_id: str | None = None
