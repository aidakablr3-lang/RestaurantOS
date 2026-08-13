"""Pydantic request/response schemas for MenuCategory CRUD (Sprint 5 Step 4.8)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateMenuCategoryRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_order: int = 0


class UpdateMenuCategoryRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_order: int = 0


class MenuCategoryResponseSchema(CamelModel):
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    display_order: int
    created_at: datetime
