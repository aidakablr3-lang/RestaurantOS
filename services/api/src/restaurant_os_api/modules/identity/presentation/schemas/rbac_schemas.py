"""Pydantic request/response schemas for RBAC endpoints.

Technical Architecture v2.0 SS5.6: parse -> call one use case -> shape
the response, no business logic here — matching every other schemas
module in this package exactly.
"""

from __future__ import annotations

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateRoleRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    description: str | None = Field(default=None, max_length=1000)
    default_scope: str = Field(default="branch", pattern="^(tenant|branch)$")
    permission_codes: list[str] = Field(default_factory=list)


class ReplaceRolePermissionsRequestSchema(CamelModel):
    permission_codes: list[str] = Field(default_factory=list)


class AssignUserRoleRequestSchema(CamelModel):
    user_id: str = Field(..., min_length=26, max_length=26)
    role_id: str = Field(..., min_length=26, max_length=26)
    branch_id: str | None = Field(default=None, min_length=26, max_length=26)


class RoleResponseSchema(CamelModel):
    id: str
    tenant_id: str | None
    name: str
    description: str | None
    default_scope: str
    is_system: bool
    is_active: bool


class UserRoleResponseSchema(CamelModel):
    id: str
    tenant_id: str
    user_id: str
    role_id: str
    branch_id: str | None
    granted_at: str
    granted_by_user_id: str | None


class PermissionResponseSchema(CamelModel):
    code: str
    module: str
    description: str
    is_active: bool


class ResolvedPermissionsResponseSchema(CamelModel):
    tenant_wide: list[str]
    by_branch: dict[str, list[str]]
