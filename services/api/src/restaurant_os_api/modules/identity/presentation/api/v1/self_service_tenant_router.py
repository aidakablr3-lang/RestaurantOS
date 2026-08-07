"""Tenant self-service endpoints — any authenticated user, scoped to
their own tenant (resolved from the access token, never a path
parameter or request body — Data Architecture v2.0 SS4.1's rule that
tenant scope is never client-asserted)."""

from __future__ import annotations

from fastapi import APIRouter

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.identity.application.dto import UpdateSettingRequestDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    AuthenticatedPrincipalDep,
    GetSubscriptionStatusUseCaseDep,
    GetTenantQuotaUsageUseCaseDep,
    GetTenantSettingsUseCaseDep,
    GetTenantUseCaseDep,
    ListFeatureFlagsUseCaseDep,
    UpdateTenantSettingsUseCaseDep,
)
from restaurant_os_api.modules.identity.presentation.schemas.tenant_schemas import (
    FeatureFlagStatusResponseSchema,
    SubscriptionResponseSchema,
    SystemSettingResponseSchema,
    TenantQuotaUsageResponseSchema,
    TenantResponseSchema,
    UpdateSettingRequestSchema,
)

router = APIRouter(prefix="/api/v1/tenants/me", tags=["tenant-self-service"])


@router.get("", response_model=ApiResponse[TenantResponseSchema])
async def get_my_tenant(
    principal: AuthenticatedPrincipalDep, use_case: GetTenantUseCaseDep
) -> ApiResponse[TenantResponseSchema]:
    result = await use_case.execute(principal.tenant_id)
    return ApiResponse(
        data=TenantResponseSchema(
            id=result.id,
            legal_name=result.legal_name,
            display_name=result.display_name,
            tenant_tier=result.tenant_tier,
            status=result.status,
            default_currency_code=result.default_currency_code,
            metadata=result.metadata,
            created_at=result.created_at,
        )
    )


@router.get("/subscription", response_model=ApiResponse[SubscriptionResponseSchema])
async def get_my_subscription(
    principal: AuthenticatedPrincipalDep, use_case: GetSubscriptionStatusUseCaseDep
) -> ApiResponse[SubscriptionResponseSchema]:
    result = await use_case.execute(principal.tenant_id)
    return ApiResponse(
        data=SubscriptionResponseSchema(
            id=result.id,
            tenant_id=result.tenant_id,
            plan_code=result.plan_code,
            status=result.status,
            current_period_end=result.current_period_end,
            trial_end=result.trial_end,
            next_billing_date=result.next_billing_date,
            grace_period_until=result.grace_period_until,
            max_branches=result.max_branches,
            max_users=result.max_users,
            max_monthly_orders=result.max_monthly_orders,
            is_active=result.is_active,
            is_in_trial=result.is_in_trial,
        )
    )


@router.get("/quotas", response_model=ApiResponse[TenantQuotaUsageResponseSchema])
async def get_my_quota_usage(
    principal: AuthenticatedPrincipalDep, use_case: GetTenantQuotaUsageUseCaseDep
) -> ApiResponse[TenantQuotaUsageResponseSchema]:
    result = await use_case.execute(principal.tenant_id)
    return ApiResponse(
        data=TenantQuotaUsageResponseSchema(
            max_branches=result.max_branches,
            max_users=result.max_users,
            max_monthly_orders=result.max_monthly_orders,
            current_users=result.current_users,
            current_branches=result.current_branches,
            current_monthly_orders=result.current_monthly_orders,
        )
    )


@router.get("/settings", response_model=ApiResponse[list[SystemSettingResponseSchema]])
async def get_my_settings(
    principal: AuthenticatedPrincipalDep, use_case: GetTenantSettingsUseCaseDep
) -> ApiResponse[list[SystemSettingResponseSchema]]:
    result = await use_case.execute(principal.tenant_id)
    return ApiResponse(
        data=[
            SystemSettingResponseSchema(key=s.key, value=s.value, branch_id=s.branch_id)
            for s in result
        ]
    )


@router.put("/settings", response_model=ApiResponse[SystemSettingResponseSchema])
async def update_my_setting(
    body: UpdateSettingRequestSchema,
    principal: AuthenticatedPrincipalDep,
    use_case: UpdateTenantSettingsUseCaseDep,
) -> ApiResponse[SystemSettingResponseSchema]:
    result = await use_case.execute(
        UpdateSettingRequestDTO(tenant_id=principal.tenant_id, key=body.key, value=body.value)
    )
    return ApiResponse(
        data=SystemSettingResponseSchema(
            key=result.key, value=result.value, branch_id=result.branch_id
        )
    )


@router.get("/feature-flags", response_model=ApiResponse[list[FeatureFlagStatusResponseSchema]])
async def get_my_feature_flags(
    principal: AuthenticatedPrincipalDep, use_case: ListFeatureFlagsUseCaseDep
) -> ApiResponse[list[FeatureFlagStatusResponseSchema]]:
    result = await use_case.execute(principal.tenant_id)
    return ApiResponse(
        data=[FeatureFlagStatusResponseSchema(key=f.key, enabled=f.enabled) for f in result]
    )
