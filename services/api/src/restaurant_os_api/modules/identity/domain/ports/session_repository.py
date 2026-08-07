"""Repository port for Session (the refresh-token registry)."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Session


class SessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def get_by_refresh_token_hash(
        self, tenant_id: str, refresh_token_hash: str
    ) -> Session | None:
        """Look up a session by its refresh token's hash, scoped to a tenant.

        ``tenant_id`` here is supplied by the caller (the refresh/logout
        request itself) rather than resolved from an already-authenticated
        context, since discovering the tenant *is* what this lookup is
        for. This is safe: an incorrect or malicious ``tenant_id`` simply
        yields no match (the row's actual tenant won't agree), because
        the real security boundary is the unforgeable, high-entropy token
        hash, not the tenant identifier — ``tenant_id`` here is routing
        information, not an authorization decision. See
        ``RefreshAccessTokenUseCase`` for the full reasoning; this
        avoids ever needing to query a Row-Level-Security-protected table
        before a tenant context can be established.
        """
        ...

    async def revoke(self, session_id: str) -> None: ...

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke every active session for a user.

        Backs "logout all devices" / immediate deactivation (Technical
        Architecture v2.0 Group C) — declared on this port now for the
        same forward-compatibility reason as
        ``UserRepository.bump_permission_version``.
        """
        ...
