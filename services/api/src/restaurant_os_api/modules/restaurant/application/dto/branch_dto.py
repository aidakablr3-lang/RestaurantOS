"""Application-layer DTOs for Branch CRUD.

Address is a nested, optional sub-object on both create and update --
matching Architecture SS3.1's own "a Branch can exist with a
placeholder address during setup" principle (every Address field is
individually nullable) and SS8's Branch Details screen, which edits
"address, hours, status" together as one unit, not as separate API
calls. ``address=None`` on update leaves the branch's existing address
relationship untouched (create-or-update, never implicitly clears it)
-- a nested sub-resource omitted from a PATCH body should not be read
as "delete this."
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from restaurant_os_api.modules.restaurant.application.dto.operating_hours_dto import (
    OperatingHoursEntryDTO,
)


@dataclass(frozen=True, slots=True)
class AddressRequestDTO:
    line1: str | None = None
    city: str | None = None
    country_code: str | None = None
    postal_code: str | None = None


@dataclass(frozen=True, slots=True)
class CreateBranchRequestDTO:
    restaurant_id: str
    name: str
    address: AddressRequestDTO | None = None


@dataclass(frozen=True, slots=True)
class UpdateBranchRequestDTO:
    branch_id: str
    name: str
    address: AddressRequestDTO | None = None


@dataclass(frozen=True, slots=True)
class AddressDTO:
    id: str
    line1: str | None
    city: str | None
    country_code: str | None
    postal_code: str | None


@dataclass(frozen=True, slots=True)
class BranchDTO:
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    status: str
    address: AddressDTO | None
    created_at: datetime


@dataclass(frozen=True, slots=True)
class BranchDetailDTO:
    """``BranchDTO`` plus its operating hours -- ``GetBranchUseCase``'s
    own return type only (Step 4.3). Not used by create/update/close/
    reopen, which never load operating hours and would otherwise return
    a misleadingly-empty list for a branch that already has real ones
    set. Architecture SS7 defines no dedicated ``GET .../operating-hours``
    endpoint; SS8's Branch Details screen shows "Branch + Address +
    OperatingHours" as one nested view, which is what this DTO backs."""

    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    status: str
    address: AddressDTO | None
    created_at: datetime
    operating_hours: list[OperatingHoursEntryDTO]


@dataclass(frozen=True, slots=True)
class BranchListResultDTO:
    branches: list[BranchDTO]
    total: int
    offset: int
    limit: int
