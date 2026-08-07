"""SQLAlchemy ORM models for the identity module.

Scope note: Role, Permission, RolePermission, and UserRole are
deliberately **not** included in this file. UserRole optionally scopes a
role assignment to a Branch (Data Architecture v2.0 SS3.1), and the
``branches`` table does not exist until the Restaurant module lands —
adding that foreign key now would either dangle or force this PR to
reach into an unrelated module. RBAC is authorization (which permissions
a session may exercise), not authentication (whether the session is
valid at all); Sprint 3 implemented only the latter, and Sprint 4.1
(Tenant Platform) adds a single interim ``is_platform_admin`` flag
rather than pulling RBAC forward — see the identity module README.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import BigInteger, Boolean, CheckConstraint, ForeignKey, Index, SmallInteger, Text
from sqlalchemy.dialects.postgresql import CITEXT, JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import (
    Base,
    SoftDeleteMixin,
    TenantScopedMixin,
    TimestampMixin,
    ULIDPrimaryKeyMixin,
)
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class TenantModel(Base, ULIDPrimaryKeyMixin, TimestampMixin):
    """Data Architecture v2.0 SS5.2.

    No ``tenant_id`` (it *is* the tenant root) and no ``deleted_at`` —
    lifecycle is governed entirely by ``status`` and the offboarding
    state machine (Data Architecture v2.0 SS4.5/SS4.6), not a generic
    soft-delete flag.
    """

    __tablename__ = "tenants"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("tenant_tier IN ('shared', 'dedicated')", name="tenant_tier_is_valid"),
        CheckConstraint(
            "status IN ('provisioning', 'active', 'suspended', 'migrating', 'offboarded')",
            name="status_is_valid",
        ),
        CheckConstraint(
            "default_currency_code ~ '^[A-Z]{3}$'", name="default_currency_code_is_iso4217"
        ),
        Index("ix_tenants_status", "status", postgresql_where="status <> 'active'"),
    )

    legal_name: Mapped[str] = mapped_column(Text, nullable=False)
    display_name: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="shared")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="provisioning")
    # FK to `currencies.code` intentionally deferred until that reference
    # table exists (see module docstring) — validated by CHECK for now.
    default_currency_code: Mapped[str] = mapped_column(Text, nullable=False)
    # Mapped to the Python name `tenant_metadata`, not `metadata` — that
    # name is reserved on every SQLAlchemy declarative model (it's the
    # class-level `Base.metadata` MetaData object). The database column
    # itself is still named `metadata` (Sprint 4.1's "tenant metadata"
    # requirement), via the explicit first positional arg below.
    tenant_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, nullable=False, server_default="{}"
    )


class UserModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    """Data Architecture v2.0 SS5.3."""

    __tablename__ = "users"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("status IN ('invited', 'active', 'deactivated')", name="status_is_valid"),
        CheckConstraint(
            "email IS NOT NULL OR pin_hash IS NOT NULL",
            name="has_at_least_one_login_method",
        ),
        Index(
            "uq_users_tenant_id_email",
            "tenant_id",
            "email",
            unique=True,
            postgresql_where="email IS NOT NULL AND deleted_at IS NULL",
        ),
        Index("ix_users_tenant_id_status", "tenant_id", "status"),
    )

    email: Mapped[str | None] = mapped_column(CITEXT, nullable=True)
    phone: Mapped[str | None] = mapped_column(Text, nullable=True)
    password_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    pin_hash: Mapped[str | None] = mapped_column(Text, nullable=True)
    permission_version: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="invited")
    # Sprint 4.1 (Tenant Platform), approved plan Decision C: an interim,
    # explicitly-not-RBAC gate for tenant-lifecycle mutation endpoints.
    is_platform_admin: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")


class SessionModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Data Architecture v2.0 SS3.1.

    Only a hash of the refresh token is ever stored (Data Architecture
    v2.0 SS11.4) — this table never holds a usable bearer credential.
    No ``SoftDeleteMixin``: a session is either active or revoked
    (``revoked_at``), not soft-deleted — the distinction matters for
    audit ("was this session ever valid" vs. "was it later revoked").
    """

    __tablename__ = "sessions"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index("ix_sessions_refresh_token_hash", "refresh_token_hash", unique=True),
        Index("ix_sessions_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    # FK to `devices.id` intentionally deferred until the Restaurant
    # module's Device table exists (see module docstring's rationale,
    # applied identically here).
    device_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    refresh_token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True, default=None
    )


class SubscriptionModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Sprint 4.1 (Tenant Platform). One current subscription per tenant —
    a plan change updates this row in place; full billing history is out
    of this sprint's scope (see the module README)."""

    __tablename__ = "subscriptions"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('trialing', 'active', 'past_due', 'canceled', 'expired')",
            name="status_is_valid",
        ),
        CheckConstraint("max_branches > 0", name="max_branches_is_positive"),
        CheckConstraint("max_users > 0", name="max_users_is_positive"),
        CheckConstraint("max_monthly_orders > 0", name="max_monthly_orders_is_positive"),
        Index("uq_subscriptions_tenant_id", "tenant_id", unique=True),
    )

    plan_code: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="trialing")
    current_period_end: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), nullable=False
    )
    trial_end: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)
    next_billing_date: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True
    )
    grace_period_until: Mapped[datetime | None] = mapped_column(
        TimestampType(timezone=True), nullable=True
    )
    max_branches: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="1")
    max_users: Mapped[int] = mapped_column(BigInteger, nullable=False, server_default="5")
    max_monthly_orders: Mapped[int] = mapped_column(
        BigInteger, nullable=False, server_default="1000"
    )


class SystemSettingModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin):
    """Sprint 4.1. ``branch_id`` is present but always NULL until the
    Restaurant module's Branch table exists — see the module README."""

    __tablename__ = "system_settings"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index(
            "uq_system_settings_tenant_id_branch_id_key",
            "tenant_id",
            "branch_id",
            "key",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    # FK to `branches.id` intentionally deferred, same rationale as
    # SessionModel.device_id.
    branch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    key: Mapped[str] = mapped_column(Text, nullable=False)
    value: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)


class FeatureFlagModel(Base, ULIDPrimaryKeyMixin, TimestampMixin):
    """Sprint 4.1. ``tenant_id`` is nullable — NULL means platform-wide,
    visible to every tenant (enforced by this table's RLS policy, which
    explicitly allows ``tenant_id IS NULL`` rows through)."""

    __tablename__ = "feature_flags"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("rollout_percentage BETWEEN 0 AND 100", name="rollout_percentage_is_valid"),
        Index(
            "uq_feature_flags_tenant_id_key",
            "tenant_id",
            "key",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    key: Mapped[str] = mapped_column(Text, nullable=False)
    tenant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tenants.id", ondelete="CASCADE"), nullable=True, index=True
    )
    enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    rollout_percentage: Mapped[int] = mapped_column(
        SmallInteger, nullable=False, server_default="100"
    )
    start_date: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)
    end_date: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True), nullable=True)


class TenantDirectoryEntryModel(Base):
    """Data Architecture v2.0 SS4.4 — the Tenant Directory Service.

    Not tenant-scoped in the RLS sense (like ``tenants`` itself, this
    table is routing metadata *about* a tenant, not a tenant's own data)
    and uses ``tenant_id`` as its primary key directly rather than a
    separate ULID, matching SS4.4's exact spec — a directory entry is a
    1:1 satellite of its tenant, never independently identified.
    """

    __tablename__ = "tenant_directory_entries"
    __table_args__ = (
        CheckConstraint("tenant_tier IN ('shared', 'dedicated')", name="tenant_tier_is_valid"),
        CheckConstraint(
            "status IN ('provisioning', 'active', 'suspended', 'migrating', 'offboarded')",
            name="status_is_valid",
        ),
    )

    tenant_id: Mapped[str] = mapped_column(
        Text, ForeignKey("tenants.id", ondelete="CASCADE"), primary_key=True
    )
    tenant_tier: Mapped[str] = mapped_column(Text, nullable=False, server_default="shared")
    shard_key: Mapped[str] = mapped_column(Text, nullable=False, server_default="shard-01")
    connection_ref: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="provisioning")
    updated_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class OutboxEventModel(Base, ULIDPrimaryKeyMixin):
    """Technical Architecture v2.0 Group B / Data Architecture v2.0 SS5.11.

    Deliberately carries no foreign keys to any business table — an
    outbox insert must never fail because of an unrelated constraint on
    a table it doesn't even need to join to. ``tenant_id`` is a plain
    column for the same reason, not a FK.
    """

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
