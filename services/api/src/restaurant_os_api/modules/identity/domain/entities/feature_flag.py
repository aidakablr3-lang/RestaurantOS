"""FeatureFlag entity.

Data Architecture v2.0 SS3.14: "A named, tenant-scopable toggle for
**progressive feature rollout**." The rollout percentage and date-window
fields added in Sprint 4.1 are a direct fulfillment of that already-
stated purpose, not a new capability being invented.

``tenant_id is None`` means a platform-wide flag, visible to every
tenant (enforced at the database layer by an RLS policy that allows
``tenant_id IS NULL`` rows through regardless of the current tenant
context — see the Sprint 4.1 migration).
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from datetime import UTC, datetime


def rollout_bucket(tenant_id: str) -> int:
    """A stable, deterministic 0-99 bucket for a tenant.

    Using a hash of the tenant_id (rather than randomness) means a given
    tenant's flag evaluation is stable across requests and processes —
    essential for a coherent user experience under a percentage rollout
    (a tenant should not flicker between the old and new behavior from
    one request to the next).
    """
    digest = hashlib.sha256(tenant_id.encode("utf-8")).hexdigest()
    return int(digest, 16) % 100


@dataclass(slots=True)
class FeatureFlag:
    id: str
    key: str
    enabled: bool
    created_at: datetime
    tenant_id: str | None = None
    rollout_percentage: int = 100
    start_date: datetime | None = None
    end_date: datetime | None = None

    def is_effective_for(self, tenant_id: str, *, now: datetime | None = None) -> bool:
        """Resolve whether this flag is actually "on" for a given tenant
        right now, folding in the enabled switch, the date window, and
        the percentage rollout in one place — callers never re-implement
        this logic."""
        if not self.enabled:
            return False
        now = now or datetime.now(UTC)
        if self.start_date is not None and now < self.start_date:
            return False
        if self.end_date is not None and now > self.end_date:
            return False
        if self.rollout_percentage >= 100:
            return True
        if self.rollout_percentage <= 0:
            return False
        return rollout_bucket(tenant_id) < self.rollout_percentage
