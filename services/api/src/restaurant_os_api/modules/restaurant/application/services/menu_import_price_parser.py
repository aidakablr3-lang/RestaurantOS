"""Deterministic price-text normalization for the menu-import feature.

The vision/spreadsheet extraction step is deliberately told to hand back
the price exactly as printed -- "90/-", "₹90", "Rs. 120", "1,200" -- and
never to silently normalize it itself. Normalization happens here
instead, as a small pure function, so it's independently unit-testable
and auditable: a wrong regex is a one-line fix, a wrong LLM guess is not.

Returns ``None`` (never raises, never guesses) for anything that isn't
confidently a single price, so the caller can flag the row for manual
review with the raw text still visible rather than silently produce a
wrong number. In particular, "90/150" (two prices run together -- most
often a half/full pair that should have been split into two extraction
rows upstream, not a single "90 divided by 150") is deliberately left
unparsed rather than guessing which side is intended.
"""

from __future__ import annotations

import re
from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

_CURRENCY_PREFIX = re.compile(r"^(?:₹|rs\.?|inr|re\.?)\s*", re.IGNORECASE)
_TRAILING_SLASH_DASH = re.compile(r"\s*/-?\s*$")
_VALID_NUMBER = re.compile(r"\d+(?:\.\d{1,2})?")


def parse_menu_price(raw: str) -> Decimal | None:
    """Best-effort parse of a menu price exactly as printed.

    ``"₹90"``, ``"90/-"``, ``"Rs. 120"``, ``"INR 45.50"``, ``"1,200"`` all
    resolve to a plain two-decimal ``Decimal``. Returns ``None`` when the
    remaining text after stripping currency markers isn't a single valid
    number.
    """
    text = raw.strip()
    text = _CURRENCY_PREFIX.sub("", text)
    text = _TRAILING_SLASH_DASH.sub("", text)
    text = text.strip().replace(",", "")

    if not _VALID_NUMBER.fullmatch(text):
        return None

    try:
        return Decimal(text).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    except InvalidOperation:
        return None
