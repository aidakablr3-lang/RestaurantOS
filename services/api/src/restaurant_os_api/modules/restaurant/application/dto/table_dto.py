"""Application-layer DTOs for Table CRUD (Sprint 5 Step 4.5).

``status`` is deliberately absent from ``CreateTableRequestDTO`` and
``UpdateTableRequestDTO`` -- a new table always starts ``available``
(the DB's own ``server_default``), and every subsequent status change
goes through ``ChangeTableStatusRequestDTO`` / the dedicated
``POST /api/v1/tables/{id}/status`` endpoint (Architecture SS7's own
explicit split), never a generic field set on the CRUD routes.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateTableRequestDTO:
    branch_id: str
    table_zone_id: str
    table_number: str
    capacity: int


@dataclass(frozen=True, slots=True)
class UpdateTableRequestDTO:
    table_id: str
    branch_id: str
    table_zone_id: str
    table_number: str
    capacity: int


@dataclass(frozen=True, slots=True)
class ChangeTableStatusRequestDTO:
    table_id: str
    status: str


@dataclass(frozen=True, slots=True)
class TableDTO:
    id: str
    tenant_id: str
    branch_id: str
    table_zone_id: str
    table_number: str
    capacity: int
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TableListResultDTO:
    tables: list[TableDTO]
    total: int
    offset: int
    limit: int
