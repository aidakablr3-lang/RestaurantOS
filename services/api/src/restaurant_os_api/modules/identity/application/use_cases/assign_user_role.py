"""AssignUserRoleUseCase — the one place a UserRole grant is created.

RBAC Foundation Architecture SS16.1/SS18 (Commit 5 — privilege
escalation protection): every grant is checked against the granter's
*own* resolved permissions before it is persisted. This is what makes
"a Branch Manager cannot grant themselves (or anyone else) a
tenant-wide role" and "a caller cannot delegate a permission they
don't hold" actual, enforced behavior rather than documented intent —
the same ``RoleGrantPolicy`` (Commit 1) is exercised here with real,
freshly-resolved data, not a synthetic example.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import (
    AssignUserRoleRequestDTO,
    UserRoleDTO,
)
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import UserRole
from restaurant_os_api.modules.identity.domain.events import UserRoleAssigned
from restaurant_os_api.modules.identity.domain.exceptions import (
    DuplicateRoleAssignmentError,
    RoleNotActiveError,
    RoleNotFoundError,
)
from restaurant_os_api.modules.identity.domain.ports import (
    RolePermissionRepository,
    RoleRepository,
    UserRepository,
    UserRoleRepository,
)
from restaurant_os_api.modules.identity.domain.services import RoleGrantPolicy
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class AssignUserRoleUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
        role_permission_repository_factory: Callable[[AsyncSession], RolePermissionRepository],
        user_role_repository_factory: Callable[[AsyncSession], UserRoleRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case
        self._role_repository_factory = role_repository_factory
        self._role_permission_repository_factory = role_permission_repository_factory
        self._user_role_repository_factory = user_role_repository_factory
        self._user_repository_factory = user_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: AssignUserRoleRequestDTO) -> UserRoleDTO:
        # Resolved in its own transaction, deliberately before the
        # granting transaction below — the granter's permissions must
        # reflect their state *at the moment of this request*, not be
        # re-derived inside the same transaction as the write (which
        # would work either way here, but keeping resolution as its own
        # call through the one shared use case, rather than
        # re-implementing the walk inline, is what makes this the only
        # place that logic exists — Commit 3's own stated reason).
        granter_permissions = await self._resolve_user_permissions_use_case.execute(
            tenant_id, request.granter_user_id
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            role_permission_repo = self._role_permission_repository_factory(uow.session)
            user_role_repo = self._user_role_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            role = await role_repo.get_by_id(tenant_id, request.role_id)
            if role is None:
                raise RoleNotFoundError(request.role_id)
            if not role.is_active:
                raise RoleNotActiveError(role.id)

            target_permission_codes = await role_permission_repo.list_permission_codes_for_role(
                role.id
            )

            RoleGrantPolicy.ensure_can_grant(
                granter_has_tenant_wide_assign=granter_permissions.has("roles.assign"),
                granter_branch_ids_with_assign=granter_permissions.branch_ids_with("roles.assign"),
                granter_permission_codes=granter_permissions.all_codes,
                target_role=role,
                target_role_permission_codes=target_permission_codes,
                target_branch_id=request.branch_id,
            )

            if await user_role_repo.exists(
                tenant_id, request.target_user_id, request.role_id, request.branch_id
            ):
                raise DuplicateRoleAssignmentError(
                    request.target_user_id, request.role_id, request.branch_id
                )

            now = datetime.now(UTC)
            user_role = await user_role_repo.create(
                UserRole(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    user_id=request.target_user_id,
                    role_id=request.role_id,
                    branch_id=request.branch_id,
                    granted_at=now,
                    granted_by_user_id=request.granter_user_id,
                )
            )

            # RBAC Foundation Architecture SS9: every RBAC-affecting
            # mutation bumps the *affected* user's permission_version —
            # not because propagation strictly requires it (nothing
            # caches permissions yet, so the next request already sees
            # the new grant), but for consistency with every other
            # "this changes what a user can do" event, and so a future
            # permission cache is already correctly invalidated the
            # moment it exists.
            await user_repo.bump_permission_version(tenant_id, request.target_user_id)

            await outbox.publish(
                tenant_id,
                UserRoleAssigned(
                    user_role_id=user_role.id,
                    user_id=user_role.user_id,
                    role_id=user_role.role_id,
                    branch_id=user_role.branch_id,
                    granted_by_user_id=user_role.granted_by_user_id,
                    occurred_at=now,
                ),
            )

        return UserRoleDTO(
            id=user_role.id,
            tenant_id=user_role.tenant_id,
            user_id=user_role.user_id,
            role_id=user_role.role_id,
            branch_id=user_role.branch_id,
            granted_at=user_role.granted_at.isoformat(),
            granted_by_user_id=user_role.granted_by_user_id,
        )
