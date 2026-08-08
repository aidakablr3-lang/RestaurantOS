"""Pydantic request/response schemas for Branch CRUD.

``AddressRequestSchema``'s fields are all optional, matching Address's
own domain-level nullability (Architecture SS3.1: "a Branch can exist
with a placeholder address during setup").
"""

from __future__ import annotations

from datetime import datetime

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


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


class UpdateBranchRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    address: AddressRequestSchema | None = None


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
