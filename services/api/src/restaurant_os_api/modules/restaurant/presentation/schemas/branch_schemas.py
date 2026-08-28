"""Pydantic request/response schemas for Branch CRUD.

``AddressRequestSchema``'s fields are all optional, matching Address's
own domain-level nullability (Architecture SS3.1: "a Branch can exist
with a placeholder address during setup").
"""

from __future__ import annotations

import re
from datetime import datetime

from pydantic import Field, field_validator

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.restaurant.presentation.schemas.operating_hours_schemas import (
    OperatingHoursEntryResponseSchema,
)

# 2-digit state code + 10-char PAN (5 letters, 4 digits, 1 letter) +
# 1 entity-count char + literal 'Z' + 1 checksum char = 15. Format only
# -- the checksum digit itself is not verified.
_GSTIN_PATTERN = re.compile(r"^[0-9]{2}[A-Z]{5}[0-9]{4}[A-Z][1-9A-Z]Z[0-9A-Z]$")


def _validate_gstin(value: str | None) -> str | None:
    if value is not None and not _GSTIN_PATTERN.match(value):
        raise ValueError(
            "GSTIN must be 15 characters: 2-digit state code, 10-character PAN, "
            "1 entity-count character, 'Z', 1 checksum character."
        )
    return value


class AddressRequestSchema(CamelModel):
    # No length/format constraints beyond the DB's own ("Constraints:
    # None beyond types", Architecture SS3.1) -- postal/country code
    # formats vary too widely internationally to invent a bound here.
    line1: str | None = None
    city: str | None = None
    country_code: str | None = None
    postal_code: str | None = None


class CreateBranchRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: AddressRequestSchema | None = None
    gstin: str | None = None

    _validate_gstin = field_validator("gstin")(_validate_gstin)


class UpdateBranchRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: AddressRequestSchema | None = None
    gstin: str | None = None

    _validate_gstin = field_validator("gstin")(_validate_gstin)


class AddressResponseSchema(CamelModel):
    id: str
    line1: str | None
    city: str | None
    country_code: str | None
    postal_code: str | None


class BranchResponseSchema(CamelModel):
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    status: str
    address: AddressResponseSchema | None
    created_at: datetime
    gstin: str | None = None


class BranchDetailResponseSchema(CamelModel):
    """``BranchResponseSchema`` plus nested operating hours -- only
    ``GET /api/v1/branches/{id}`` returns this shape (Step 4.3);
    create/update/close/reopen return the plain ``BranchResponseSchema``
    unchanged."""

    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    status: str
    address: AddressResponseSchema | None
    created_at: datetime
    operating_hours: list[OperatingHoursEntryResponseSchema]
    gstin: str | None = None
