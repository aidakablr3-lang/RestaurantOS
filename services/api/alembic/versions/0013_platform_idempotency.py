"""platform-scoped idempotency keys, for tenant creation

Revision ID: 0013
Revises: 0012
Create Date: 2026-08-16

Closes a real, disclosed gap: ``IdempotencyGuard``/``idempotency_keys``
(0005) is wired into 16 routers but never into
``admin_tenant_router.py``'s ``POST /api/v1/admin/tenants`` (tenant
onboarding), so a retried or double-submitted create-tenant request
could create a duplicate tenant.

``idempotency_keys`` itself cannot be reused for this: ``tenant_id`` is
a hard `NOT NULL` foreign key to ``tenants.id`` (0005's own
``TenantScopedMixin``), but tenant *creation* is the one operation that
by definition runs before any tenant row exists to reference. This is
the same "runs before a tenant is authoritatively known" situation
``UnitOfWork``'s own docstring already documents for the login use
case -- and the same reason ``tenants`` itself carries no
``tenant_id``/RLS policy. ``platform_idempotency_keys`` follows that
existing precedent: no ``tenant_id`` column, no RLS policy (there is no
tenant to scope it to), keyed globally on ``idempotency_key`` alone,
used only by platform-admin-gated routes that are pre-tenant by nature
(today: just tenant onboarding).

Structurally identical to 0005's ``idempotency_keys`` otherwise --
same placeholder-row-then-update concurrency mechanism, same TTL-based
expiry column for the same not-yet-built cleanup job.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0013"
down_revision: str | None = "0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ULID_REGEX = r"^[0-9A-HJKMNP-TV-Z]{26}$"


def upgrade() -> None:
    op.create_table(
        "platform_idempotency_keys",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.Text(), nullable=False),
        sa.Column("request_fingerprint", sa.Text(), nullable=False),
        # NULL until the guarded use case completes -- same
        # concurrency-safety mechanism as idempotency_keys (0005): the
        # placeholder row's UNIQUE(idempotency_key) is what makes a
        # concurrent duplicate fail fast rather than race the use case.
        sa.Column("response_status", sa.Integer(), nullable=True),
        sa.Column("response_body", postgresql.JSONB(), nullable=True),
        sa.Column(
            "created_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id", name=conv("pk_platform_idempotency_keys")),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_platform_idempotency_keys_id_is_valid_ulid")
        ),
        sa.UniqueConstraint(
            "idempotency_key", name=conv("uq_platform_idempotency_keys_idempotency_key")
        ),
    )
    # Supports the (not-yet-built, out of scope here) periodic cleanup
    # job that deletes expired rows -- same rationale as 0005's matching
    # index on idempotency_keys.
    op.create_index(
        "ix_platform_idempotency_keys_expires_at", "platform_idempotency_keys", ["expires_at"]
    )


def downgrade() -> None:
    op.drop_table("platform_idempotency_keys")
