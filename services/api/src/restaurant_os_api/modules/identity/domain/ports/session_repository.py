"""Repository port for Session (the refresh-token registry)."""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import Session


class SessionRepository(Protocol):
    async def create(self, session: Session) -> Session: ...

    async def get_by_refresh_token_hash(self, refresh_token_hash: str) -> Session | None: ...

    async def revoke(self, session_id: str) -> None: ...

    async def revoke_all_for_user(self, user_id: str) -> None:
        """Revoke every active session for a user.

        Backs "logout all devices" / immediate deactivation (Technical
        Architecture v2.0 Group C) — declared on this port now for the
        same forward-compatibility reason as
        ``UserRepository.bump_permission_version``.
        """
        ...
