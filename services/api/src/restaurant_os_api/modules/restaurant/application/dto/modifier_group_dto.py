"""Application-layer DTOs for ModifierGroup CRUD (Sprint 5 Step 4.9)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateModifierGroupRequestDTO:
    name: str
    selection_type: str


@dataclass(frozen=True, slots=True)
class UpdateModifierGroupRequestDTO:
    modifier_group_id: str
    name: str
    selection_type: str


@dataclass(frozen=True, slots=True)
class ModifierGroupDTO:
    id: str
    tenant_id: str
    name: str
    selection_type: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class ModifierGroupListResultDTO:
    modifier_groups: list[ModifierGroupDTO]
    total: int
    offset: int
    limit: int
