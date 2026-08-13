"""Application-layer DTOs for the guest-facing QR ordering menu view.

Deliberately a distinct, minimal read model from ``MenuItemDTO``/
``MenuCategoryDTO`` -- the same "own contract, not the authenticated
shape" discipline ``QRCodeResolutionDTO`` already established against
``QRCodeDTO``. A guest never sees ``recipe_id``, ``station``,
``tenant_id``, or unavailable items; branch-price/availability
overrides are not resolved here for the same disclosed reason
``AddOrderItemUseCase`` doesn't resolve them -- no reusable "effective
price" helper exists in this codebase yet.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class GuestMenuItemDTO:
    id: str
    name: str
    price_amount: Decimal
    currency_code: str


@dataclass(frozen=True, slots=True)
class GuestMenuCategoryDTO:
    id: str
    name: str
    display_order: int
    items: list[GuestMenuItemDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class GuestMenuDTO:
    branch_id: str
    table_id: str
    restaurant_name: str
    branch_name: str
    table_number: str
    categories: list[GuestMenuCategoryDTO]
