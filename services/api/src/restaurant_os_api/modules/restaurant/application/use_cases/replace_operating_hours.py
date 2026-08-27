"""ReplaceOperatingHoursUseCase.

Restaurant Platform Architecture SS7's ``PUT /api/v1/branches/{id}/
operating-hours`` -- a full-week replace, not per-day CRUD (the
architecture's own words: "Full-week replace, not per-day PATCH"),
matching ``OperatingHoursRepository.replace_for_branch``'s already-built
shape (Step 3) exactly: the entire submitted list overwrites whatever
existed before, in one call.

Per-row shape (day range, closed/open+times consistency) is validated
at the presentation schema layer (Pydantic, 422) -- the same layering
``CreateRestaurantRequestSchema`` already uses for its own field
constraints. What only this use case can check is *cross-row*
consistency for the same ``day_of_week`` (Architecture SS3.1: "overlap
validation is an application-layer concern, not a schema constraint"):

1. An explicit ``is_closed`` row is exclusive for its day -- mixing a
   "closed all day" row with an "open" row for the same day is a
   direct self-contradiction, not a legitimate split shift.
2. Two open periods for the same day (legitimate split shifts, per
   Architecture SS3.1's own example) must not overlap.

No domain event is published for this operation: Architecture SS11's
event catalogue does not list one for ``OperatingHours`` (unlike
``Branch``, which already had `Updated`/`Closed`/`Reopened` events this
sprint extended `Restaurant` to match), and there is no equally direct
sibling-entity precedent here to extend from -- disclosed as a known
gap rather than silently inventing an event type architecture never
named.

Overnight windows (``closes_at < opens_at``, e.g. opens 22:00 closes
02:00) are accepted as closing on the *following* calendar day -- the
only genuinely invalid same-day-open input is ``opens_at ==
closes_at``. No 24-hour or timezone-conversion behavior is
implemented; neither is named anywhere in SS3.1's `OperatingHours`
entry.

Known, disclosed gap: the overlap check below (``sorted_open`` +
``pairwise``) only compares entries *within the same
``day_of_week``*. It has no way to detect an overnight entry's
spillover into the next day's own early-morning row (e.g. Friday
22:00-02:00 stored on ``day_of_week=5`` isn't compared against a
Saturday 01:00-06:00 row stored on ``day_of_week=6``, even though
those two windows do overlap in real time). This was already the
day-siloed shape of this check before overnight windows were allowed;
allowing overnight now makes that pre-existing limitation reachable.
Cross-day overlap detection would need entries compared as real
instants, not per-day time-of-day values -- deferred as a separate
piece of work, not silently built here.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, time
from itertools import pairwise

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.application.dto import (
    OperatingHoursEntryDTO,
    OperatingHoursEntryRequestDTO,
    ReplaceOperatingHoursRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases._operating_hours_mapper import (
    operating_hours_to_dto,
)
from restaurant_os_api.modules.restaurant.domain.entities import OperatingHours
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    OperatingHoursConflictError,
)
from restaurant_os_api.modules.restaurant.domain.ports import (
    BranchRepository,
    OperatingHoursRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext


def _validate_no_conflicts(entries: list[OperatingHoursEntryRequestDTO]) -> None:
    # Defensive: the presentation schema layer already enforces this
    # per-row (day range, closed/open+times consistency, opens < closes)
    # before a request ever reaches this use case, but this use case is
    # also called directly from unit tests and is the actual business
    # boundary -- it must not trust that upstream layer blindly.
    for entry in entries:
        if not (0 <= entry.day_of_week <= 6):
            raise OperatingHoursConflictError(entry.day_of_week, "day_of_week must be 0-6")
        if not entry.is_closed:
            if entry.opens_at is None or entry.closes_at is None:
                raise OperatingHoursConflictError(
                    entry.day_of_week, "an open entry requires both opens_at and closes_at"
                )
            if entry.opens_at == entry.closes_at:
                raise OperatingHoursConflictError(
                    entry.day_of_week, "opening and closing time cannot be the same"
                )

    by_day: dict[int, list[OperatingHoursEntryRequestDTO]] = {}
    for entry in entries:
        by_day.setdefault(entry.day_of_week, []).append(entry)

    for day_of_week, day_entries in by_day.items():
        closed_rows = [e for e in day_entries if e.is_closed]
        open_rows = [e for e in day_entries if not e.is_closed]

        if closed_rows and open_rows:
            raise OperatingHoursConflictError(
                day_of_week, "a 'closed all day' entry cannot coexist with an open period"
            )
        if len(closed_rows) > 1:
            raise OperatingHoursConflictError(
                day_of_week, "more than one 'closed all day' entry was submitted"
            )

        sorted_open = sorted(open_rows, key=lambda e: e.opens_at)  # type: ignore[arg-type, return-value]
        for earlier, later in pairwise(sorted_open):
            assert earlier.closes_at is not None and later.opens_at is not None  # validated above
            if earlier.closes_at > later.opens_at:
                raise OperatingHoursConflictError(day_of_week, "two open periods overlap")


class ReplaceOperatingHoursUseCase:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        branch_repository_factory: Callable[[AsyncSession], BranchRepository],
        operating_hours_repository_factory: Callable[[AsyncSession], OperatingHoursRepository],
    ) -> None:
        self._session_factory = session_factory
        self._branch_repository_factory = branch_repository_factory
        self._operating_hours_repository_factory = operating_hours_repository_factory

    async def execute(
        self, tenant_id: str, request: ReplaceOperatingHoursRequestDTO
    ) -> list[OperatingHoursEntryDTO]:
        _validate_no_conflicts(request.entries)

        now = datetime.now(UTC)
        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            branch_repo = self._branch_repository_factory(uow.session)
            operating_hours_repo = self._operating_hours_repository_factory(uow.session)

            branch = await branch_repo.get_by_id(tenant_id, request.branch_id)
            if branch is None:
                raise BranchNotFoundError(request.branch_id)

            rows = [
                OperatingHours(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    branch_id=request.branch_id,
                    day_of_week=entry.day_of_week,
                    is_closed=entry.is_closed,
                    created_at=now,
                    opens_at=entry.opens_at,
                    closes_at=entry.closes_at,
                )
                for entry in request.entries
            ]
            await operating_hours_repo.replace_for_branch(tenant_id, request.branch_id, rows)

        # Mirrors `OperatingHoursRepository.list_for_branch`'s own `ORDER BY
        # day_of_week` exactly, so a PUT's response and a subsequent GET's
        # nested `operatingHours` array are never observably different
        # orderings of the same data. `opens_at` is the tiebreaker for split
        # shifts sharing a day (a closed row never coexists with an open row
        # for the same day -- `_validate_no_conflicts` rejects that -- so
        # `time.min` for closed rows never collides with a real opens_at).
        ordered_rows = sorted(rows, key=lambda r: (r.day_of_week, r.opens_at or time.min))
        return [operating_hours_to_dto(row) for row in ordered_rows]
