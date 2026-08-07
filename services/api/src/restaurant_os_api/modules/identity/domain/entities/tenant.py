"""Tenant entity.

The root of all tenant-scoped data (Data Architecture v2.0 SS3.1). Sprint
3 kept this thin (just enough for authentication); Sprint 4.1 (Tenant
Platform) adds the lifecycle transition methods and metadata that
tenant administration needs, without touching anything Sprint 3 already
relied on.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import StrEnum
from typing import Any

from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidTenantStatusTransitionError,
    TenantNotActiveError,
)


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
    metadata: dict[str, Any] = field(default_factory=dict)

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

    def activate(self) -> None:
        """Initial activation, following successful onboarding provisioning.

        Data Architecture v2.0 SS4.5's lifecycle: provisioning -> active.
        """
        self._transition_to(TenantStatus.ACTIVE, allowed_from=(TenantStatus.PROVISIONING,))

    def suspend(self) -> None:
        """Suspend an active tenant — billing failure or manual hold.

        Data Architecture v2.0 SS4.5: "the tenant's data is untouched,
        but the Auth layer rejects new sessions" — this method only
        changes the lifecycle status; revoking already-issued sessions
        is an application-layer concern (SuspendTenantUseCase), since
        that requires the SessionRepository, which the Domain layer must
        never import.
        """
        self._transition_to(TenantStatus.SUSPENDED, allowed_from=(TenantStatus.ACTIVE,))

    def reactivate(self) -> None:
        """Reverse a suspension. Distinct from ``activate()`` because the
        legal preceding state differs (suspended, not provisioning) and
        the two represent different business events for audit purposes."""
        self._transition_to(TenantStatus.ACTIVE, allowed_from=(TenantStatus.SUSPENDED,))

    def offboard(self) -> None:
        """Tenant relationship ended (Data Architecture v2.0 SS4.6).

        This is "tenant soft delete" as scoped for Sprint 4.1: the
        lifecycle transition only. The tenant row itself is never
        deleted, and the scheduled, audited physical purge after the
        legal retention window is explicitly out of scope here.
        """
        self._transition_to(
            TenantStatus.OFFBOARDED,
            allowed_from=(TenantStatus.ACTIVE, TenantStatus.SUSPENDED),
        )

    def _transition_to(
        self, new_status: TenantStatus, *, allowed_from: tuple[TenantStatus, ...]
    ) -> None:
        if self.status not in allowed_from:
            raise InvalidTenantStatusTransitionError(self.id, self.status.value, new_status.value)
        self.status = new_status
