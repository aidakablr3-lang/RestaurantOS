"""menu_items.recipe_id -> recipes.id foreign key

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-11

Sprint 7, Step 5 (Inventory + Recipe backend). ``menu_items.recipe_id``
has existed since migration ``0004`` as a reserved, nullable, FK-less
column -- its own comment there says "Inventory Platform's future FK
target -- reserved, unpopulated, no FK yet (Recipe doesn't exist)".
``recipes`` now exists (migration ``0007``), so this migration adds
the FK it was always reserved for. Purely additive: the column already
exists and is already nullable, so this is a metadata-only change with
zero risk to any existing row (every existing ``menu_items`` row has
``recipe_id IS NULL``, which trivially satisfies the new constraint).

``ON DELETE RESTRICT``, matching Data Architecture v2.0 Group G's
policy for FKs into an Immutable-lifecycle-adjacent table -- ``Recipe``
is versioned/superseded, never deleted, so a hard-delete attempt while
still referenced should fail loudly rather than silently null out a
menu item's recipe.
"""

from __future__ import annotations

from collections.abc import Sequence

from alembic import op

revision: str = "0008"
down_revision: str | None = "0007"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_foreign_key(
        "fk_menu_items_recipe_id_recipes",
        "menu_items",
        "recipes",
        ["recipe_id"],
        ["id"],
        ondelete="RESTRICT",
    )


def downgrade() -> None:
    op.drop_constraint("fk_menu_items_recipe_id_recipes", "menu_items", type_="foreignkey")
