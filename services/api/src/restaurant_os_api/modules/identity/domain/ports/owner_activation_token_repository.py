"""Repository port for OwnerActivationToken."""

from __future__ import annotations

from datetime import datetime
from typing import Protocol

from restaurant_os_api.modules.identity.domain.entities import OwnerActivationToken


class OwnerActivationTokenRepository(Protocol):
    async def create(self, token: OwnerActivationToken) -> OwnerActivationToken: ...

    async def get_by_token_hash(self, token_hash: str) -> OwnerActivationToken | None:
        """Look up a token by its hash alone, with no tenant scoping.

        Mirrors ``SessionRepository.get_by_refresh_token_hash``'s own
        reasoning one step further: that method still takes a caller-
        supplied ``tenant_id`` (the refresh request's own body carries
        one). An owner-activation request has no equivalent field — the
        raw token is the only thing the caller has, and discovering the
        tenant *is* what this lookup is for. The real security boundary
        is the unforgeable, high-entropy token hash itself, exactly as
        already reasoned for sessions.
        """
        ...

    async def mark_used(self, token_id: str, *, used_at: datetime) -> None: ...

    async def get_latest_for_user(self, tenant_id: str, user_id: str) -> OwnerActivationToken | None:
        """The most recently issued token for one user, tenant-scoped.

        Phase 1 design doc §A.4: backs ``GetOwnerActivationTokenStatusUseCase``,
        which ``ProvisionTenantStep.verify()`` calls to confirm the
        just-issued token is still usable. Unlike ``get_by_token_hash``
        (the activation request's own unauthenticated lookup, which has
        no tenant to scope by), this caller already knows both
        ``tenant_id`` and ``user_id`` — scoped the same
        belt-and-suspenders way every other repository method in this
        module is, even though the table itself carries no RLS."""
        ...
