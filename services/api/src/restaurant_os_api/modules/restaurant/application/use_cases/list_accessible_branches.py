"""ListAccessibleBranchesUseCase -- the reusable "which branches can
this caller see" resolution Step 4 Decision Lock's Decision 2 asks for.

Deliberately thin: every actual authorization primitive it needs
already exists (RBAC Foundation Architecture SS8) --
``ResolveUserPermissionsUseCase`` (identity module, consumed here
exactly as Restaurant Platform Architecture SS12.2 says Restaurant
Platform must: waiting for and consuming RBAC, never building a second
mechanism) and ``ResolvedPermissions.branch_ids_with()`` (already
returns the exact union Decision 2's rule 3 asks for). This use case
composes those with ``BranchRepository.list_for_tenant``/``list_by_ids``
(this module's own) and adds nothing else:

1. Tenant-wide grant (``permission_code in resolved.tenant_wide``) ->
   every branch belonging to the tenant, across every restaurant.
2. Branch-scoped grant(s) -> only the specific, unioned set of branch
   ids the caller actually holds ``permission_code`` at
   (``resolved.branch_ids_with(permission_code)``).
3. Neither -> an empty result. Tenant membership alone is never
   sufficient (Decision 2's rule 5) -- there is no code path here that
   can return a branch without a matching permission grant for it.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import Branch
from restaurant_os_api.modules.restaurant.domain.ports import BranchRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ListAccessibleBranchesUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        resolve_user_permissions: ResolveUserPermissionsUseCase,
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._resolve_user_permissions = resolve_user_permissions

    async def execute(
        self,
        tenant_id: str,
        user_id: str,
        permission_code: str,
        *,
        offset: int,
        limit: int,
    ) -> tuple[list[Branch], int]:
        resolved = await self._resolve_user_permissions.execute(tenant_id, user_id)

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)

            if permission_code in resolved.tenant_wide:
                return await branch_repo.list_for_tenant(tenant_id, offset=offset, limit=limit)

            branch_ids = resolved.branch_ids_with(permission_code)
            if not branch_ids:
                return [], 0

            branches = await branch_repo.list_by_ids(tenant_id, branch_ids)

        # list_by_ids has no offset/limit of its own (the caller's
        # granted-branch set is bounded by how many branches they hold
        # a grant at, never a large scan) -- paginate the already-small
        # in-memory result instead of adding a second, rarely-exercised
        # pagination path to the repository port.
        branches.sort(key=lambda b: b.created_at, reverse=True)
        total = len(branches)
        return branches[offset : offset + limit], total
