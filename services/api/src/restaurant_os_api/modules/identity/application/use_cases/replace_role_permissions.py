"""ReplaceRolePermissionsUseCase.

Only the codes being *added* need the delegation ceiling check
(``RoleGrantPolicy.ensure_can_delegate``) — removing a permission from
a role never needs authorization beyond ``roles.assign`` itself
(checked by the ``require_permission("roles.assign")`` route
dependency, Commit 4), since taking access away is never an escalation.

**Known, disclosed limitation:** unlike ``AssignUserRoleUseCase``/
``RevokeUserRoleUseCase`` (which bump the one directly-affected user's
``permission_version``), this use case does not fan out a
``permission_version`` bump to every user currently holding this role.
Every permission resolution is a fresh, uncached Postgres read
(RBAC_Foundation_Architecture.md section 9), so this does not affect
*correctness* — the next request from any affected user already sees
the new permission set regardless. The bump exists elsewhere purely
for consistency and future cache-invalidation readiness; extending it
to a role-wide fan-out is real, tracked follow-up work, not silently
assumed done here.
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import ReplaceRolePermissionsRequestDTO
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import RoleNotFoundError
from restaurant_os_api.modules.identity.domain.ports import RolePermissionRepository, RoleRepository
from restaurant_os_api.modules.identity.domain.services import RoleGrantPolicy
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ReplaceRolePermissionsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
        role_permission_repository_factory: Callable[[AsyncSession], RolePermissionRepository],
    ) -> None:
        self._session_factory = session_factory
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case
        self._role_repository_factory = role_repository_factory
        self._role_permission_repository_factory = role_permission_repository_factory

    async def execute(self, tenant_id: str, request: ReplaceRolePermissionsRequestDTO) -> None:
        actor_permissions = await self._resolve_user_permissions_use_case.execute(
            tenant_id, request.actor_user_id
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            role_permission_repo = self._role_permission_repository_factory(uow.session)

            role = await role_repo.get_by_id(tenant_id, request.role_id)
            if role is None:
                raise RoleNotFoundError(request.role_id)

            current_codes = await role_permission_repo.list_permission_codes_for_role(role.id)
            added_codes = request.permission_codes - current_codes

            RoleGrantPolicy.ensure_can_delegate(
                actor_permission_codes=actor_permissions.all_codes,
                permission_codes_to_delegate=added_codes,
            )

            await role_permission_repo.replace_for_role(role.id, request.permission_codes)
