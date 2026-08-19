"""onboarding copilot phase 1 -- run/step/audit tables, owner activation

Revision ID: 0014
Revises: 0013
Create Date: 2026-08-18

Four new tables for the RestaurantOS Setup Copilot, Phase 1
(docs/PHASE1_DESIGN.md):

``onboarding_runs`` / ``onboarding_step_states`` / ``onboarding_audit_log``
-- deliberately **not** RLS-protected and carry no ``NOT NULL`` FK to
``tenants``. ``onboarding_runs.tenant_id`` is genuinely unknown until the
``provision_tenant`` step verifies, and the step graph has to be seeded
(most steps ``blocked``, one ``ready``) *before* a tenant exists at all --
so ``onboarding_step_states`` rows are null-tenant too, for a while. This
follows the same precedent ``tenants`` itself and ``platform_idempotency_keys``
(0013) already set for "runs before a tenant is authoritatively known":
no RLS, access controlled by ``require_platform_admin`` at the route
layer instead (design doc SS0 flag #4, SSC).

``owner_activation_tokens`` carries a ``TenantScopedMixin``-shaped
``tenant_id`` column (created inside the same transaction as the tenant
and its Owner -- see ``TenantProvisioningService.provision()``) but
**deliberately no RLS policy**, unlike ``sessions`` (0001), which it is
otherwise modeled on (hash-only storage, mirroring
``sessions.refresh_token_hash``). This is not the same exemption reason
as the three onboarding tables above: the row's tenant is known at
INSERT time. The problem is the one READ path that matters --
``POST /api/v1/owner-activation`` -- which starts from nothing but the
raw token; the caller has no ``tenant_id`` to supply (unlike
``SessionRepository.get_by_refresh_token_hash``, whose own docstring
notes ``tenant_id`` is "supplied by the caller" from the refresh
request's own body -- a field an activation request has no equivalent
of, since discovering the tenant *is* the point). An RLS policy keyed on
``current_setting('app.tenant_id', true)`` would evaluate to `NULL` with
no tenant context set, and ``tenant_id = NULL`` is never true in SQL --
the row would be structurally unfindable by the one caller who needs to
find it. So this table joins ``platform_idempotency_keys``' precedent
for a different reason: not "no tenant exists yet" but "which tenant is
unknown until this exact read resolves it." Once resolved,
``ActivateOwnerUseCase`` re-enters through ``UnitOfWork(session_factory,
TenantContext(token.tenant_id))`` for the actual ``users`` row update --
that write is fully RLS-protected as normal; only the token table's own
lookup is exempt.

**Integrity safeguard for the RLS exemption** (design doc SSA.1): since
``onboarding_runs`` has no RLS, it loses the usual guarantee that a row's
tenant can't silently change out from under it. Two constraints close
that gap without needing RLS:

- A ``CHECK`` (single-row invariant): a run cannot be ``completed`` while
  still tenant-less.
- A ``BEFORE UPDATE`` trigger (transition invariant, needs ``OLD``/``NEW``,
  so it can't be a ``CHECK``): once ``tenant_id`` is set, it can never
  become a *different* non-null value.

This is deliberately narrower than "every tenant has >=1 Owner grant"
(SSD's invariant, not enforced by any constraint or trigger here -- that
one needs cross-table aggregation over ``user_roles``/``roles``, a
meaningfully heavier and more fragile thing than a single-column
monotonic-once-set check on one row's own ``OLD``/``NEW`` values).

``run_id`` on both ``onboarding_step_states`` and ``onboarding_audit_log``
cascades on delete from ``onboarding_runs`` -- this is what makes
``scripts/purge_tenant.py``'s existing dynamic tenant-scoped-table
discovery (``information_schema.columns WHERE column_name = 'tenant_id'``)
correctly clean up all three onboarding tables for a purged tenant even
though only ``onboarding_runs`` itself has a ``tenant_id`` column: purge
deletes the ``onboarding_runs`` row it finds by ``tenant_id``, and the
cascade takes the dependent ``onboarding_step_states``/``onboarding_audit_log``
rows with it. No change to ``purge_tenant.py`` needed or made here --
verified by this migration's own FK choice, not assumed.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0014"
down_revision: str | None = "0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ULID_REGEX = r"^[0-9A-HJKMNP-TV-Z]{26}$"


def upgrade() -> None:
    # --- onboarding_runs -----------------------------------------------------
    op.create_table(
        "onboarding_runs",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=True),
        sa.Column("status", sa.Text(), nullable=False, server_default="in_progress"),
        sa.Column("created_by_user_id", sa.Text(), nullable=False),
        sa.Column(
            "context",
            postgresql.JSONB(),
            nullable=False,
            server_default=sa.text("'{}'::jsonb"),
        ),
        sa.Column(
            "started_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.Column("completed_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=conv("pk_onboarding_runs")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=conv("fk_onboarding_runs_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["created_by_user_id"],
            ["users.id"],
            name=conv("fk_onboarding_runs_created_by_user_id_users"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_onboarding_runs_id_is_valid_ulid")
        ),
        sa.CheckConstraint(
            "status IN ('in_progress', 'blocked', 'completed', 'abandoned')",
            name=conv("ck_onboarding_runs_status_is_valid"),
        ),
        sa.CheckConstraint(
            "status <> 'completed' OR tenant_id IS NOT NULL",
            name=conv("ck_onboarding_runs_completed_has_tenant"),
        ),
    )
    op.create_index("ix_onboarding_runs_tenant_id", "onboarding_runs", ["tenant_id"])
    op.create_index(
        "ix_onboarding_runs_created_by_user_id", "onboarding_runs", ["created_by_user_id"]
    )

    # --- onboarding_step_states -----------------------------------------------
    op.create_table(
        "onboarding_step_states",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=False),
        sa.Column("status", sa.Text(), nullable=False, server_default="blocked"),
        sa.Column("input", postgresql.JSONB(), nullable=True),
        sa.Column("output", postgresql.JSONB(), nullable=True),
        sa.Column("idempotency_key", sa.Text(), nullable=True),
        sa.Column("verify_evidence", sa.Text(), nullable=True),
        sa.Column("error", sa.Text(), nullable=True),
        sa.Column("attempts", sa.Integer(), nullable=False, server_default="0"),
        sa.Column(
            "updated_at",
            sa.TIMESTAMP(timezone=True),
            server_default=sa.text("now()"),
            nullable=False,
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_onboarding_step_states")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["onboarding_runs.id"],
            name=conv("fk_onboarding_step_states_run_id_onboarding_runs"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_onboarding_step_states_id_is_valid_ulid")
        ),
        sa.CheckConstraint(
            "status IN ('blocked', 'ready', 'collecting', 'executing', "
            "'verified', 'failed', 'skipped')",
            name=conv("ck_onboarding_step_states_status_is_valid"),
        ),
        sa.UniqueConstraint(
            "run_id", "step_id", name=conv("uq_onboarding_step_states_run_id_step_id")
        ),
    )
    op.create_index("ix_onboarding_step_states_run_id", "onboarding_step_states", ["run_id"])

    # --- onboarding_audit_log -------------------------------------------------
    op.create_table(
        "onboarding_audit_log",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("run_id", sa.Text(), nullable=False),
        sa.Column("step_id", sa.Text(), nullable=True),
        sa.Column("actor_type", sa.Text(), nullable=False),
        sa.Column("actor_id", sa.Text(), nullable=True),
        sa.Column("action", sa.Text(), nullable=False),
        sa.Column("request", postgresql.JSONB(), nullable=False),
        sa.Column("response", postgresql.JSONB(), nullable=False),
        sa.Column(
            "at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_onboarding_audit_log")),
        sa.ForeignKeyConstraint(
            ["run_id"],
            ["onboarding_runs.id"],
            name=conv("fk_onboarding_audit_log_run_id_onboarding_runs"),
            ondelete="CASCADE",
        ),
        sa.ForeignKeyConstraint(
            ["actor_id"],
            ["users.id"],
            name=conv("fk_onboarding_audit_log_actor_id_users"),
            ondelete="SET NULL",
        ),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_onboarding_audit_log_id_is_valid_ulid")
        ),
        sa.CheckConstraint(
            "actor_type IN ('human', 'copilot')",
            name=conv("ck_onboarding_audit_log_actor_type_is_valid"),
        ),
    )
    op.create_index("ix_onboarding_audit_log_run_id", "onboarding_audit_log", ["run_id"])

    # --- owner_activation_tokens (RLS-protected, tenant-scoped) --------------
    op.create_table(
        "owner_activation_tokens",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("user_id", sa.Text(), nullable=False),
        sa.Column("token_hash", sa.Text(), nullable=False),
        sa.Column("issued_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("expires_at", sa.TIMESTAMP(timezone=True), nullable=False),
        sa.Column("used_at", sa.TIMESTAMP(timezone=True), nullable=True),
        sa.PrimaryKeyConstraint("id", name=conv("pk_owner_activation_tokens")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=conv("fk_owner_activation_tokens_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["user_id"],
            ["users.id"],
            name=conv("fk_owner_activation_tokens_user_id_users"),
            ondelete="CASCADE",
        ),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_owner_activation_tokens_id_is_valid_ulid")
        ),
    )
    op.create_index("ix_owner_activation_tokens_tenant_id", "owner_activation_tokens", ["tenant_id"])
    op.create_index("ix_owner_activation_tokens_user_id", "owner_activation_tokens", ["user_id"])
    op.create_index(
        "ix_owner_activation_tokens_token_hash",
        "owner_activation_tokens",
        ["token_hash"],
        unique=True,
    )

    # No RLS on owner_activation_tokens -- see module docstring: the one
    # read path that matters (activation by raw token alone) has no
    # tenant context to set, so a tenant_isolation policy here would
    # make the row unfindable by design, not protect it.

    # --- onboarding_runs.tenant_id immutability (design doc SSA.1) -----------
    op.execute(
        """
        CREATE FUNCTION onboarding_runs_tenant_id_immutable() RETURNS trigger AS $$
        BEGIN
            IF OLD.tenant_id IS NOT NULL AND NEW.tenant_id IS DISTINCT FROM OLD.tenant_id THEN
                RAISE EXCEPTION 'onboarding_runs.tenant_id is immutable once set (run %)', OLD.id;
            END IF;
            RETURN NEW;
        END;
        $$ LANGUAGE plpgsql;
        """
    )
    op.execute(
        """
        CREATE TRIGGER trg_onboarding_runs_tenant_id_immutable
        BEFORE UPDATE ON onboarding_runs
        FOR EACH ROW EXECUTE FUNCTION onboarding_runs_tenant_id_immutable();
        """
    )


def downgrade() -> None:
    op.execute(
        "DROP TRIGGER IF EXISTS trg_onboarding_runs_tenant_id_immutable ON onboarding_runs"
    )
    op.execute("DROP FUNCTION IF EXISTS onboarding_runs_tenant_id_immutable()")

    op.drop_table("owner_activation_tokens")
    op.drop_table("onboarding_audit_log")
    op.drop_table("onboarding_step_states")
    op.drop_table("onboarding_runs")
