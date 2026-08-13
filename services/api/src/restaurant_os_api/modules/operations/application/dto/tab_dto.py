"""Application-layer DTOs for Tab (Sprint 7 Step 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateTabRequestDTO:
    branch_id: str
    table_id: str | None = None


@dataclass(frozen=True, slots=True)
class TabDTO:
    id: str
    tenant_id: str
    branch_id: str
    status: str
    opened_at: datetime
    created_at: datetime
    table_id: str | None
    customer_id: str | None
    closed_at: datetime | None
