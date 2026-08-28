"""branches.gstin -- Indian GST registration number

Revision ID: 0018
Revises: 0017
Create Date: 2026-08-28

GST registration is granted per legal entity *per state*. The legal
entity concept in this schema lives on Restaurant (its own legal_name),
but registration validity is scoped to state, and only Branch (via its
address) represents a location specific enough to vary by state -- a
Restaurant operating branches in two states legally needs two
different GSTINs, which a single Restaurant-level column can't hold.
Branches in the same state under the same Restaurant will legitimately
share one value, stored redundantly rather than introducing a new
(restaurant, state) -> GSTIN table nothing here has asked for.

Nullable, new column: existing rows all get NULL, which the CHECK
below always accepts, so unlike migration 0017 this needs no
pre-migration audit -- a new nullable column cannot violate anything
that already exists.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0018"
down_revision: str | None = "0017"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "ck_branches_gstin_is_valid"
_CHECK = "gstin IS NULL OR gstin ~ '^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$'"


def upgrade() -> None:
    op.add_column("branches", sa.Column("gstin", sa.Text(), nullable=True))
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "branches", _CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "branches", type_="check")
    op.drop_column("branches", "gstin")
