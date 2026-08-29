"""GST invoice numbering: branches.invoice_prefix, bills.invoice_number,
invoice_number_counters

Revision ID: 0019
Revises: 0018
Create Date: 2026-08-28

Three pieces:

1. ``branches.invoice_prefix`` -- owner-set (or auto-derived from the
   branch name), short code an invoice number series is built from.
   Existing branches are backfilled deterministically from their own
   name (first 2-4 alphanumeric characters, uppercased; a name with
   too few alphanumeric characters falls back to a slice of the
   branch's own id) -- this is harmless housekeeping, not fabricated
   invoice history, since no bill has ever been numbered yet.

2. A partial unique index on ``(gstin, invoice_prefix) WHERE gstin IS
   NOT NULL``. An invoice number series belongs to a GST registration,
   not a tenant: two branches sharing one GSTIN must never share a
   prefix, but two branches with different (or no) GSTINs may
   legitimately share one. Postgres treats every NULL as distinct in a
   unique index, and the WHERE clause excludes gstin-less rows
   entirely, so this only ever constrains branches that share a real
   registration.

3. ``bills.invoice_number`` (nullable) and ``invoice_number_counters``
   (one row per tenant/branch/financial-year, incremented via a single
   atomic ``INSERT ... ON CONFLICT ... DO UPDATE ... RETURNING`` --
   see ``SQLAlchemyInvoiceNumberCounterRepository``). Existing bills
   are **not** backfilled with a number -- whatever a customer actually
   received at transaction time (if anything was printed) already had
   no compliant number on it, and assigning one to the database row
   now wouldn't retroactively fix that paper trail. Only bills
   generated after this migration ships get a real number, and then
   only for a branch with a gstin on file (see GenerateBillUseCase).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0019"
down_revision: str | None = "0018"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_ULID_REGEX = r"^[0-9A-HJKMNP-TV-Z]{26}$"


def upgrade() -> None:
    # --- branches.invoice_prefix -----------------------------------------
    op.add_column("branches", sa.Column("invoice_prefix", sa.Text(), nullable=True))
    op.create_check_constraint(
        conv("ck_branches_invoice_prefix_is_valid"),
        "branches",
        "invoice_prefix IS NULL OR invoice_prefix ~ '^[A-Z0-9]{2,10}$'",
    )

    # Deterministic backfill for existing branches: first 2-4
    # alphanumeric characters of the name, uppercased. A name with
    # fewer than 2 alphanumeric characters (emoji-only, CJK-only, ...)
    # falls back to "BR" + the last 4 characters of the branch's own
    # id, mirroring CreateBranchUseCase's own default_invoice_prefix()
    # fallback exactly, so a freshly-migrated branch and a
    # freshly-created one get a prefix the same way.
    op.execute(
        """
        UPDATE branches
        SET invoice_prefix = UPPER(LEFT(REGEXP_REPLACE(name, '[^A-Za-z0-9]', '', 'g'), 4))
        WHERE invoice_prefix IS NULL
        """
    )
    op.execute(
        """
        UPDATE branches
        SET invoice_prefix = 'BR' || UPPER(RIGHT(id, 4))
        WHERE invoice_prefix IS NULL OR LENGTH(invoice_prefix) < 2
        """
    )
    op.alter_column("branches", "invoice_prefix", nullable=False)

    op.create_index(
        "uq_branches_gstin_invoice_prefix",
        "branches",
        ["gstin", "invoice_prefix"],
        unique=True,
        postgresql_where=sa.text("gstin IS NOT NULL"),
    )

    # --- bills.invoice_number ----------------------------------------------
    op.add_column("bills", sa.Column("invoice_number", sa.Text(), nullable=True))
    op.create_index(
        "uq_bills_tenant_id_invoice_number",
        "bills",
        ["tenant_id", "invoice_number"],
        unique=True,
        postgresql_where=sa.text("invoice_number IS NOT NULL"),
    )

    # --- invoice_number_counters ---------------------------------------------
    op.create_table(
        "invoice_number_counters",
        sa.Column("id", sa.Text(), nullable=False),
        sa.Column("tenant_id", sa.Text(), nullable=False),
        sa.Column("branch_id", sa.Text(), nullable=False),
        sa.Column("financial_year", sa.Text(), nullable=False),
        sa.Column("seq", sa.Integer(), nullable=False),
        sa.Column(
            "created_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.Column(
            "updated_at", sa.TIMESTAMP(timezone=True), server_default=sa.text("now()"), nullable=False
        ),
        sa.PrimaryKeyConstraint("id", name=conv("pk_invoice_number_counters")),
        sa.ForeignKeyConstraint(
            ["tenant_id"],
            ["tenants.id"],
            name=conv("fk_invoice_number_counters_tenant_id_tenants"),
            ondelete="RESTRICT",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"],
            ["branches.id"],
            name=conv("fk_invoice_number_counters_branch_id_branches"),
            ondelete="RESTRICT",
        ),
        sa.CheckConstraint(
            f"id ~ '{_ULID_REGEX}'", name=conv("ck_invoice_number_counters_id_is_valid_ulid")
        ),
        sa.CheckConstraint("seq > 0", name=conv("ck_invoice_number_counters_seq_is_positive")),
    )
    op.create_index(
        "ix_invoice_number_counters_tenant_id", "invoice_number_counters", ["tenant_id"]
    )
    op.create_index(
        "ix_invoice_number_counters_branch_id", "invoice_number_counters", ["branch_id"]
    )
    op.create_index(
        "uq_invoice_number_counters_tenant_branch_fy",
        "invoice_number_counters",
        ["tenant_id", "branch_id", "financial_year"],
        unique=True,
    )
    op.execute(
        """
        CREATE TRIGGER trg_invoice_number_counters_set_updated_at
        BEFORE UPDATE ON invoice_number_counters
        FOR EACH ROW
        EXECUTE FUNCTION set_updated_at();
        """
    )

    op.execute("ALTER TABLE invoice_number_counters ENABLE ROW LEVEL SECURITY")
    op.execute(
        """
        CREATE POLICY tenant_isolation ON invoice_number_counters
        USING (tenant_id = current_setting('app.tenant_id', true))
        """
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS trg_invoice_number_counters_set_updated_at ON invoice_number_counters")
    op.drop_table("invoice_number_counters")

    op.drop_index("uq_bills_tenant_id_invoice_number", table_name="bills")
    op.drop_column("bills", "invoice_number")

    op.drop_index("uq_branches_gstin_invoice_prefix", table_name="branches")
    op.drop_constraint(conv("ck_branches_invoice_prefix_is_valid"), "branches", type_="check")
    op.drop_column("branches", "invoice_prefix")
