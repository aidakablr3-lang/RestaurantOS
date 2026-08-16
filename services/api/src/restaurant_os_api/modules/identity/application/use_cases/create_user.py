"""CreateUserUseCase — the API counterpart to ``scripts/create_user.py``.

Closes the "no user-creation use case exists" gap: ``UserRepository``
had ``get_by_id``/``get_by_email`` but no ``create()`` until now (see
``UserRepository``'s own port docstring history). This use case creates
a bare account only — no role, no access — deliberately mirroring the
existing split between ``TenantProvisioningService.provision()``
(creates a tenant, no user) and ``AssignUserRoleUseCase`` (grants a
role, never creates a user): granting a role is where the real
privilege-escalation check (``RoleGrantPolicy``) already lives, and
creating an inert, access-less account is not itself a privilege an
attacker could escalate into, so this use case does not duplicate that
policy. The router gates this endpoint on ``roles.assign`` (at any
scope) precisely because a bare account is only useful to whoever can
follow up with a role grant — see ``users_router.py``'s own docstring.

Still does not close the *first user of a tenant* bootstrap case:
creating any user requires an authenticated caller who already holds
``roles.assign``, and a brand-new tenant has no user at all yet. That
one case still goes through ``scripts/create_user.py``, run by whoever
operates the platform, exactly as before.
"""

from __future__ import annotations

import secrets
from collections.abc import Callable
from datetime import UTC, datetime

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.dto import CreateUserRequestDTO, UserDTO
from restaurant_os_api.modules.identity.application.interfaces import PasswordHasher
from restaurant_os_api.modules.identity.application.use_cases._user_mapper import user_to_dto
from restaurant_os_api.modules.identity.domain.entities import User, UserStatus
from restaurant_os_api.modules.identity.domain.events import UserCreated
from restaurant_os_api.modules.identity.domain.exceptions import UserEmailConflictError
from restaurant_os_api.modules.identity.domain.ports import UserRepository
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext


def _generate_password() -> str:
    # Same choice as scripts/create_user.py's own _generate_password:
    # ~96 bits of entropy, short enough to relay out-of-band once.
    return secrets.token_urlsafe(12)


class CreateUserUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        password_hasher: PasswordHasher,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._user_repository_factory = user_repository_factory
        self._password_hasher = password_hasher
        self._outbox_writer_factory = outbox_writer_factory

    async def execute(self, tenant_id: str, request: CreateUserRequestDTO) -> UserDTO:
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            user_repo = self._user_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            if await user_repo.get_by_email(tenant_id, request.email) is not None:
                raise UserEmailConflictError(request.email)

            generated_password = request.password is None
            password = request.password or _generate_password()
            now = datetime.now(UTC)

            user = await user_repo.create(
                User(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    email=request.email,
                    phone=request.phone,
                    password_hash=self._password_hasher.hash(password),
                    pin_hash=None,
                    permission_version=1,
                    status=UserStatus.ACTIVE,
                    created_at=now,
                    is_platform_admin=False,
                )
            )

            await outbox.publish(
                tenant_id,
                UserCreated(
                    user_id=user.id,
                    tenant_id=tenant_id,
                    email=user.email,
                    created_by_user_id=request.creator_user_id,
                    occurred_at=now,
                ),
            )

        return user_to_dto(user, generated_password=password if generated_password else None)
