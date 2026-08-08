"""RevokeUserRoleUseCase.

RBAC Foundation Architecture SS16.1's scope ceiling applies to
revocation too (Commit 5): a caller must not be able to revoke a grant
at a branch they have no ``roles.assign`` authority over, symmetric
with the grant-time check. No delegation ceiling applies here —
revoking hands out nothing new (``RoleGrantPolicy.ensure_can_revoke``).
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.identity.application.dto import RevokeUserRoleRequestDTO
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.events import UserRoleRevoked
from restaurant_os_api.modules.identity.domain.exceptions import UserRoleNotFoundError
from restaurant_os_api.modules.identity.domain.ports import UserRepository, UserRoleRepository
from restaurant_os_api.modules.identity.domain.services import RoleGrantPolicy
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


class RevokeUserRoleUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
        user_role_repository_factory: Callable[[AsyncSession], UserRoleRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case
        self._user_role_repository_factory = user_role_repository_factory
        self._user_repository_factory = user_repository_factory
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: RevokeUserRoleRequestDTO) -> None:
        revoker_permissions = await self._resolve_user_permissions_use_case.execute(
            tenant_id, request.revoker_user_id
        )

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            user_role_repo = self._user_role_repository_factory(uow.session)
            user_repo = self._user_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            existing = await user_role_repo.get_by_id(tenant_id, request.user_role_id)
            if existing is None:
                raise UserRoleNotFoundError(request.user_role_id)

            RoleGrantPolicy.ensure_can_revoke(
                revoker_has_tenant_wide_assign=revoker_permissions.has("roles.assign"),
                revoker_branch_ids_with_assign=revoker_permissions.branch_ids_with("roles.assign"),
                target_branch_id=existing.branch_id,
            )

            revoked = await user_role_repo.revoke(tenant_id, request.user_role_id)
            if revoked is None:
                raise UserRoleNotFoundError(request.user_role_id)

            await user_repo.bump_permission_version(tenant_id, revoked.user_id)

            await outbox.publish(
                tenant_id,
                UserRoleRevoked(
                    user_role_id=revoked.id,
                    user_id=revoked.user_id,
                    role_id=revoked.role_id,
                    branch_id=revoked.branch_id,
                    occurred_at=datetime.now(UTC),
                ),
            )
