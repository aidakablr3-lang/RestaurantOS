"""inventory_categories.category_type -- food vs. beverage scoping

Revision ID: 0011
Revises: 0010
Create Date: 2026-08-14

Product decision: recipe-based food-inventory deduction can't be
trusted to reflect real chef usage (no way to verify what a chef
actually draws on vs. what a recipe says), so food inventory is being
de-scoped from routine day-to-day tracking; liquor/beverage inventory
stays tracked (via purchasing/goods-receipt records, Sprint 7 Step 6 --
no new tracking mechanism needed there). This column is what the
application layer's food-vs-beverage permission gate (``menu.read``/
``menu.manage`` additionally required to see or manage a ``food``
category or any item under one) reads to decide.

Purely additive: ``NOT NULL`` with ``server_default 'food'`` so every
existing ``inventory_categories`` row (and any row inserted
concurrently with this migration) keeps its current, fully-visible
behavior -- nothing is silently hidden by this migration alone; the
application-layer gate landing alongside it is what actually changes
visibility. The ``CHECK`` constraint mirrors the enum-column precedent
already used for ``menu_items.station`` (migration ``0009``).
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0011"
down_revision: str | None = "0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "inventory_categories",
        sa.Column("category_type", sa.Text(), nullable=False, server_default=sa.text("'food'")),
    )
    op.create_check_constraint(
        "category_type_is_valid",
        "inventory_categories",
        "category_type IN ('food', 'beverage')",
    )


def downgrade() -> None:
    op.drop_constraint("category_type_is_valid", "inventory_categories", type_="check")
    op.drop_column("inventory_categories", "category_type")
