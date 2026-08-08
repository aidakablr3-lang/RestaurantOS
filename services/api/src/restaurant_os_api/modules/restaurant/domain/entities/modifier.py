"""Modifier entity.

Restaurant Platform Architecture SS3.1: an individual selectable option
within a ``ModifierGroup``. ``price_delta`` may be negative (a "remove
ingredient" discount-adjacent modifier).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class Modifier:
    id: str
    tenant_id: str
    modifier_group_id: str
    name: str
    created_at: datetime
    price_delta: Decimal = Decimal(0)
