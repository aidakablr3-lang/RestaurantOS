"""Tenant lifecycle domain events.

Framework-agnostic plain data (Technical Architecture v2.0 SS2.2: no
Infrastructure imports in Domain) — each satisfies the
``platform.events.DomainEvent`` structural contract so
``TenantProvisioningService`` and the lifecycle use cases can hand them
to the ``OutboxWriter`` port uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class TenantCreated:
    tenant_id: str
    legal_name: str
    display_name: str
    tenant_tier: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TenantCreated"
    aggregate_type: ClassVar[str] = "tenant"

    @property
    def aggregate_id(self) -> str:
        return self.tenant_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "tenantId": self.tenant_id,
            "legalName": self.legal_name,
            "displayName": self.display_name,
            "tenantTier": self.tenant_tier,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TenantSuspended:
    tenant_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TenantSuspended"
    aggregate_type: ClassVar[str] = "tenant"

    @property
    def aggregate_id(self) -> str:
        return self.tenant_id

    def to_payload(self) -> dict[str, Any]:
        return {"tenantId": self.tenant_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class TenantReactivated:
    tenant_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TenantReactivated"
    aggregate_type: ClassVar[str] = "tenant"

    @property
    def aggregate_id(self) -> str:
        return self.tenant_id

    def to_payload(self) -> dict[str, Any]:
        return {"tenantId": self.tenant_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class TenantOffboarded:
    tenant_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TenantOffboarded"
    aggregate_type: ClassVar[str] = "tenant"

    @property
    def aggregate_id(self) -> str:
        return self.tenant_id

    def to_payload(self) -> dict[str, Any]:
        return {"tenantId": self.tenant_id, "occurredAt": self.occurred_at.isoformat()}
