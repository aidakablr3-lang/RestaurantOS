"""Pydantic request/response schemas for the auth endpoints.

Technical Architecture v2.0 SS5.6: the Presentation layer's only job is
parse -> call one use case -> shape the response. These schemas never
carry business logic.
"""

from __future__ import annotations

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class LoginRequestSchema(CamelModel):
    tenant_id: str = Field(..., min_length=26, max_length=26)
    email: str = Field(..., min_length=3, max_length=320)
    password: str = Field(..., min_length=1, max_length=512)
    device_id: str | None = Field(default=None, min_length=26, max_length=26)


class RefreshRequestSchema(CamelModel):
    tenant_id: str = Field(..., min_length=26, max_length=26)
    refresh_token: str = Field(..., min_length=1)
    device_id: str | None = Field(default=None, min_length=26, max_length=26)


class LogoutRequestSchema(CamelModel):
    tenant_id: str = Field(..., min_length=26, max_length=26)
    refresh_token: str = Field(..., min_length=1)


class TokenPairResponseSchema(CamelModel):
    access_token: str
    refresh_token: str
    token_type: str
    expires_in: int
