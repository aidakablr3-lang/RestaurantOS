"""InventoryCategory -- tenant-level grouping (e.g. "Produce," "Dry
Goods"). Not branch-scoped -- the category itself is a naming/grouping
concern, not a stock-holding one."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum


class InventoryCategoryType(StrEnum):
    FOOD = "food"
    BEVERAGE = "beverage"


@dataclass(slots=True)
class InventoryCategory:
    id: str
    tenant_id: str
    name: str
    category_type: InventoryCategoryType
    created_at: datetime
