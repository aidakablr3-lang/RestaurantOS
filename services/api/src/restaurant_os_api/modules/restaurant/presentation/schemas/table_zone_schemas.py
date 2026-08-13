"""Pydantic request/response schemas for TableZone CRUD (Sprint 5 Step 4.4)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateTableZoneRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_order: int = 0


class UpdateTableZoneRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    display_order: int = 0


class TableZoneResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    name: str
    display_order: int
    created_at: datetime
