"""Application-layer DTOs for MenuItem CRUD (Sprint 5 Step 4.8).

``station`` (added for kitchen/bar station routing) defaults to
``"kitchen"`` on create, matching ``MenuItem.station``'s own default --
existing callers that don't know about stations yet keep getting the
pre-existing single-ticket-per-order behavior.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateMenuItemRequestDTO:
    menu_category_id: str
    name: str
    price_amount: Decimal
    currency_code: str
    is_available: bool = True
    display_order: int = 0
    station: str = "kitchen"


@dataclass(frozen=True, slots=True)
class UpdateMenuItemRequestDTO:
    menu_item_id: str
    menu_category_id: str
    name: str
    price_amount: Decimal
    currency_code: str
    is_available: bool
    display_order: int
    station: str


@dataclass(frozen=True, slots=True)
class MenuItemDTO:
    id: str
    tenant_id: str
    menu_category_id: str
    name: str
    price_amount: Decimal
    currency_code: str
    is_available: bool
    display_order: int
    recipe_id: str | None
    created_at: datetime
    station: str


@dataclass(frozen=True, slots=True)
class MenuItemListResultDTO:
    menu_items: list[MenuItemDTO]
    total: int
    offset: int
    limit: int
