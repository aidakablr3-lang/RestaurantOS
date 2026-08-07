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
