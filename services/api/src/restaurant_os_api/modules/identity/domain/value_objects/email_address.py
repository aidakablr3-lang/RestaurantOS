"""Email address value object.

A minimal, dependency-free RFC-5322-adjacent validator. It intentionally
does not attempt full RFC 5322 compliance (that grammar accepts many
addresses no real mail provider does) — it rejects the classes of input
that would otherwise reach the database and violate the CITEXT uniqueness
constraint's expectations (Data Architecture v2.0 SS5.3).
"""

from __future__ import annotations

import re
from dataclasses import dataclass

from restaurant_os_api.modules.identity.domain.exceptions import (
    InvalidEmailAddressError,
)

_EMAIL_PATTERN = re.compile(
    r"^[a-zA-Z0-9.!#$%&'*+/=?^_`{|}~-]+"
    r"@[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?"
    r"(?:\.[a-zA-Z0-9](?:[a-zA-Z0-9-]{0,61}[a-zA-Z0-9])?)+$"
)


@dataclass(frozen=True, slots=True)
class EmailAddress:
    """An email address, normalized to lowercase at construction time.

    Normalizing here — once, at the domain boundary — is what lets the
    database's CITEXT column and this value object's equality agree on
    what "the same address" means, rather than relying on every call site
    to remember to lowercase input before comparing.
    """

    value: str

    def __post_init__(self) -> None:
        if not _EMAIL_PATTERN.match(self.value):
            raise InvalidEmailAddressError(self.value)
        object.__setattr__(self, "value", self.value.lower())

    def __str__(self) -> str:
        return self.value
