"""menu_items.station -- KDS station routing

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-12

Full-day operational simulation finding: ``FireOrderUseCase`` always
created exactly one ``KitchenTicket`` per order, station hardcoded to
``"kitchen"``, even though the ``KitchenTicket``/``KitchenItem`` schema
(migration ``0007``) already supports many tickets per order and
``fire_order.py``'s own docstring disclosed the missing piece: no
column anywhere records which station a given menu item actually
belongs to.

Purely additive: ``NOT NULL`` with ``server_default 'kitchen'`` so
every existing ``menu_items`` row (and any row inserted concurrently
with this migration) gets the same one-ticket-per-order behavior it
already had, zero backfill risk. The ``CHECK`` constraint mirrors the
enum-column precedent already used for ``kitchen_tickets.status`` etc.
(migration ``0007``) -- ``kitchen``/``bar`` matches this feature's own
name ("kitchen/bar station routing"); a station column, once it
exists, is cheap to extend with more values in a later migration if a
real per-station KDS (grill/cold/expo, per the product blueprint) is
ever built.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0009"
down_revision: str | None = "0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "menu_items",
        sa.Column(
            "station", sa.Text(), nullable=False, server_default=sa.text("'kitchen'")
        ),
    )
    # Both ``op.create_check_constraint`` and ``op.drop_constraint(...,
    # type_="check")`` re-run the ``ck`` naming convention
    # (``ck_%(table_name)s_%(constraint_name)s``) over whatever name is
    # given here -- unlike ``sa.CheckConstraint(name=conv(...))`` inside
    # ``op.create_table``, wrapping this in ``conv()`` does not suppress
    # that. Passing just the suffix (not the full ``ck_menu_items_...``
    # name) on both sides lets the convention build the identical final
    # name -- ``ck_menu_items_station_is_valid`` -- consistently.
    op.create_check_constraint(
        "station_is_valid",
        "menu_items",
        "station IN ('kitchen', 'bar')",
    )


def downgrade() -> None:
    op.drop_constraint("station_is_valid", "menu_items", type_="check")
    op.drop_column("menu_items", "station")
