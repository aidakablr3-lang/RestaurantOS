"""Pydantic request/response schemas for Tenant Administration endpoints.

Technical Architecture v2.0 SS5.6: parse -> call one use case -> shape
the response, no business logic here.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class OnboardTenantRequestSchema(CamelModel):
    legal_name: str = Field(..., min_length=1, max_length=255)
    display_name: str = Field(..., min_length=1, max_length=255)
    default_currency_code: str = Field(..., min_length=3, max_length=3)
    owner_email: str = Field(..., min_length=3, max_length=320)
    owner_phone: str | None = None


class UpdateTenantRequestSchema(CamelModel):
    display_name: str = Field(..., min_length=1, max_length=255)
    metadata: dict[str, Any] = Field(default_factory=dict)


class TenantResponseSchema(CamelModel):
    id: str
    legal_name: str
    display_name: str
    tenant_tier: str
    status: str
    default_currency_code: str
    metadata: dict[str, Any]
    created_at: datetime
    # Only present on the onboard response -- see TenantDTO's own
    # docstring. owner_activation_token is shown exactly once.
    owner_id: str | None = None
    owner_email: str | None = None
    owner_activation_token: str | None = None


class SubscriptionResponseSchema(CamelModel):
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


class TenantQuotaUsageResponseSchema(CamelModel):
    max_branches: int
    max_users: int
    max_monthly_orders: int
    current_users: int
    current_branches: int | None
    current_monthly_orders: int | None


class SystemSettingResponseSchema(CamelModel):
    key: str
    value: dict[str, Any]
    branch_id: str | None


class UpdateSettingRequestSchema(CamelModel):
    key: str = Field(..., min_length=1, max_length=255)
    value: dict[str, Any]


class FeatureFlagStatusResponseSchema(CamelModel):
    key: str
    enabled: bool
