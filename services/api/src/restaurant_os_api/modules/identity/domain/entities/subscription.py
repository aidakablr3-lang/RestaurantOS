"""Subscription entity.

Data Architecture v2.0 SS3.1 assigned this entity's *purpose* ("the
tenant's current commercial plan, billing cycle, and feature
entitlements") to the identity module but deliberately left its detailed
schema unspecified (only ~13 "representative" tables were fully
specified). Sprint 4.1 fills that in — trial/billing/grace-period
tracking and quota limits are a direct, compatible expansion of
"billing cycle" and "feature entitlements," not a new decision.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from enum import StrEnum


class SubscriptionStatus(StrEnum):
    TRIALING = "trialing"
    ACTIVE = "active"
    PAST_DUE = "past_due"
    CANCELED = "canceled"
    EXPIRED = "expired"


@dataclass(slots=True)
class Subscription:
    id: str
    tenant_id: str
    plan_code: str
    status: SubscriptionStatus
    current_period_end: datetime
    created_at: datetime
    trial_end: datetime | None = None
    next_billing_date: datetime | None = None
    grace_period_until: datetime | None = None
    max_branches: int = 1
    max_users: int = 5
    max_monthly_orders: int = 1_000

    def is_active(self, *, now: datetime | None = None) -> bool:
        """Whether this subscription currently entitles the tenant to use
        the platform — the check ``GetSubscriptionStatusUseCase`` and the
        tenant-validation middleware both rely on.

        A ``past_due`` subscription still counts as active until its
        grace period lapses (Sprint 4.1's grace-period addition) — this
        is what stops a single missed payment from an instant, jarring
        lockout.
        """
        now = now or datetime.now(UTC)
        if self.status in (SubscriptionStatus.ACTIVE, SubscriptionStatus.TRIALING):
            return True
        if self.status == SubscriptionStatus.PAST_DUE:
            return self.grace_period_until is not None and now < self.grace_period_until
        return False

    def is_in_trial(self, *, now: datetime | None = None) -> bool:
        now = now or datetime.now(UTC)
        return self.status == SubscriptionStatus.TRIALING and (
            self.trial_end is None or now < self.trial_end
        )
