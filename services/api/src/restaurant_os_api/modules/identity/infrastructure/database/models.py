"""SQLAlchemy ORM models for the identity module's login/refresh/logout slice.

Scope note: Role, Permission, RolePermission, and UserRole are
deliberately **not** included in this file. UserRole optionally scopes a
role assignment to a Branch (Data Architecture v2.0 SS3.1), and the
``branches`` table does not exist until the Restaurant module lands —
adding that foreign key now would either dangle or force this PR to
reach into an unrelated module. RBAC is authorization (which permissions
a session may exercise), not authentication (whether the session is
valid at all); this PR implements only the latter. See the PR
description's "Not Included" section.
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import BigInteger, CheckConstraint, ForeignKey, Index, Text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

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
