"""Tax entity -- tenant-scoped reference data (Architecture doc SS3.3).
No lifecycle beyond ``is_active``/soft-delete, handled at the
repository layer like every other soft-deletable entity."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class Tax:
    id: str
    tenant_id: str
    name: str
    rate: Decimal
    is_active: bool
    created_at: datetime
