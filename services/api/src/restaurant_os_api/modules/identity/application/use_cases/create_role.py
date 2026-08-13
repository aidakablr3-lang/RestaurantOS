"""CreateRoleUseCase.

RBAC Foundation Architecture SS16 ("role management" endpoint). The
Blueprint's own "Roles & Permissions" screen ("Create custom role,
assign permissions") is what this backs. ``roles.assign`` is
interpreted here as covering both "manage the role catalogue" and
"assign roles to users" — the approved permission catalogue
(RBAC_Foundation_Architecture.md section 6.2) has exactly 11 "needed
now" codes and no separate `roles.manage`; a deliberate, disclosed
interpretation, not a silent addition to that approved list.

The delegation ceiling (``RoleGrantPolicy.ensure_can_delegate``,
Commit 5) applies here too: a caller must not be able to *define* a new
role carrying permissions they don't themselves hold, any more than
they could hand out an existing one.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import CreateRoleRequestDTO, RoleDTO
from restaurant_os_api.modules.identity.application.use_cases._role_mapper import role_to_dto
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.entities import Role, RoleScope
from restaurant_os_api.modules.identity.domain.events import RoleCreated
from restaurant_os_api.modules.identity.domain.exceptions import RoleNameConflictError
from restaurant_os_api.modules.identity.domain.ports import RolePermissionRepository, RoleRepository
from restaurant_os_api.modules.identity.domain.services import RoleGrantPolicy
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class CreateRoleUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
        role_permission_repository_factory: Callable[[AsyncSession], RolePermissionRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case
        self._role_repository_factory = role_repository_factory
        self._role_permission_repository_factory = role_permission_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateRoleRequestDTO) -> RoleDTO:
        creator_permissions = await self._resolve_user_permissions_use_case.execute(
            tenant_id, request.creator_user_id
        )
        RoleGrantPolicy.ensure_can_delegate(
            actor_permission_codes=creator_permissions.all_codes,
            permission_codes_to_delegate=request.permission_codes,
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            role_repo = self._role_repository_factory(uow.session)
            role_permission_repo = self._role_permission_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            if await role_repo.get_by_name(tenant_id, request.name) is not None:
                raise RoleNameConflictError(request.name)

            now = datetime.now(UTC)
            role = await role_repo.create(
                Role(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    name=request.name,
                    description=request.description,
                    default_scope=RoleScope(request.default_scope),
                    is_system=False,
                    is_active=True,
                    created_at=now,
                )
            )
            await role_permission_repo.replace_for_role(role.id, request.permission_codes)

            await outbox.publish(
                tenant_id,
                RoleCreated(role_id=role.id, tenant_id=tenant_id, name=role.name, occurred_at=now),
            )

        return role_to_dto(role)
