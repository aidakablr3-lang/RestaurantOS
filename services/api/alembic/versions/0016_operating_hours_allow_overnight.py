"""operating_hours: allow overnight windows (closes_at < opens_at)

Revision ID: 0016
Revises: 0015
Create Date: 2026-08-27

A branch could not enter genuine operating hours for any bar or pub
open past midnight -- ``opens_at < closes_at OR is_closed`` rejected
every overnight window (e.g. opens 22:00, closes 02:00) at the
Pydantic schema layer, the use-case layer, and here at the DB. The
schema and use-case layers now accept ``closes_at < opens_at`` as
closing on the *following* calendar day; this migration relaxes the
matching DB constraint to match. The only input this constraint (or
either app-layer check) still rejects for an open entry is
``opens_at == closes_at`` -- a zero-length window.

This is a pure relaxation (strictly a superset of what the old
constraint accepted), so unlike migration 0015's currency constraint
there is no pre-migration audit needed: no existing row could possibly
violate the new, looser check.

Renamed from ``opens_before_closes`` to ``opens_and_closes_are_distinct``
since "before" is no longer accurate -- an overnight row has
``opens_at`` numerically *after* ``closes_at``.
"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0016"
down_revision: str | None = "0015"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_OLD_NAME = "ck_operating_hours_opens_before_closes"
_NEW_NAME = "ck_operating_hours_opens_and_closes_are_distinct"

_OLD_CHECK = "opens_at < closes_at OR is_closed"
_NEW_CHECK = "opens_at <> closes_at OR is_closed"


def upgrade() -> None:
    op.drop_constraint(conv(_OLD_NAME), "operating_hours", type_="check")
    op.create_check_constraint(conv(_NEW_NAME), "operating_hours", _NEW_CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_NEW_NAME), "operating_hours", type_="check")
    op.create_check_constraint(conv(_OLD_NAME), "operating_hours", _OLD_CHECK)
