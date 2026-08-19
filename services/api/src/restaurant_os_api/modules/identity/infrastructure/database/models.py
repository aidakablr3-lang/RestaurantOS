"""SQLAlchemy ORM models for the identity module.

Sprint 5, Step 2 (RBAC Foundation) adds ``RoleModel``, ``PermissionModel``,
``RolePermissionModel``, ``UserRoleModel`` below — the follow-up the
original Sprint 3 scope note (superseded, quoted for history) pointed
at: "RBAC has no consumer until a protected, non-auth route exists.
Tracked as a follow-up PR." ``UserRoleModel.branch_id`` is still a
plain, unconstrained column, not yet FK'd to ``branches`` — that table
is created by migration 0004 (Restaurant Platform), which also adds
the FK constraint (see ``0003_rbac_foundation.py``'s own docstring).
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


class OwnerActivationTokenModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin):
    """Phase 1 design doc SSA.4 / migration 0014.

    Only a hash of the activation token is ever stored, the same
    ``sessions.refresh_token_hash`` discipline. No ``TimestampMixin``:
    ``issued_at``/``expires_at``/``used_at`` are this table's complete
    lifecycle — there is no separate ``updated_at`` concept for a row
    that is written once and marked used at most once. No RLS on this
    table (migration 0014's own docstring has the full reasoning) —
    ``tenant_id`` is still a real, indexed, `NOT NULL`` FK column here
    (application-layer scoping and referential integrity still apply),
    it just isn't backed by a `CREATE POLICY` the way every other
    ``TenantScopedMixin`` table's is.
    """

    __tablename__ = "owner_activation_tokens"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index("ix_owner_activation_tokens_token_hash", "token_hash", unique=True),
        Index("ix_owner_activation_tokens_user_id", "user_id"),
    )

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    token_hash: Mapped[str] = mapped_column(Text, nullable=False)
    issued_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    expires_at: Mapped[datetime] = mapped_column(TimestampType(timezone=True), nullable=False)
    used_at: Mapped[datetime | None] = mapped_column(
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


class PermissionModel(Base):
    """RBAC Foundation Architecture SS4.2/SS13.1. ``code`` is the primary
    key (not a ULID) — a deliberate deviation, mirroring the
    ``ChartOfAccount.account_code`` precedent for a small,
    human-referenced, platform-seeded reference table. No ``tenant_id``
    at all: pure platform reference data, same as ``currencies``."""

    __tablename__ = "permissions"
    __table_args__ = (
        CheckConstraint(r"code ~ '^[a-z][a-z0-9_]*\.[a-z][a-z0-9_]*$'", name="code_is_valid"),
    )

    code: Mapped[str] = mapped_column(Text, primary_key=True)
    module: Mapped[str] = mapped_column(Text, nullable=False, index=True)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )


class RoleModel(Base, ULIDPrimaryKeyMixin, TimestampMixin):
    """RBAC Foundation Architecture SS4.1. ``tenant_id`` nullable — NULL
    means platform-wide, visible to every tenant (this table's RLS
    policy explicitly allows ``tenant_id IS NULL`` rows through,
    matching ``FeatureFlagModel``'s own precedent exactly). No
    platform-wide row is created by Sprint 5's own migration seed data
    — the nullable column exists so that path stays open later."""

    __tablename__ = "roles"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("default_scope IN ('tenant', 'branch')", name="default_scope_is_valid"),
        Index(
            "uq_roles_tenant_id_name",
            "tenant_id",
            "name",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
    )

    tenant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True, index=True
    )
    name: Mapped[str] = mapped_column(Text, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    default_scope: Mapped[str] = mapped_column(Text, nullable=False, server_default="branch")
    is_system: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="false")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")


class RolePermissionModel(Base, ULIDPrimaryKeyMixin):
    """RBAC Foundation Architecture SS4.3. A pure association row (Data
    Architecture v2.0 Group F: "no independent audit weight") — no
    ``TimestampMixin``/``SoftDeleteMixin`` beyond ``created_at``, matching
    the base catalogue's own ``RolePermission`` classification."""

    __tablename__ = "role_permissions"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index(
            "uq_role_permissions_role_id_permission_code",
            "role_id",
            "permission_code",
            unique=True,
        ),
    )

    role_id: Mapped[str] = mapped_column(
        Text, ForeignKey("roles.id", ondelete="CASCADE"), nullable=False, index=True
    )
    permission_code: Mapped[str] = mapped_column(
        Text, ForeignKey("permissions.code", ondelete="RESTRICT"), nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )


class UserRoleModel(Base, ULIDPrimaryKeyMixin, TenantScopedMixin, TimestampMixin, SoftDeleteMixin):
    """RBAC Foundation Architecture SS4.4. ``branch_id``: plain,
    unconstrained ``TEXT`` — FK to ``branches.id`` intentionally
    deferred to migration 0004 (Restaurant Platform), same rationale as
    ``SessionModel.device_id``/``SystemSettingModel.branch_id``.
    ``UNIQUE NULLS NOT DISTINCT (user_id, role_id, branch_id)`` is what
    makes one user holding a tenant-wide role plus multiple
    branch-specific roles simultaneously both possible and
    duplicate-safe at the database level."""

    __tablename__ = "user_roles"
    __table_args__ = (
        ulid_check_constraint("id"),
        Index(
            "uq_user_roles_user_id_role_id_branch_id",
            "user_id",
            "role_id",
            "branch_id",
            unique=True,
            postgresql_nulls_not_distinct=True,
        ),
        Index("ix_user_roles_role_id", "role_id"),
        Index("ix_user_roles_branch_id", "branch_id"),
    )

    user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role_id: Mapped[str] = mapped_column(
        Text, ForeignKey("roles.id", ondelete="RESTRICT"), nullable=False
    )
    branch_id: Mapped[str | None] = mapped_column(Text, nullable=True)
    granted_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    granted_by_user_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )


# Note: OutboxEventModel is NOT defined here. It is genuinely
# cross-module, shared-kernel infrastructure (every future module writes
# its own domain events to the same table) — it lives in
# platform/outbox/models.py, not inside a specific module's
# Infrastructure layer. It shares this file's ``outbox_events`` table
# (created by this same migration) but is registered on ``Base.metadata``
# from its own home in ``platform``.
