"""Identifier generation.

Data Architecture v2.0 ADR-D1 / Group H: primary keys are ULIDs, stored
as ``TEXT`` with a Crockford Base32 ``CHECK`` constraint (never
PostgreSQL's ``CHAR(n)`` — see Group H's rationale). This module is the
single place a ULID is minted, so every entity's ID has identical
format guarantees.
"""

from __future__ import annotations

import secrets

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


def generate_qr_token() -> str:
    """Return a new, cryptographically random, non-sequential opaque
    token for ``QRCode.token``.

    Deliberately **not** a ULID -- ADR 0001 requires this value resist
    guessing, and a ULID is time-ordered and partially predictable by
    design (correct for a primary key, wrong for a value a leaked/
    scanned QR code exposes). ``secrets.token_urlsafe`` is the
    standard library's own CSPRNG-backed generator for exactly this
    purpose; 32 bytes (256 bits) of entropy, URL-safe so it can be
    embedded directly in the future guest-resolution URL without
    additional encoding.
    """
    return secrets.token_urlsafe(32)
