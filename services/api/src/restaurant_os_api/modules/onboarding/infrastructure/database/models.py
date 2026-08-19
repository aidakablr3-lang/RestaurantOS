"""SQLAlchemy ORM models for the onboarding module -- migration 0014.

None of the three tables use ``TenantScopedMixin`` (``onboarding_runs.
tenant_id`` is nullable and not RLS-protected; ``onboarding_step_states``/
``onboarding_audit_log`` carry no ``tenant_id`` column at all -- their
tenant is reachable only via ``run_id`` -> ``onboarding_runs``) or
``TimestampMixin`` (each table's own timestamp shape is different:
``started_at``/``completed_at``, a bare ``updated_at``, and a bare
``at`` respectively -- none is the standard ``created_at``/``updated_at``
pair). See the migration's own module docstring for the full RLS-exemption
reasoning.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import TIMESTAMP as TimestampType
from sqlalchemy import CheckConstraint, ForeignKey, Index, Integer, Text, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy.sql import func

from restaurant_os_api.platform.database import Base, ULIDPrimaryKeyMixin
from restaurant_os_api.platform.database.mixins import ulid_check_constraint


class OnboardingRunModel(Base, ULIDPrimaryKeyMixin):
    __tablename__ = "onboarding_runs"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('in_progress', 'blocked', 'completed', 'abandoned')",
            name="status_is_valid",
        ),
        CheckConstraint(
            "status <> 'completed' OR tenant_id IS NOT NULL",
            name="completed_has_tenant",
        ),
        Index("ix_onboarding_runs_tenant_id", "tenant_id"),
        Index("ix_onboarding_runs_created_by_user_id", "created_by_user_id"),
    )

    tenant_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("tenants.id", ondelete="RESTRICT"), nullable=True
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="in_progress")
    created_by_user_id: Mapped[str] = mapped_column(
        Text, ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    context: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False, server_default="{}")
    started_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
    completed_at: Mapped[datetime | None] = mapped_column(TimestampType(timezone=True))


class OnboardingStepStateModel(Base, ULIDPrimaryKeyMixin):
    __tablename__ = "onboarding_step_states"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint(
            "status IN ('blocked', 'ready', 'collecting', 'executing', "
            "'verified', 'failed', 'skipped')",
            name="status_is_valid",
        ),
        UniqueConstraint("run_id", "step_id", name="run_id_step_id"),
        Index("ix_onboarding_step_states_run_id", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("onboarding_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="blocked")
    input: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    output: Mapped[dict[str, Any] | None] = mapped_column(JSONB)
    idempotency_key: Mapped[str | None] = mapped_column(Text)
    verify_evidence: Mapped[str | None] = mapped_column(Text)
    error: Mapped[str | None] = mapped_column(Text)
    attempts: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")
    updated_at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )


class OnboardingAuditLogModel(Base, ULIDPrimaryKeyMixin):
    __tablename__ = "onboarding_audit_log"
    __table_args__ = (
        ulid_check_constraint("id"),
        CheckConstraint("actor_type IN ('human', 'copilot')", name="actor_type_is_valid"),
        Index("ix_onboarding_audit_log_run_id", "run_id"),
    )

    run_id: Mapped[str] = mapped_column(
        Text, ForeignKey("onboarding_runs.id", ondelete="CASCADE"), nullable=False
    )
    step_id: Mapped[str | None] = mapped_column(Text)
    actor_type: Mapped[str] = mapped_column(Text, nullable=False)
    actor_id: Mapped[str | None] = mapped_column(
        Text, ForeignKey("users.id", ondelete="SET NULL")
    )
    action: Mapped[str] = mapped_column(Text, nullable=False)
    request: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    response: Mapped[dict[str, Any]] = mapped_column(JSONB, nullable=False)
    at: Mapped[datetime] = mapped_column(
        TimestampType(timezone=True), server_default=func.now(), nullable=False
    )
