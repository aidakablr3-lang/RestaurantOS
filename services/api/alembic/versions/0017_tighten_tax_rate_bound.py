"""taxes.rate: tighten the plausibility bound from 0-1 to 0-0.5

Revision ID: 0017
Revises: 0016
Create Date: 2026-08-27

A production incident stored rate=0.9 for a tenant's "CGST 9%"/"SGST
9%" taxes -- 0.9 is a legally-shaped fraction under the old 0-1 bound
(nothing distinguishes "a legitimate 90% rate" from "9% divided by 10
instead of 100"), so it passed every check in the stack and silently
overcharged every bill by 10x. No real restaurant tax rate is ever
above 50%; this migration makes that the DB's own floor, not just a
convention enforced above it.

WARNING -- this TIGHTENS the constraint, unlike migration 0016's pure
relaxation. Per docs/DEPLOYMENT.md's "any migration that adds/tightens
a constraint must be preceded by an audit query" rule: run this BEFORE
applying, across every tenant, not just the one from the incident --

    SELECT id, tenant_id, name, rate, is_active, created_at
    FROM taxes
    WHERE rate > 0.5
    ORDER BY tenant_id, created_at;

Any row returned will fail this migration outright (a plain CHECK
violation, not the crash-loop-on-container-start failure mode
migration 0015 hit -- `alembic upgrade head` runs as a one-shot step
before `api` starts serving, so this fails the deploy cleanly instead
of crash-looping a running container). Fix every returned row's rate
(divide by 10, or whatever the correct value actually is) before
re-running the migration.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0017"
down_revision: str | None = "0016"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "ck_taxes_rate_is_valid"
_OLD_CHECK = "rate >= 0 AND rate <= 1"
_NEW_CHECK = "rate >= 0 AND rate <= 0.5"


def upgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "taxes", type_="check")
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "taxes", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "taxes", type_="check")
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "taxes", _OLD_CHECK)
