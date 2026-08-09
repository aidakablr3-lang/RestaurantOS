"""Pydantic request/response schemas for MenuItem CRUD (Sprint 5 Step 4.8).

``menu_category_id`` is deliberately absent from both request schemas
-- it is scope (the URL's own path parameter), not an editable field,
matching how ``TableZoneRequestSchema``/``BranchRequestSchema`` never
carry their own parent scope id in the body either. ``recipe_id`` is
also absent -- Architecture SS3.1 names it a reserved, unpopulated FK
target for the future Inventory Platform, not settable this sprint.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateMenuItemRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_amount: Decimal = Field(..., ge=0)
    currency_code: str = Field(..., min_length=3, max_length=3)
    is_available: bool = True
    display_order: int = 0


class UpdateMenuItemRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_amount: Decimal = Field(..., ge=0)
    currency_code: str = Field(..., min_length=3, max_length=3)
    is_available: bool = True
    display_order: int = 0


class MenuItemResponseSchema(CamelModel):
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
