"""Pydantic request/response schemas for Tab (Sprint 7 Step 3)."""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateTabRequestSchema(CamelModel):
    table_id: str | None = Field(default=None, min_length=26, max_length=26)


class TabResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    status: str
    opened_at: datetime
    created_at: datetime
    table_id: str | None
    customer_id: str | None
    closed_at: datetime | None
