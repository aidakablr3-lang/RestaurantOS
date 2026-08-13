"""reports.read permission -- End-of-Day report (full-day operational
simulation gap fix)

Revision ID: 0010
Revises: 0009
Create Date: 2026-08-12

No report/summary/analytics feature existed anywhere in this codebase
before this. Adds exactly one new row to ``permissions`` following
migration 0007's own "seed data: new permissions (appended to the
existing table)" pattern -- ``role_permissions.permission_code`` has an
FK to ``permissions.code`` (migration 0003), so the code must exist
here before ``tenant_provisioning_service.py``'s ``_DEFAULT_ROLE_CATALOGUE``
can grant it to any role.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op

revision: str = "0010"
down_revision: str | None = "0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CODE = "reports.read"
_MODULE = "operations"
_DESCRIPTION = "View branch-level operational reports (e.g. the end-of-day summary)."


def upgrade() -> None:
    permissions_table = sa.table(
        "permissions",
        sa.column("code", sa.Text()),
        sa.column("module", sa.Text()),
        sa.column("description", sa.Text()),
    )
    op.bulk_insert(
        permissions_table,
        [{"code": _CODE, "module": _MODULE, "description": _DESCRIPTION}],
    )


def downgrade() -> None:
    op.execute(f"DELETE FROM permissions WHERE code = '{_CODE}'")
