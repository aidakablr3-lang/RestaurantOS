"""Application-layer DTOs for tenant lifecycle and administration.

Technical Architecture v2.0 SS5.6: distinct from the presentation
layer's Pydantic schemas, same reasoning as ``auth_dto.py`` — a use
case's unit tests never need FastAPI/Pydantic installed.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any


@dataclass(frozen=True, slots=True)
class OnboardTenantRequestDTO:
    legal_name: str
    display_name: str
    default_currency_code: str


@dataclass(frozen=True, slots=True)
class UpdateTenantRequestDTO:
    tenant_id: str
    display_name: str
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True, slots=True)
class ListTenantsRequestDTO:
    offset: int = 0
    limit: int = 20
    status: str | None = None


@dataclass(frozen=True, slots=True)
class TenantDTO:
    id: str
    legal_name: str
    display_name: str
    tenant_tier: str
    status: str
    default_currency_code: str
    metadata: dict[str, Any]
    created_at: datetime


@dataclass(frozen=True, slots=True)
class TenantListResultDTO:
    tenants: list[TenantDTO]
    total: int
    offset: int
    limit: int
