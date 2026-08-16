"""The idempotency_keys table's SQLAlchemy model.

Technical Architecture v2.0 Group B/E, ``platform/idempotency`` --
shared-kernel, like ``platform/outbox``: every module's mutating use
cases can be wrapped by ``IdempotencyGuard`` (``guard.py``), not just
Restaurant Platform's own Step 4 endpoints.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import Integer, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import Base, TenantScopedMixin, ULIDPrimaryKeyMixin
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class IdempotencyKeyModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    __tablename__ = "idempotency_keys"
    __table_args__ = (ulid_check_constraint("id"),)

    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    # NULL until the guarded use case completes -- see IdempotencyGuard's
    # own docstring for why this is the concurrency-safety mechanism.
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)


class PlatformIdempotencyKeyModel(Base, ULIDPrimaryKeyMixin):
    """Same shape as ``IdempotencyKeyModel``, deliberately without
    ``TenantScopedMixin`` -- see ``PlatformIdempotencyGuard``'s own
    docstring (``guard.py``) for why tenant-creation idempotency cannot
    use the tenant-scoped table: there is no tenant row yet to satisfy
    that column's ``NOT NULL`` foreign key. Global uniqueness on
    ``idempotency_key`` alone is correct here precisely because this
    table only ever backs platform-admin routes that are pre-tenant by
    nature (today: just tenant onboarding)."""

    __tablename__ = "platform_idempotency_keys"
    __table_args__ = (ulid_check_constraint("id"),)

    idempotency_key: Mapped[str] = mapped_column(Text, nullable=False, unique=True)
    request_fingerprint: Mapped[str] = mapped_column(Text, nullable=False)
    response_status: Mapped[int | None] = mapped_column(Integer, nullable=True, default=None)
    response_body: Mapped[dict[str, Any] | None] = mapped_column(JSONB, nullable=True, default=None)
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    expires_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
