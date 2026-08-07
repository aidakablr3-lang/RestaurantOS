"""The Transactional Outbox port.

Technical Architecture v2.0 Group B: a use case writes its domain
events through this port *inside the same database transaction* as its
business write — the concrete implementation (added in the migration
that creates ``outbox_events``, Sprint 4.1 Commit 3) inserts a row using
the same ``AsyncSession`` the Unit of Work already opened, so the event
and the business change commit or roll back together atomically.

Scope note (Sprint 4.1): this port and its implementation cover durable,
atomic *recording* of events only. The relay from ``outbox_events`` to
Redis Streams (Technical Architecture v2.0 Group D) is not built in this
sprint — no Redis client exists in this codebase yet, and standing one
up is infrastructure work disproportionate to "Tenant Platform, nothing
else." Events are correctly and durably recorded, ready to be relayed
once that infrastructure exists.
"""

from __future__ import annotations

from typing import Protocol

from restaurant_os_api.platform.events import DomainEvent


class OutboxWriter(Protocol):
    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        """Record ``event`` in the outbox, scoped to ``tenant_id``.

        Must be called with a repository-style, session-bound instance
        (see the ``*_factory`` pattern already used for repositories in
        ``LoginUserUseCase`` etc.) so the insert shares the calling use
        case's transaction.
        """
        ...
