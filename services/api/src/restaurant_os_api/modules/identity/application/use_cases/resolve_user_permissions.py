"""ResolveUserPermissionsUseCase — the one place permission resolution
happens (RBAC Foundation Architecture SS8).

User -> UserRole (active grants) -> Role (active only) -> RolePermission
-> Permission (active only), aggregated by scope. Every mutating and
permission-checking path in this module calls through here rather than
re-implementing the walk — there is exactly one resolution algorithm,
not one per call site.

Never trusted from the client, never cached across requests, never
embedded in a JWT (RBAC Foundation Architecture SS8.2) — this is a
fresh Postgres read every time, which is also why an RBAC change takes
effect on the very next request with no separate propagation mechanism
needed (SS9).
"""

from __future__ import annotations

from collections.abc import Callable

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.ports import (
    RolePermissionRepository,
    RoleRepository,
    UserRoleRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


class ResolveUserPermissionsUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        user_role_repository_factory: Callable[[AsyncSession], UserRoleRepository],
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
        role_permission_repository_factory: Callable[[AsyncSession], RolePermissionRepository],
    ) -> None:
        self._session_factory = session_factory
        self._user_role_repository_factory = user_role_repository_factory
        self._role_repository_factory = role_repository_factory
        self._role_permission_repository_factory = role_permission_repository_factory

    async def execute(self, tenant_id: str, user_id: str) -> ResolvedPermissions:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            user_role_repo = self._user_role_repository_factory(uow.session)
            role_repo = self._role_repository_factory(uow.session)
            role_permission_repo = self._role_permission_repository_factory(uow.session)

            grants = await user_role_repo.list_active_for_user(tenant_id, user_id)

            tenant_wide: set[str] = set()
            by_branch: dict[str, set[str]] = {}

            for grant in grants:
                role = await role_repo.get_by_id(tenant_id, grant.role_id)
                # A retired role, or one whose row has otherwise gone
                # missing (should not happen given ON DELETE RESTRICT,
                # defense-in-depth regardless), contributes nothing —
                # never raises, since one bad grant must not break
                # resolution of every other grant a user holds.
                if role is None or not role.is_active:
                    continue

                codes = await role_permission_repo.list_permission_codes_for_role(role.id)
                if grant.is_tenant_wide:
                    tenant_wide.update(codes)
                elif grant.branch_id is not None:
                    by_branch.setdefault(grant.branch_id, set()).update(codes)

        return ResolvedPermissions(
            tenant_wide=frozenset(tenant_wide),
            by_branch={branch_id: frozenset(codes) for branch_id, codes in by_branch.items()},
        )
