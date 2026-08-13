"""Reusable authorization for a body-supplied ``branch_id`` -- Step 4
Decision Lock, Decision 3: the same class of gap RBAC Sprint 5 Step 2's
own "Finding 2" found (a branch identifier that arrives somewhere other
than the URL path cannot be gated by ``require_branch_permission``,
which only reads a path parameter). Generalized here instead of
repeating a menu-specific version at every future call site (branch
price, availability, and anything else that ever needs this shape).

Never trusts the body's ``branch_id`` as an authorization claim -- it
only identifies *which resource* the request targets, exactly like
``require_branch_permission``'s own docstring already establishes for
the path-parameter case. The decision itself is always made from the
caller's own resolved grants (RBAC's ``ResolvedPermissions``), checked
against the branch a real, tenant-scoped repository lookup actually
found -- never against the raw client-supplied string.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.restaurant.domain.entities import Branch
from restaurant_os_api.modules.restaurant.domain.exceptions import BranchNotFoundError
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository


async def resolve_and_authorize_branch(
    *,
    branch_repository: BranchRepository,
    tenant_id: str,
    branch_id: str,
    resolved_permissions: ResolvedPermissions,
    permission_code: str,
) -> Branch:
    """Loads ``branch_id`` scoped to ``tenant_id`` (RLS plus the
    explicit filter reject a cross-tenant id as simply not found --
    "belt and suspenders", Data Architecture v2.0 SS4.1, never a
    distinguishable "found but wrong tenant" response that would leak
    cross-tenant existence), then checks the caller's own resolved
    permissions against *that* branch specifically. Raises
    ``BranchNotFoundError`` (404) for a missing or cross-tenant id, and
    ``PermissionDeniedError`` (403, identity's own existing exception --
    reused, not duplicated, per the "do not invent a second
    authorization mechanism" rule) for a real branch the caller simply
    isn't authorized at."""
    branch = await branch_repository.get_by_id(tenant_id, branch_id)
    if branch is None:
        raise BranchNotFoundError(branch_id)

    if not resolved_permissions.has(permission_code, branch_id=branch.id):
        raise PermissionDeniedError(permission_code, branch_id=branch.id)

    return branch
