"""Unit tests for indian_financial_year -- pure function, no I/O."""

from __future__ import annotations

from datetime import UTC, datetime

from restaurant_os_api.platform.financial_year import indian_financial_year


def test_late_march_utc_that_is_already_april_in_ist_lands_in_the_next_fy() -> None:
    # The exact regression case: 2026-03-31 23:00 UTC is 2026-04-01
    # 04:30 IST -- already FY 2026-27, not FY 2025-26 as a naive
    # UTC-only month check would conclude.
    at = datetime(2026, 3, 31, 23, 0, tzinfo=UTC)
    assert indian_financial_year(at) == "2026-27"


def test_late_march_utc_that_is_still_march_in_ist_stays_in_the_prior_fy() -> None:
    # Same UTC date, earlier in the day -- 2026-03-31 10:00 UTC is
    # 2026-03-31 15:30 IST, still March.
    at = datetime(2026, 3, 31, 10, 0, tzinfo=UTC)
    assert indian_financial_year(at) == "2025-26"


def test_april_first_utc_is_unambiguously_the_new_fy() -> None:
    at = datetime(2026, 4, 1, 0, 0, tzinfo=UTC)
    assert indian_financial_year(at) == "2026-27"


def test_mid_year_dates_map_to_the_fy_they_started_in() -> None:
    assert indian_financial_year(datetime(2026, 6, 15, tzinfo=UTC)) == "2026-27"
    assert indian_financial_year(datetime(2027, 1, 15, tzinfo=UTC)) == "2026-27"
    assert indian_financial_year(datetime(2027, 3, 15, tzinfo=UTC)) == "2026-27"
