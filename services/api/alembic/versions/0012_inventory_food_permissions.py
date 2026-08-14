"""inventory_food.manage / inventory_food.read permissions

Revision ID: 0012
Revises: 0011
Create Date: 2026-08-14

Product decision (2026-08-14): food-inventory categories/items
(``inventory_categories.category_type = 'food'``, migration 0011)
need their own permission, separate from ``menu.manage``/``menu.read``.
The obvious reuse of those two codes doesn't work -- the real seeded
"Inventory Manager" role already holds them (needed for recipe editing,
which genuinely is part of that role), so gating food-inventory on
``menu.manage`` would restrict nothing for it in practice.

Grants the two new codes only to "Tenant Owner" and "Restaurant
Manager" -- the two default-catalogue roles the architecture doc's own
role table already treats as full menu owners -- explicitly NOT to
"Inventory Manager", which is the entire point of this change.
Backfills every already-provisioned tenant's existing ``is_system``
rows for those two role names (SS6.3's own disclosed convention: "new
permissions added by future modules do not automatically flow into
these role definitions... each future module's migration must
explicitly re-grant its permissions to the roles below"), in addition
to updating ``_DEFAULT_ROLE_CATALOGUE`` for tenants provisioned after
this migration.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from restaurant_os_api.core.ids import generate_ulid

revision: str = "0012"
down_revision: str | None = "0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_MODULE = "operations"
_NEW_PERMISSIONS: tuple[tuple[str, str], ...] = (
    ("inventory_food.manage", "Create, edit, and view food-category inventory items/categories."),
    ("inventory_food.read", "View food-category inventory items/categories."),
)
_GRANTED_ROLE_NAMES = ("Tenant Owner", "Restaurant Manager")


def upgrade() -> None:
    bind = op.get_bind()

    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.Text()),
        sa.column("module", sa.Text()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permissions_table,
        [{"code": code, "module": _MODULE, "description": desc} for code, desc in _NEW_PERMISSIONS],
    )

    role_ids = bind.execute(
        sa.text(
            "SELECT id FROM roles WHERE is_system = true AND name = ANY(:names)"
        ),
        {"names": list(_GRANTED_ROLE_NAMES)},
    ).scalars().all()

    role_permissions_table = sa.table(
        "role_permissions",
        sa.column("id", sa.Text()),
        sa.column("role_id", sa.Text()),
        sa.column("permission_code", sa.Text()),
    )
    new_grants = [
        {"id": generate_ulid(), "role_id": role_id, "permission_code": code}
        for role_id in role_ids
        for code, _desc in _NEW_PERMISSIONS
    ]
    if new_grants:
        op.bulk_insert(role_permissions_table, new_grants)


def downgrade() -> None:
    bind = op.get_bind()
    codes = [code for code, _desc in _NEW_PERMISSIONS]
    bind.execute(
        sa.text("DELETE FROM role_permissions WHERE permission_code = ANY(:codes)"),
        {"codes": codes},
    )
    bind.execute(
        sa.text("DELETE FROM permissions WHERE code = ANY(:codes)"),
        {"codes": codes},
    )
