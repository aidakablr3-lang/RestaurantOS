"""The standard API response envelope.

Technical Architecture v2.0 SS5.6: every response — success or error —
uses one envelope shape, so every client writes one parsing path. Field
names are camelCase on the wire (Pydantic's alias generator), while
Python code stays snake_case.
"""

from __future__ import annotations

from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

T = TypeVar("T")


class CamelModel(BaseModel):
    model_config = ConfigDict(alias_generator=to_camel, populate_by_name=True)


class ApiResponse(CamelModel, Generic[T]):  # noqa: UP046 -- Pydantic generic model support
    success: bool = True
    data: T


class ApiErrorDetail(CamelModel):
    code: str
    message: str


class ApiErrorResponse(CamelModel):
    success: bool = False
    error: ApiErrorDetail
