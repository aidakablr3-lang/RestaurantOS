"""Auth endpoints: login, refresh, logout.

Technical Architecture v2.0 SS5.5: URI-based versioning (`/api/v1/...`).
Every handler here does exactly one thing: parse the request, call one
use case, shape the response — no business logic.
"""

from __future__ import annotations

from fastapi import APIRouter, status

from restaurant_os_api.core.response import ApiResponse
from restaurant_os_api.modules.identity.application.dto import (
    LoginRequestDTO,
    LogoutRequestDTO,
    RefreshRequestDTO,
)
from restaurant_os_api.modules.identity.presentation.dependencies import (
    LoginUseCaseDep,
    LogoutUseCaseDep,
    RefreshUseCaseDep,
)
from restaurant_os_api.modules.identity.presentation.schemas.auth_schemas import (
    LoginRequestSchema,
    LogoutRequestSchema,
    RefreshRequestSchema,
    TokenPairResponseSchema,
)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


@router.post(
    "/login",
    response_model=ApiResponse[TokenPairResponseSchema],
    status_code=status.HTTP_200_OK,
)
async def login(
    body: LoginRequestSchema, use_case: LoginUseCaseDep
) -> ApiResponse[TokenPairResponseSchema]:
    result = await use_case.execute(
        LoginRequestDTO(
            tenant_id=body.tenant_id,
            email=body.email,
            password=body.password,
            device_id=body.device_id,
        )
    )
    return ApiResponse(
        data=TokenPairResponseSchema(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
    )


@router.post(
    "/refresh",
    response_model=ApiResponse[TokenPairResponseSchema],
    status_code=status.HTTP_200_OK,
)
async def refresh(
    body: RefreshRequestSchema, use_case: RefreshUseCaseDep
) -> ApiResponse[TokenPairResponseSchema]:
    result = await use_case.execute(
        RefreshRequestDTO(
            tenant_id=body.tenant_id,
            refresh_token=body.refresh_token,
            device_id=body.device_id,
        )
    )
    return ApiResponse(
        data=TokenPairResponseSchema(
            access_token=result.access_token,
            refresh_token=result.refresh_token,
            token_type=result.token_type,
            expires_in=result.expires_in,
        )
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, response_model=None)
async def logout(body: LogoutRequestSchema, use_case: LogoutUseCaseDep) -> None:
    await use_case.execute(
        LogoutRequestDTO(tenant_id=body.tenant_id, refresh_token=body.refresh_token)
    )
