"""User domain events.

Framework-agnostic plain data (Technical Architecture v2.0 SS2.2),
satisfying the ``platform.events.DomainEvent`` structural contract
exactly like ``tenant_events.py``/``rbac_events.py`` — published
through the existing ``OutboxWriter`` port, no new event infrastructure.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class UserCreated:
    user_id: str
    tenant_id: str
    email: str | None
    # None for the one caller with no delegating actor: atomic first-Owner
    # provisioning (TenantProvisioningService.provision(), Phase 1 design
    # doc SSA.4) is a system operation, not a human- or API-caller-initiated
    # grant -- there is no user to attribute it to.
    created_by_user_id: str | None
    occurred_at: datetime

    event_type: ClassVar[str] = "UserCreated"
    aggregate_type: ClassVar[str] = "user"

    @property
    def aggregate_id(self) -> str:
        return self.user_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "userId": self.user_id,
            "tenantId": self.tenant_id,
            "email": self.email,
            "createdByUserId": self.created_by_user_id,
            "occurredAt": self.occurred_at.isoformat(),
        }
