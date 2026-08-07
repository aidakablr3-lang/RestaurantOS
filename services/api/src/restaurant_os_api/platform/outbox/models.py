"""The Outbox table's SQLAlchemy model.

Technical Architecture v2.0 Group B / Data Architecture v2.0 SS5.11.
Lives in ``platform/outbox``, not inside any specific module's
Infrastructure layer — this table is genuinely shared-kernel: every
module's use cases write their own domain events here through the same
``OutboxWriter`` port (see ``outbox_writer.py`` and
``sqlalchemy_outbox_writer.py`` in this package).

Deliberately carries no foreign keys to any business table — an outbox
insert must never fail because of an unrelated constraint on a table it
doesn't even need to join to. ``tenant_id`` is a plain column for the
same reason, not a FK.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import Base, ULIDPrimaryKeyMixin
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class OutboxEventModel(Base, ULIDPrimaryKeyMixin):
    __tablename__ = "outbox_events"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index(
            "ix_outbox_events_dispatched_at",
            "dispatched_at",
            postgresql_where="dispatched_at IS NULL",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    aggregate_type: Mapped[str] = mapped_column(Text, nullable=False)
    aggregate_id: Mapped[str] = mapped_column(Text, nullable=False)
    event_type: Mapped[str] = mapped_column(Text, nullable=False)
    event_version: Mapped[int] = mapped_column(SmallInteger, nullable=False, server_default="1")
    payload: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    dispatched_at: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True, default=None
    )
