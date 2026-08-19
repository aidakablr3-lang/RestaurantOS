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
    owner_email: str
    owner_phone: str | None = None


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
    # Only populated on the response to an *onboard* call (Phase 1 design
    # doc SSA.4's atomic first-Owner provisioning) -- every other tenant
    # lifecycle use case sharing this DTO (get/list/update/suspend/
    # reactivate/offboard) leaves these at their default. Mirrors
    # UserDTO.generated_password's own "shown exactly once" convention --
    # owner_activation_token is the raw, one-time token; only its hash is
    # ever persisted.
    owner_id: str | None = None
    owner_email: str | None = None
    owner_activation_token: str | None = None


@dataclass(frozen=True, slots=True)
class TenantListResultDTO:
    tenants: list[TenantDTO]
    total: int
    offset: int
    limit: int
