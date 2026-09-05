"""Pydantic request/response schemas for the menu-import feature.

The extract endpoint takes multipart file uploads, not a JSON body, so
there is no request schema for it -- only a response schema (the
extracted rows). The commit endpoint takes the final, reviewed row list
as JSON, so it has both.
"""

from __future__ import annotations

from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class ExtractedMenuRowResponseSchema(CamelModel):
    category: str
    name: str
    raw_price: str
    price_amount: Decimal | None
    confidence: str
    source_image_index: int | None
    dietary_type: str | None
    portion_label: str | None
    pricing_unit: str | None
    note: str | None


class MenuImportExtractResponseSchema(CamelModel):
    rows: list[ExtractedMenuRowResponseSchema]


class MenuImportCommitRowRequestSchema(CamelModel):
    category: str = Field(..., min_length=1, max_length=255)
    name: str = Field(..., min_length=1, max_length=255)
    price_amount: Decimal = Field(..., gt=0)
    portion_label: str | None = Field(default=None, max_length=100)


class CommitMenuImportRequestSchema(CamelModel):
    rows: list[MenuImportCommitRowRequestSchema] = Field(..., min_length=1)


class CommitMenuImportResultResponseSchema(CamelModel):
    categories_created: int
    items_created: int
