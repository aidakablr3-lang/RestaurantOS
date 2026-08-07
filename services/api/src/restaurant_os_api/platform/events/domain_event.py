"""The domain event contract.

Technical Architecture v2.0 SS9.3: domain events are defined by each
module's own Domain layer (see
``modules/identity/domain/events/tenant_events.py`` for the first
concrete examples) — this module defines only the *shape* every event
must satisfy to be publishable through the Transactional Outbox
(Group B), so ``platform/outbox`` can handle any module's events
uniformly without importing that module.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable


@runtime_checkable
class DomainEvent(Protocol):
    """Structural contract — no inheritance required.

    A module's event dataclasses satisfy this by declaring
    ``event_type``/``aggregate_type`` as class-level constants and
    ``aggregate_id``/``to_payload()`` as instance members; see
    ``tenant_events.py`` for the pattern.
    """

    event_type: str
    aggregate_type: str

    @property
    def aggregate_id(self) -> str: ...

    def to_payload(self) -> dict[str, Any]: ...
