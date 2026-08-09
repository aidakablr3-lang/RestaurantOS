"""Reusable effective-window overlap check -- migration 0005's own
docstring (Step 4 Decision Lock) commits to this exact "friendly
pre-check" for both ``MenuItemBranchPrice`` and ``MenuItemAvailability``,
in front of the GiST ``EXCLUDE`` constraint that is each table's real,
race-free guarantee. Generalized here, not duplicated per entity, the
same shape ``resolve_and_authorize_branch`` already established for a
concern shared by both entities' create use cases.

Mirrors the constraint's own semantics exactly: two
``[effective_from, effective_to)`` windows overlap if each starts
before the other ends, treating a ``None`` (open-ended) ``effective_to``
as unbounded -- the same ``tstzrange(..., '[)')`` interpretation
Postgres's ``btree_gist`` applies.
"""

from __future__ import annotations

from datetime import datetime


def windows_overlap(
    a_from: datetime,
    a_to: datetime | None,
    b_from: datetime,
    b_to: datetime | None,
) -> bool:
    a_starts_before_b_ends = b_to is None or a_from < b_to
    b_starts_before_a_ends = a_to is None or b_from < a_to
    return a_starts_before_b_ends and b_starts_before_a_ends
