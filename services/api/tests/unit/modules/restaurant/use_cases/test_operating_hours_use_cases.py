"""Unit tests for ReplaceOperatingHoursUseCase (Sprint 5 Step 4.3) --
in-memory fakes, no network/DB access.

Covers per-row validation (day range, closed/open+times consistency,
overnight windows), cross-row conflicts (closed+open same day,
duplicate closed rows, overlapping open periods), legitimate split
shifts, full replace semantics, and branch-not-found/cross-tenant
behavior.
"""

from __future__ import annotations

from datetime import UTC, datetime, time

import pytest

from restaurant_os_api.modules.restaurant.application.dto import (
    OperatingHoursEntryRequestDTO,
    ReplaceOperatingHoursRequestDTO,
)
from restaurant_os_api.modules.restaurant.application.use_cases import (
    ReplaceOperatingHoursUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    OperatingHours,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    BranchNotFoundError,
    OperatingHoursConflictError,
)
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    InMemoryBranchRepository,
    InMemoryOperatingHoursRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
        "address_id": None,
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


def _use_case(
    branch_repo: InMemoryBranchRepository, operating_hours_repo: InMemoryOperatingHoursRepository
) -> ReplaceOperatingHoursUseCase:
    return ReplaceOperatingHoursUseCase(
        session_factory=_session_factory(),
        branch_repository_factory=lambda _s: branch_repo,
        operating_hours_repository_factory=lambda _s: operating_hours_repo,
    )


class TestReplaceOperatingHoursUseCase:
    async def test_replaces_and_returns_the_new_entries(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=1,
                        is_closed=False,
                        opens_at=time(9, 0),
                        closes_at=time(17, 0),
                    )
                ],
            ),
        )

        assert len(result) == 1
        assert result[0].day_of_week == 1
        assert result[0].opens_at == time(9, 0)
        stored = await operating_hours_repo.list_for_branch(TENANT_ID, BRANCH_ID)
        assert len(stored) == 1

    async def test_replace_overwrites_whatever_existed_before(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        existing = [
            OperatingHours(
                id="01ARZ3NDEKTSV4RRFFQ6OPHR99",
                tenant_id=TENANT_ID,
                branch_id=BRANCH_ID,
                day_of_week=5,
                is_closed=True,
                created_at=datetime.now(UTC),
            )
        ]
        operating_hours_repo = InMemoryOperatingHoursRepository({BRANCH_ID: existing})
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=2,
                        is_closed=False,
                        opens_at=time(8, 0),
                        closes_at=time(12, 0),
                    )
                ],
            ),
        )

        assert len(result) == 1
        assert result[0].day_of_week == 2
        stored = await operating_hours_repo.list_for_branch(TENANT_ID, BRANCH_ID)
        assert len(stored) == 1
        assert stored[0].day_of_week == 2

    async def test_replacing_with_an_empty_list_clears_all_hours(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        existing = [
            OperatingHours(
                id="01ARZ3NDEKTSV4RRFFQ6OPHR99",
                tenant_id=TENANT_ID,
                branch_id=BRANCH_ID,
                day_of_week=5,
                is_closed=True,
                created_at=datetime.now(UTC),
            )
        ]
        operating_hours_repo = InMemoryOperatingHoursRepository({BRANCH_ID: existing})
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID, ReplaceOperatingHoursRequestDTO(branch_id=BRANCH_ID, entries=[])
        )

        assert result == []
        stored = await operating_hours_repo.list_for_branch(TENANT_ID, BRANCH_ID)
        assert stored == []

    async def test_split_shifts_two_non_overlapping_open_periods_same_day_succeed(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(11, 0),
                        closes_at=time(14, 0),
                    ),
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(17, 0),
                        closes_at=time(22, 0),
                    ),
                ],
            ),
        )

        assert len(result) == 2

    async def test_returned_entries_are_ordered_by_day_regardless_of_submission_order(
        self,
    ) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(day_of_week=5, is_closed=True),
                    OperatingHoursEntryRequestDTO(day_of_week=1, is_closed=True),
                    OperatingHoursEntryRequestDTO(day_of_week=3, is_closed=True),
                ],
            ),
        )

        assert [e.day_of_week for e in result] == [1, 3, 5]

    async def test_split_shift_entries_for_the_same_day_are_ordered_by_opens_at(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(17, 0),
                        closes_at=time(22, 0),
                    ),
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(11, 0),
                        closes_at=time(14, 0),
                    ),
                ],
            ),
        )

        assert [e.opens_at for e in result] == [time(11, 0), time(17, 0)]

    async def test_raises_not_found_for_an_unknown_branch(self) -> None:
        use_case = _use_case(InMemoryBranchRepository(), InMemoryOperatingHoursRepository())

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID, ReplaceOperatingHoursRequestDTO(branch_id=BRANCH_ID, entries=[])
            )

    async def test_raises_not_found_for_a_cross_tenant_branch(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch(tenant_id=OTHER_TENANT_ID)})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(BranchNotFoundError):
            await use_case.execute(
                TENANT_ID, ReplaceOperatingHoursRequestDTO(branch_id=BRANCH_ID, entries=[])
            )

    async def test_rejects_a_day_of_week_out_of_range(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[OperatingHoursEntryRequestDTO(day_of_week=7, is_closed=True)],
                ),
            )

    async def test_rejects_an_open_entry_missing_times(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[OperatingHoursEntryRequestDTO(day_of_week=1, is_closed=False)],
                ),
            )

    async def test_rejects_opens_at_equal_to_closes_at(self) -> None:
        # The one input that's still genuinely invalid for an open entry:
        # a zero-length window, regardless of the time of day chosen.
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[
                        OperatingHoursEntryRequestDTO(
                            day_of_week=1,
                            is_closed=False,
                            opens_at=time(10, 0),
                            closes_at=time(10, 0),
                        )
                    ],
                ),
            )

    async def test_accepts_an_overnight_window_closing_after_midnight(self) -> None:
        # opens_at > closes_at used to be rejected outright -- it's now a
        # legitimate overnight window, closing the following calendar day
        # (any bar/pub open past midnight needs exactly this shape).
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=1,
                        is_closed=False,
                        opens_at=time(12, 30),
                        closes_at=time(0, 30),
                    )
                ],
            ),
        )

        assert result[0].opens_at == time(12, 30)
        assert result[0].closes_at == time(0, 30)

    async def test_accepts_an_overnight_window_opening_in_the_evening(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=1,
                        is_closed=False,
                        opens_at=time(18, 0),
                        closes_at=time(2, 0),
                    )
                ],
            ),
        )

        assert result[0].opens_at == time(18, 0)
        assert result[0].closes_at == time(2, 0)

    async def test_rejects_a_closed_and_open_entry_for_the_same_day(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[
                        OperatingHoursEntryRequestDTO(day_of_week=2, is_closed=True),
                        OperatingHoursEntryRequestDTO(
                            day_of_week=2,
                            is_closed=False,
                            opens_at=time(9, 0),
                            closes_at=time(17, 0),
                        ),
                    ],
                ),
            )

    async def test_rejects_more_than_one_closed_entry_for_the_same_day(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[
                        OperatingHoursEntryRequestDTO(day_of_week=4, is_closed=True),
                        OperatingHoursEntryRequestDTO(day_of_week=4, is_closed=True),
                    ],
                ),
            )

    async def test_rejects_two_overlapping_open_periods_same_day(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        with pytest.raises(OperatingHoursConflictError):
            await use_case.execute(
                TENANT_ID,
                ReplaceOperatingHoursRequestDTO(
                    branch_id=BRANCH_ID,
                    entries=[
                        OperatingHoursEntryRequestDTO(
                            day_of_week=3,
                            is_closed=False,
                            opens_at=time(9, 0),
                            closes_at=time(15, 0),
                        ),
                        OperatingHoursEntryRequestDTO(
                            day_of_week=3,
                            is_closed=False,
                            opens_at=time(14, 0),
                            closes_at=time(22, 0),
                        ),
                    ],
                ),
            )

    async def test_back_to_back_periods_touching_at_the_boundary_do_not_overlap(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        operating_hours_repo = InMemoryOperatingHoursRepository()
        use_case = _use_case(branch_repo, operating_hours_repo)

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(9, 0),
                        closes_at=time(14, 0),
                    ),
                    OperatingHoursEntryRequestDTO(
                        day_of_week=3,
                        is_closed=False,
                        opens_at=time(14, 0),
                        closes_at=time(22, 0),
                    ),
                ],
            ),
        )

        assert len(result) == 2

    async def test_validation_errors_are_scoped_to_their_own_day_independently(self) -> None:
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = _use_case(branch_repo, InMemoryOperatingHoursRepository())

        result = await use_case.execute(
            TENANT_ID,
            ReplaceOperatingHoursRequestDTO(
                branch_id=BRANCH_ID,
                entries=[
                    OperatingHoursEntryRequestDTO(day_of_week=0, is_closed=True),
                    OperatingHoursEntryRequestDTO(
                        day_of_week=1,
                        is_closed=False,
                        opens_at=time(9, 0),
                        closes_at=time(17, 0),
                    ),
                ],
            ),
        )

        assert {e.day_of_week for e in result} == {0, 1}
