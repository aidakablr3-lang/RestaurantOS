"""Application-layer DTOs for Modifier CRUD (Sprint 5 Step 4.9).

No list-result wrapper -- ``ModifierRepository.list_for_group`` is
unpaginated (mirrors ``QRCodeRepository.list_for_table``'s own shape),
so ``ListModifiersUseCase`` returns a plain ``list[ModifierDTO]``.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class CreateModifierRequestDTO:
    modifier_group_id: str
    name: str
    price_delta: Decimal = Decimal(0)


@dataclass(frozen=True, slots=True)
class UpdateModifierRequestDTO:
    modifier_id: str
    modifier_group_id: str
    name: str
    price_delta: Decimal


@dataclass(frozen=True, slots=True)
class ModifierDTO:
    id: str
    tenant_id: str
    modifier_group_id: str
    name: str
    price_delta: Decimal
    created_at: datetime
