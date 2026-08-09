"""Pydantic request/response schemas for Table CRUD (Sprint 5 Step 4.5).

``status`` is deliberately absent from the create/update request
schemas -- see ``application/dto/table_dto.py``'s own docstring for
why (Architecture SS7's dedicated status-change endpoint).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.domain.entities import TableStatus


class CreateTableRequestSchema(CamelModel):
    table_zone_id: str = Field(..., min_length=26, max_length=26)
    table_number: str = Field(..., min_length=1, max_length=255)
    capacity: int = Field(..., gt=0)


class UpdateTableRequestSchema(CamelModel):
    table_zone_id: str = Field(..., min_length=26, max_length=26)
    table_number: str = Field(..., min_length=1, max_length=255)
    capacity: int = Field(..., gt=0)


class ChangeTableStatusRequestSchema(CamelModel):
    status: TableStatus


class TableResponseSchema(CamelModel):
    id: str
    tenant_id: str
    branch_id: str
    table_zone_id: str
    table_number: str
    capacity: int
    status: str
    created_at: datetime
