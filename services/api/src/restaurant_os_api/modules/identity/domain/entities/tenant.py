"""Tenant entity.

The root of all tenant-scoped data (Data Architecture v2.0 SS3.1). This
entity is intentionally thin for the login/refresh/logout slice — it
carries only what authentication needs to check (is this tenant allowed
to authenticate right now), not the full tenant-management surface
(subscription, branding, etc.), which belongs to a later PR.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.identity.domain.exceptions import TenantNotActiveError


class TenantTier(StrEnum):
    SHARED = "shared"
    DEDICATED = "dedicated"


class TenantStatus(StrEnum):
    PROVISIONING = "provisioning"
    ACTIVE = "active"
    SUSPENDED = "suspended"
    MIGRATING = "migrating"
    OFFBOARDED = "offboarded"


@dataclass(slots=True)
class Tenant:
    id: str
    legal_name: str
    display_name: str
    tenant_tier: TenantTier
    status: TenantStatus
    default_currency_code: str
    created_at: datetime

    def ensure_can_authenticate(self) -> None:
        """Raise if this tenant is not allowed to have new sessions created.

        Data Architecture v2.0 SS4.5: a suspended tenant's data is
        untouched, but new sessions must be rejected immediately — this
        is the domain-layer half of that guarantee; the auth middleware
        enforces the same check on every subsequent request via the
        Redis-cached permission/session state (Technical Architecture
        v2.0 Group C).
        """
        if self.status not in (TenantStatus.ACTIVE, TenantStatus.MIGRATING):
            raise TenantNotActiveError(self.id, self.status.value)
