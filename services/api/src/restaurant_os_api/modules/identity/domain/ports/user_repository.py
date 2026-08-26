"""Repository port for User."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import User


class UserRepository(Protocol):
    async def get_by_id(self, tenant_id: str, user_id: str) -> User | None: ...

    async def get_by_email(self, tenant_id: str, email: str) -> User | None:
        """Look up a user by email, scoped to a tenant.

        ``tenant_id`` is mandatory and must come from an already-resolved
        request context (Data Architecture v2.0 SS4.1) — never from
        client-controlled input alone, since the ``(tenant_id, email)``
        pair is what the database's partial unique index is actually
        keyed on (Data Architecture v2.0 SS5.3).
        """
        ...

    async def bump_permission_version(self, tenant_id: str, user_id: str) -> int:
        """Increment and return the user's permission_version.

        Technical Architecture v2.0 Group C: called whenever a user's
        access is revoked or changed, so already-issued access tokens
        fail their next permission-version check almost immediately.
        Not used by the login/refresh/logout use cases themselves, but
        declared on this port now so the deactivation use case (a
        follow-up PR) has a stable contract to implement against.
        """
        ...

    async def count_active_for_tenant(self, tenant_id: str) -> int:
        """Count active (not deactivated, not soft-deleted) users in a
        tenant. Sprint 4.1: backs quota-usage reporting — the one
        dimension of "current usage" this module can actually measure
        today, since Branch/Order don't exist yet (see
        ``GetTenantQuotaUsageUseCase``)."""
        ...

    async def create(self, user: User) -> User:
        """Insert a new user. Caller is responsible for checking
        ``get_by_email`` first — this method does not itself guard
        against a duplicate email, matching every other ``create()`` on
        this module's repositories (``RoleRepository.create()``,
        ``TenantRepository.create()``)."""
        ...

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[User], int]:
        """Page through a tenant's users, newest first, excluding
        soft-deleted rows — same shape as ``RoleRepository.list_for_tenant``."""
        ...

    async def activate(self, tenant_id: str, user_id: str, *, password_hash: str) -> None:
        """Set ``password_hash`` and flip ``status`` ``INVITED -> ACTIVE``
        in one statement. Sole caller: ``ActivateOwnerUseCase`` (Phase 1
        design doc SSA.4) — a narrow, purpose-specific update, matching
        this port's existing ``bump_permission_version`` shape rather
        than a generic ``update(user)``."""
        ...
