"""Pydantic request/response schemas for ModifierGroup CRUD (Sprint 5 Step 4.9)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.domain.entities import ModifierSelectionType


class CreateModifierGroupRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    selection_type: ModifierSelectionType


class UpdateModifierGroupRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    selection_type: ModifierSelectionType


class ModifierGroupResponseSchema(CamelModel):
    id: str
    tenant_id: str
    name: str
    selection_type: str
    created_at: datetime
