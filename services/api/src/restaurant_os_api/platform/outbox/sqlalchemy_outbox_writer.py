"""SQLAlchemy implementation of the ``OutboxWriter`` port.

Technical Architecture v2.0 Group B: constructed with the *same*
``AsyncSession`` the calling use case's Unit of Work already opened
(the same repository-factory pattern used throughout the identity
module), so this insert commits or rolls back atomically with the
business write around it — never a separate transaction.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.platform.events import DomainEvent
from restaurant_os_api.platform.outbox.models import OutboxEventModel


class SQLAlchemyOutboxWriter:
    """Implements ``OutboxWriter``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def publish(self, tenant_id: str, event: DomainEvent) -> None:
        model = OutboxEventModel(
            id=generate_ulid(),
            tenant_id=tenant_id,
            aggregate_type=event.aggregate_type,
            aggregate_id=event.aggregate_id,
            event_type=event.event_type,
            payload=event.to_payload(),
        )
        self._session.add(model)
        await self._session.flush()
