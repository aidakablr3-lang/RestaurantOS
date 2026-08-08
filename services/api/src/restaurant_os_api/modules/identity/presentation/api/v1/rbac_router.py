"""RBAC endpoints.

Technical Architecture v2.0 SS5.5: URI-based versioning, one handler
does one thing: parse, call one use case, shape the response — the
same discipline ``admin_tenant_router.py`` already established.

**Path prefix note:** the earlier planning document
(``RestaurantOS_Restaurant_Platform_Architecture.md`` section 7)
sketched these under ``/api/v1/admin/roles`` — reconsidered during
implementation and moved to ``/api/v1/rbac/...``. The existing
``/api/v1/admin/tenants`` prefix is gated by ``require_platform_admin``
(Sprint 4.1 Decision C); reusing "admin" for routes gated by an
entirely different mechanism (``require_permission("roles.assign")``,
which has nothing to do with platform administration) would invite
exactly the confusion this whole effort exists to prevent. A small,
disclosed deviation from the sketch, not a silent one.

Every mutating route below is gated by ``roles.assign`` — the approved
catalogue's single permission covering both role authoring and role
assignment (RBAC_Foundation_Architecture.md section 6.2's note,
restated in ``create_role.py``). ``GET /me/permissions`` needs only
authentication: a user is always allowed to see their own resolved
grants, which is exactly what lets ``apps/admin-web`` decide what UI to
render (RBAC_Foundation_Architecture.md section 8.2 — nothing is ever
trusted from the JWT for this decision).

**Two different flavors of the ``roles.assign`` gate, corrected in the
RBAC Sprint 5 Step 2 follow-up pass (AI_HANDOFF.md section 21,
"Finding 2"):** role *catalogue* management (``POST``/``GET
/rbac/roles``, ``GET /rbac/roles/{id}``, ``PUT
/rbac/roles/{id}/permissions``, ``GET /rbac/permissions``) stays on
``RequireRolesAssignDep`` — a plain, **tenant-wide** ``roles.assign``
check — because a ``Role`` row has no ``branch_id`` at all (SS4.1) and
``RoleGrantPolicy`` applies no scope ceiling to authoring/editing a
role definition. ``POST``/``DELETE /rbac/user-roles*`` (the two routes
that actually create or remove a scoped ``UserRole`` grant) use
``RequireRolesAssignAtAnyScopeDep`` instead — a caller holding
``roles.assign`` at a *branch* is coarsely let past this gate, with the
real, fine-grained scope/delegation decision made exactly once, inside
``RoleGrantPolicy`` (see ``require_permission_at_any_scope``'s own
docstring in ``dependencies.py`` for the full reasoning).
"""

from __future__ import annotations

from typing import Annotated

from fastapi import APIRouter, Depends, Path, Query, status

from restaurant_os_api.core.response import ApiResponse, PaginationMeta
from restaurant_os_api.modules.identity.application.dto import (
    AssignUserRoleRequestDTO,
    AuthenticatedPrincipalDTO,
    CreateRoleRequestDTO,
    ReplaceRolePermissionsRequestDTO,
    RevokeUserRoleRequestDTO,
    RoleDTO,
)
from restaurant_os_api.modules.identity.presentation.dependencies import (
    AssignUserRoleUseCaseDep,
    AuthenticatedPrincipalDep,
    CreateRoleUseCaseDep,
    GetRoleUseCaseDep,
    ListPermissionsUseCaseDep,
    ListRolesUseCaseDep,
    ReplaceRolePermissionsUseCaseDep,
    ResolveUserPermissionsUseCaseDep,
    RevokeUserRoleUseCaseDep,
    require_permission,
    require_permission_at_any_scope,
)
from restaurant_os_api.modules.identity.presentation.schemas.rbac_schemas import (
    AssignUserRoleRequestSchema,
    CreateRoleRequestSchema,
    PermissionResponseSchema,
    ReplaceRolePermissionsRequestSchema,
    ResolvedPermissionsResponseSchema,
    RoleResponseSchema,
    UserRoleResponseSchema,
)

router = APIRouter(tags=["rbac"])

RoleIdPath = Annotated[str, Path(min_length=26, max_length=26)]
UserRoleIdPath = Annotated[str, Path(min_length=26, max_length=26)]

# `require_permission("roles.assign")` returns an ordinary
# AuthenticatedPrincipalDTO on success (Commit 4) -- reused here as the
# dependency for every role-catalogue route below, exactly like
# `PlatformAdminDep` is reused across `admin_tenant_router.py`.
RequireRolesAssignDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission("roles.assign"))
]

# Branch-aware variant (Commit 9, "Finding 2" fix) -- used only by the
# two routes that create/remove a scoped UserRole grant. See
# `require_permission_at_any_scope`'s own docstring for why this exists
# and why it is deliberately coarse-grained.
RequireRolesAssignAtAnyScopeDep = Annotated[
    AuthenticatedPrincipalDTO, Depends(require_permission_at_any_scope("roles.assign"))
]


def _role_to_schema(dto: RoleDTO) -> RoleResponseSchema:
    return RoleResponseSchema(
        id=dto.id,
        tenant_id=dto.tenant_id,
        name=dto.name,
        description=dto.description,
        default_scope=dto.default_scope,
        is_system=dto.is_system,
        is_active=dto.is_active,
    )


@router.get("/api/v1/me/permissions", response_model=ApiResponse[ResolvedPermissionsResponseSchema])
async def get_my_permissions(
    principal: AuthenticatedPrincipalDep,
    resolve_permissions: ResolveUserPermissionsUseCaseDep,
) -> ApiResponse[ResolvedPermissionsResponseSchema]:
    resolved = await resolve_permissions.execute(principal.tenant_id, principal.user_id)
    return ApiResponse(
        data=ResolvedPermissionsResponseSchema(
            tenant_wide=sorted(resolved.tenant_wide),
            by_branch={branch_id: sorted(codes) for branch_id, codes in resolved.by_branch.items()},
        )
    )


@router.get("/api/v1/rbac/permissions", response_model=ApiResponse[list[PermissionResponseSchema]])
async def list_permissions(
    _principal: RequireRolesAssignDep,
    use_case: ListPermissionsUseCaseDep,
) -> ApiResponse[list[PermissionResponseSchema]]:
    permissions = await use_case.execute()
    return ApiResponse(
        data=[
            PermissionResponseSchema(
                code=p.code, module=p.module, description=p.description, is_active=p.is_active
            )
            for p in permissions
        ]
    )


@router.post(
    "/api/v1/rbac/roles",
    response_model=ApiResponse[RoleResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def create_role(
    body: CreateRoleRequestSchema,
    principal: RequireRolesAssignDep,
    use_case: CreateRoleUseCaseDep,
) -> ApiResponse[RoleResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        CreateRoleRequestDTO(
            creator_user_id=principal.user_id,
            name=body.name,
            description=body.description,
            default_scope=body.default_scope,
            permission_codes=frozenset(body.permission_codes),
        ),
    )
    return ApiResponse(data=_role_to_schema(result))


@router.get("/api/v1/rbac/roles", response_model=ApiResponse[list[RoleResponseSchema]])
async def list_roles(
    principal: RequireRolesAssignDep,
    use_case: ListRolesUseCaseDep,
    offset: Annotated[int, Query(ge=0)] = 0,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
) -> ApiResponse[list[RoleResponseSchema]]:
    result = await use_case.execute(principal.tenant_id, offset=offset, limit=limit)
    return ApiResponse(
        data=[_role_to_schema(r) for r in result.roles],
        meta=PaginationMeta(total=result.total, offset=result.offset, limit=result.limit),
    )


@router.get("/api/v1/rbac/roles/{role_id}", response_model=ApiResponse[RoleResponseSchema])
async def get_role(
    role_id: RoleIdPath,
    principal: RequireRolesAssignDep,
    use_case: GetRoleUseCaseDep,
) -> ApiResponse[RoleResponseSchema]:
    result = await use_case.execute(principal.tenant_id, role_id)
    return ApiResponse(data=_role_to_schema(result))


@router.put("/api/v1/rbac/roles/{role_id}/permissions", response_model=ApiResponse[None])
async def replace_role_permissions(
    role_id: RoleIdPath,
    body: ReplaceRolePermissionsRequestSchema,
    principal: RequireRolesAssignDep,
    use_case: ReplaceRolePermissionsUseCaseDep,
) -> ApiResponse[None]:
    await use_case.execute(
        principal.tenant_id,
        ReplaceRolePermissionsRequestDTO(
            actor_user_id=principal.user_id,
            role_id=role_id,
            permission_codes=frozenset(body.permission_codes),
        ),
    )
    return ApiResponse(data=None)


@router.post(
    "/api/v1/rbac/user-roles",
    response_model=ApiResponse[UserRoleResponseSchema],
    status_code=status.HTTP_201_CREATED,
)
async def assign_user_role(
    body: AssignUserRoleRequestSchema,
    principal: RequireRolesAssignAtAnyScopeDep,
    use_case: AssignUserRoleUseCaseDep,
) -> ApiResponse[UserRoleResponseSchema]:
    result = await use_case.execute(
        principal.tenant_id,
        AssignUserRoleRequestDTO(
            granter_user_id=principal.user_id,
            target_user_id=body.user_id,
            role_id=body.role_id,
            branch_id=body.branch_id,
        ),
    )
    return ApiResponse(
        data=UserRoleResponseSchema(
            id=result.id,
            tenant_id=result.tenant_id,
            user_id=result.user_id,
            role_id=result.role_id,
            branch_id=result.branch_id,
            granted_at=result.granted_at,
            granted_by_user_id=result.granted_by_user_id,
        )
    )


@router.delete(
    "/api/v1/rbac/user-roles/{user_role_id}",
    response_model=ApiResponse[None],
    status_code=status.HTTP_200_OK,
)
async def revoke_user_role(
    user_role_id: UserRoleIdPath,
    principal: RequireRolesAssignAtAnyScopeDep,
    use_case: RevokeUserRoleUseCaseDep,
) -> ApiResponse[None]:
    await use_case.execute(
        principal.tenant_id,
        RevokeUserRoleRequestDTO(revoker_user_id=principal.user_id, user_role_id=user_role_id),
    )
    return ApiResponse(data=None)
