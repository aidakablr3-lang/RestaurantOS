"""Pydantic request/response schemas for User endpoints.

Technical Architecture v2.0 SS5.6: parse -> call one use case -> shape
the response, no business logic here — matching every other schemas
module in this package exactly.
"""

from __future__ import annotations

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class CreateUserRequestSchema(CamelModel):
    email: str = Field(..., min_length=3, max_length=320)
    phone: str | None = Field(default=None, max_length=32)
    # Omit to have the server generate one, returned once in the
    # response (`generatedPassword`) -- see CreateUserUseCase's own
    # docstring. Accepting one here is for a caller who wants to relay
    # a specific credential (e.g. from an out-of-band conversation with
    # the new hire), not the default path.
    password: str | None = Field(default=None, min_length=8, max_length=255)


class UserResponseSchema(CamelModel):
    id: str
    tenant_id: str
    email: str | None
    phone: str | None
    status: str
    created_at: str
    generated_password: str | None = None
