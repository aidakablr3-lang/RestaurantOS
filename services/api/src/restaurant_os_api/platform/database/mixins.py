"""Cross-cutting SQLAlchemy mixins.

Data Architecture v2.0 SS2.1/SS5.1 and Technical Architecture v2.0 SS10.6:
every entity composes exactly the mixins its Catalogue lifecycle calls
for. An Immutable-lifecycle entity never includes SoftDeleteMixin.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import CheckConstraint, ForeignKey, Text
from sqlalchemy.orm import Mapped, declared_attr, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.core.ids import ULID_PATTERN, generate_ulid


def ulid_check_constraint(column_name: str = "id") -> CheckConstraint:
    """A CHECK constraint validating a column is a well-formed ULID.

    Called explicitly from each concrete model's ``__table_args__``
    rather than contributed automatically by ``ULIDPrimaryKeyMixin`` —
    SQLAlchemy does not cleanly merge ``__table_args__`` declared by more
    than one mixin on the same model, and a silently-dropped constraint
    is a worse outcome than one extra explicit line per model
    (Data Architecture v2.0 Group H).
    """
    return CheckConstraint(
        f"{column_name} ~ '{ULID_PATTERN}'",
        name=f"{column_name}_is_valid_ulid",
    )


class ULIDPrimaryKeyMixin:
    """A ULID-format TEXT primary key column named ``id``.

    ``TEXT``, never ``CHAR(n)`` — Data Architecture v2.0 Group H: Postgres's
    ``CHAR(n)`` has no storage advantage over ``text`` and introduces
    trailing-whitespace comparison surprises that have no place in a
    primary key.
    """

    id: Mapped[str] = mapped_column(Text, primary_key=True, default=generate_ulid)


class TenantScopedMixin:
    """A required ``tenant_id`` foreign key, indexed.

    This is the literal enforcement surface for Data Architecture v2.0
    SS4.1's dual isolation layer: the application-layer base repository
    filters on this column on every query, and the database's Row-Level
    Security policy checks it against the transaction-scoped
    ``SET LOCAL app.tenant_id`` value.
    """

    @declared_attr
    def tenant_id(cls) -> Mapped[str]:
        return mapped_column(
            Text,
            ForeignKey("tenants.id", ondelete="RESTRICT"),
            nullable=False,
            index=True,
        )


class TimestampMixin:
    """``created_at`` / ``updated_at``, both timezone-aware.

    ``updated_at``'s ``onupdate`` is defense-in-depth for ORM-mediated
    writes; the authoritative guarantee is the ``set_updated_at()``
    database trigger applied to every table carrying this mixin in the
    Alembic migration, so the invariant holds even for raw SQL or bulk
    operations that bypass the ORM (Technical Architecture v2.0 SS5.1).
    """

    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


class SoftDeleteMixin:
    """A nullable ``deleted_at`` marker.

    Omitted entirely on Immutable-lifecycle entities (Data Architecture
    v2.0 Part 1 SS3's legend) — soft-delete is meaningless for a row that
    must never be deleted at all.
    """

    deleted_at: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), default=None)
