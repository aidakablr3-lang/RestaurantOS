"""Indian financial year computation for invoice numbering.

India's financial year runs 1 April - 31 March, in IST (UTC+5:30), not
UTC. This codebase timestamps everything in UTC (``datetime.now(UTC)``
throughout) -- a bill generated at 2026-03-31 23:00 UTC is already
2026-04-01 04:30 IST, the *next* financial year, even though the
server's own clock still reads March. Converting to IST before
deciding the year is the whole point of this module; doing the
month/year check directly on a UTC timestamp would silently misnumber
every bill generated in the ~5.5-hour window around each FY boundary.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

IST = timezone(timedelta(hours=5, minutes=30))


def indian_financial_year(at: datetime) -> str:
    """``2026-03-31T23:00:00+00:00`` (UTC) -> ``"2026-27"`` (already
    IST 2026-04-01). Format is ``"{start}-{end % 100:02d}"``, the
    conventional Indian FY notation."""
    ist = at.astimezone(IST)
    if ist.month >= 4:
        start_year = ist.year
    else:
        start_year = ist.year - 1
    return f"{start_year}-{(start_year + 1) % 100:02d}"
