"""kitchen_tickets/kitchen_items -- add a cancelled status

Revision ID: 0030
Revises: 0021
Create Date: 2026-09-08

Operational-gap fix: voiding a fired ``Order`` previously left any
already-created ``KitchenTicket`` sitting on the KDS in whatever status
it was in, with nothing telling the kitchen to stop. Adds
``cancelled`` to both tables' ``status`` CHECK constraint, plus
``kitchen_tickets.cancelled_at`` (nullable, application-set -- same
shape as ``orders.closed_at``) so the KDS can compute how long a
cancelled ticket has been visible on the board. ``kitchen_items`` gets
no equivalent timestamp column: an item is only ever viewed nested
under its parent ticket, so the ticket's own ``cancelled_at`` is the
only one the KDS needs.

down_revision is 0021, not a later migration some other in-flight
branch may have added -- this migration only depends on what's
actually merged. Numbered 0030 (not 0022) specifically to steer clear
of the concurrent ``rls/runtime-role-isolation`` branch's own
0020/0022-0027 revisions -- whichever branch merges second still has
to renumber its tail, but starting from a number well past that
range keeps this migration's own history stable regardless of merge
order.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0030"
down_revision: str | None = "0021"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_TICKET_CONSTRAINT = "ck_kitchen_tickets_status_is_valid"
_TICKET_CHECK = "status IN ('fired', 'in_progress', 'ready', 'served', 'cancelled')"
_TICKET_CHECK_OLD = "status IN ('fired', 'in_progress', 'ready', 'served')"

_ITEM_CONSTRAINT = "ck_kitchen_items_status_is_valid"
_ITEM_CHECK = "status IN ('queued', 'in_progress', 'ready', 'cancelled')"
_ITEM_CHECK_OLD = "status IN ('queued', 'in_progress', 'ready')"


def upgrade() -> None:
    op.add_column(
        "kitchen_tickets", sa.Column("cancelled_at", sa.TIMESTAMP(timezone=True), nullable=True)
    )

    op.drop_constraint(conv(_TICKET_CONSTRAINT), "kitchen_tickets", type_="check")
    op.create_check_constraint(conv(_TICKET_CONSTRAINT), "kitchen_tickets", _TICKET_CHECK)

    op.drop_constraint(conv(_ITEM_CONSTRAINT), "kitchen_items", type_="check")
    op.create_check_constraint(conv(_ITEM_CONSTRAINT), "kitchen_items", _ITEM_CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_ITEM_CONSTRAINT), "kitchen_items", type_="check")
    op.create_check_constraint(conv(_ITEM_CONSTRAINT), "kitchen_items", _ITEM_CHECK_OLD)

    op.drop_constraint(conv(_TICKET_CONSTRAINT), "kitchen_tickets", type_="check")
    op.create_check_constraint(conv(_TICKET_CONSTRAINT), "kitchen_tickets", _TICKET_CHECK_OLD)

    op.drop_column("kitchen_tickets", "cancelled_at")
