"""Pydantic request/response schemas for Modifier CRUD (Sprint 5 Step 4.9).

``modifier_group_id`` is deliberately absent from both request schemas
-- it is scope (the URL's own path parameter), not an editable field,
matching ``MenuItemRequestSchema``'s own precedent for
``menu_category_id``.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateModifierRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_delta: Decimal = Decimal(0)


class UpdateModifierRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    price_delta: Decimal = Decimal(0)


class ModifierResponseSchema(CamelModel):
    id: str
    tenant_id: str
    modifier_group_id: str
    name: str
    price_delta: Decimal
    created_at: datetime
