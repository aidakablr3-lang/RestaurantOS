"""Unit tests for parse_menu_price -- pure function, no fakes needed."""

from __future__ import annotations

from decimal import Decimal

import pytest

from restaurant_os_api.modules.restaurant.application.services.menu_import_price_parser import (
    parse_menu_price,
)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("90", Decimal("90.00")),
        ("90/-", Decimal("90.00")),
        ("90 /-", Decimal("90.00")),
        ("90/", Decimal("90.00")),
        ("₹90", Decimal("90.00")),
        ("₹ 90", Decimal("90.00")),
        ("₹90/-", Decimal("90.00")),
        ("Rs. 120", Decimal("120.00")),
        ("Rs 120", Decimal("120.00")),
        ("RS.120", Decimal("120.00")),
        ("INR 45.50", Decimal("45.50")),
        ("Re. 10", Decimal("10.00")),
        ("1,200", Decimal("1200.00")),
        ("₹1,200/-", Decimal("1200.00")),
        ("120.00", Decimal("120.00")),
        ("  90  ", Decimal("90.00")),
    ],
)
def test_parses_known_menu_price_formats(raw: str, expected: Decimal) -> None:
    assert parse_menu_price(raw) == expected


@pytest.mark.parametrize(
    "raw",
    [
        "90/150",  # two prices run together -- ambiguous, not "90 divided by 150"
        "market price",
        "",
        "₹",
        "90-120",
        "free",
    ],
)
def test_returns_none_for_unparseable_price_text(raw: str) -> None:
    assert parse_menu_price(raw) is None
