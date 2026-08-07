from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class SubscriptionDTO:
    id: str
    tenant_id: str
    plan_code: str
    status: str
    current_period_end: datetime
    trial_end: datetime | None
    next_billing_date: datetime | None
    grace_period_until: datetime | None
    max_branches: int
    max_users: int
    max_monthly_orders: int
    is_active: bool
    is_in_trial: bool


@dataclass(frozen=True, slots=True)
class TenantQuotaUsageDTO:
    max_branches: int
    max_users: int
    max_monthly_orders: int
    current_users: int
    # None = not yet measurable this sprint — the Branch/Order modules
    # this dimension depends on do not exist yet (Sprint 4.1 scope
    # boundary). Reported as an honest "not available," never a
    # fabricated 0.
    current_branches: int | None
    current_monthly_orders: int | None
