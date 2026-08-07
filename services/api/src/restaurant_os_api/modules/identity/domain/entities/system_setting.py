"""SystemSetting entity — tenant/branch-level configuration values.

Data Architecture v2.0 SS3.14. ``branch_id`` exists on the schema now
(so no migration is needed once the Restaurant module lands) but is
always ``None`` in this sprint — Branch does not exist yet, per Sprint
4.1's explicit scope boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


@dataclass(slots=True)
class SystemSetting:
    id: str
    tenant_id: str
    key: str
    value: dict[str, Any]
    created_at: datetime
    branch_id: str | None = None
