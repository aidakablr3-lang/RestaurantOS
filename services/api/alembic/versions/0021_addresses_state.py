"""addresses.state -- Indian state/UT, enforced against a real list

Revision ID: 0021
Revises: 0019
Create Date: 2026-08-29

A printed GST tax invoice needs the branch's state (not just city and
postal code) -- required for the interstate-vs-intrastate CGST/SGST
split to even make sense on the document, and the GSTIN's own 2-digit
prefix is a state code, so a mismatched state is a real, silent data-
entry error otherwise. Nullable, matching every other Address field
(Restaurant Platform Architecture SS3.1: "a Branch can exist with a
placeholder address during setup").

The CHECK constraint enumerates real state/UT names rather than just
checking shape, the same "fixed set of allowed values" idiom migration
0015 used for tenants.default_currency_code (ISO 4217 membership).
The list below is a frozen literal snapshot of
platform/indian_states.py's INDIAN_STATE_GST_CODES keys as of this
migration's authoring -- deliberately NOT imported from that module,
for the same reason 0015 gives: a migration's behavior should not
silently change because application code was edited later.

down_revision is 0019, not a later migration some other in-flight
branch may have added -- this migration only depends on what's
actually merged.
"""

from __future__ import annotations

from collections.abc import Sequence

import sqlalchemy as sa
from sqlalchemy.sql.naming import conv

from alembic import op

revision: str = "0021"
down_revision: str | None = "0019"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

_CONSTRAINT_NAME = "state_is_a_real_indian_state_or_ut"

_CHECK = (
    "state IS NULL OR state IN ("
    "'Jammu and Kashmir', 'Himachal Pradesh', 'Punjab', 'Chandigarh', "
    "'Uttarakhand', 'Haryana', 'Delhi', 'Rajasthan', 'Uttar Pradesh', 'Bihar', "
    "'Sikkim', 'Arunachal Pradesh', 'Nagaland', 'Manipur', 'Mizoram', 'Tripura', "
    "'Meghalaya', 'Assam', 'West Bengal', 'Jharkhand', 'Odisha', 'Chhattisgarh', "
    "'Madhya Pradesh', 'Gujarat', 'Dadra and Nagar Haveli and Daman and Diu', "
    "'Maharashtra', 'Andhra Pradesh', 'Karnataka', 'Goa', 'Lakshadweep', "
    "'Kerala', 'Tamil Nadu', 'Puducherry', 'Andaman and Nicobar Islands', "
    "'Telangana', 'Ladakh')"
)


def upgrade() -> None:
    op.add_column("addresses", sa.Column("state", sa.Text(), nullable=True))
    op.create_check_constraint(conv(_CONSTRAINT_NAME), "addresses", _CHECK)


def downgrade() -> None:
    op.drop_constraint(conv(_CONSTRAINT_NAME), "addresses", type_="check")
    op.drop_column("addresses", "state")
