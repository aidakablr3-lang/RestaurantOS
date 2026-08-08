"""Application-layer DTOs for TableZone CRUD (Sprint 5 Step 4.4)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateTableZoneRequestDTO:
    branch_id: str
    name: str
    display_order: int = 0


@dataclass(frozen=True, slots=True)
class UpdateTableZoneRequestDTO:
    table_zone_id: str
    branch_id: str
    name: str
    display_order: int


@dataclass(frozen=True, slots=True)
class TableZoneDTO:
    id: str
    tenant_id: str
    branch_id: str
    name: str
    display_order: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TableZoneListResultDTO:
    table_zones: list[TableZoneDTO]
    total: int
    offset: int
    limit: int
