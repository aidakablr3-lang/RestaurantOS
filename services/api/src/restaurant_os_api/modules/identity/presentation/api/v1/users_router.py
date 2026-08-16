"""User endpoints — the real API counterpart to ``scripts/create_user.py``.

Closes the "no user-creation API/UI exists" gap: until now, the only
way to create a user account (the tenant's first Owner, or any staff
hire after) was a manually-run operator script (``create_user.py``),
because ``UserRepository`` had no ``create()`` method at all.

Gated on ``require_permission_at_any_scope("roles.assign")`` — the same
gate ``POST /api/v1/rbac/user-roles`` already uses (``rbac_router.py``).
Reusing this existing permission, rather than adding a new one, is
deliberate: a bare account with no role has no access at all, so the
capability that actually matters is "can this caller grant a role to
someone" — and that is exactly what ``roles.assign`` already means.
Today, only the default "Tenant Owner" role holds ``roles.assign``
(tenant-wide), so in practice only a tenant's Owner (or anyone they've
explicitly delegated ``roles.assign`` to) can create staff accounts --
consistent with, not a change to, the existing RBAC default catalogue.

Still not full self-service: creating a tenant's *first* user requires
an already-authenticated caller holding ``roles.assign``, and a
brand-new tenant has none yet. That bootstrap case still goes through
``scripts/create_user.py``.
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Query, status

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.identity.application.dto import (
    AuthenticatedPrincipalDTO,
    CreateUserRequestDTO,
)
from restaurant_os_api.modules.identity.application.dto.user_dto import UserDTO
from restaurant_os_api.modules.identity.presentation.dependencies import (
    CreateUserUseCaseDep,
    ListUsersUseCaseDep,
    require_permission_at_any_scope,
)
from restaurant_os_api.modules.identity.presentation.schemas.user_schemas import (
    CreateUserRequestSchema,
    UserResponseSchema,
)

router = APIRouter(tags=["users"])

RequireRolesAssignAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("roles.assign"))
]


def _user_to_schema(dto: UserDTO) -> UserResponseSchema:
    return UserResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        email=dto.email,
        phone=dto.phone,
        status=dto.status,
        created_at=dto.created_at,
        generated_password=dto.generated_password,
    )


@router.post(
    "/api/v1/users",
    response_model=ApiResponse[UserResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_user(
    body: CreateUserRequestSchema,
    principal: RequireRolesAssignAtAnyScopeDep,
    use_case: CreateUserUseCaseDep,
) -> ApiResponse[UserResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        CreateUserRequestDTO(
            creator_user_id=principal.user_id,
            email=body.email,
            phone=body.phone,
            password=body.password,
        ),
    )
    return ApiResponse(data=_user_to_schema(result))


@router.get("/api/v1/users", response_model=ApiResponse[list[UserResponseSchema]])
async def list_users(
    principal: RequireRolesAssignAtAnyScopeDep,
    use_case: ListUsersUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[UserResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_user_to_schema(u) for u in result.users],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )
