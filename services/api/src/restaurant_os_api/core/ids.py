"""Identifier generation.

Data Architecture v2.0 ADR-D1 / Group H: primary keys are ULIDs, stored
as ``TEXT`` with a Crockford Base32 ``CHECK`` constraint (never
PostgreSQL's ``CHAR(n)`` — see Group H's rationale). This module is the
single place a ULID is minted, so every entity's ID has identical
format guarantees.
"""

from __future__ import annotations

from ulid import ULID

#: Matches the CHECK constraint applied to every primary/foreign key
#: column in the Alembic migration (Data Architecture v2.0 Group H.3).
ULID_PATTERN = r"^[0-9A-HJKMNP-TV-Z]{26}$"


def generate_ulid() -> str:
    """Return a new, lexicographically time-sortable ULID as a string.

    Safe to call on an offline client as well as the server — ULIDs
    require no coordination and no database round-trip to mint, which is
    exactly the property the local-first sync engine (Technical
    Architecture v2.0 Group A) depends on.
    """
    return str(ULID())
