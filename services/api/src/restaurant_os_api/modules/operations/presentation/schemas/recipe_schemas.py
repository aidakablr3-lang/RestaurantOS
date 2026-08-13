"""Pydantic request/response schemas for Recipe + RecipeIngredient
(Sprint 7 Step 5)."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class ReviseRecipeIngredientRequestSchema(CamelModel):
    inventory_item_id: str = Field(..., min_length=26, max_length=26)
    quantity: Decimal = Field(..., gt=0)
    unit: str = Field(..., min_length=1, max_length=50)


class ReviseRecipeRequestSchema(CamelModel):
    name: str = Field(..., min_length=1, max_length=255)
    ingredients: list[ReviseRecipeIngredientRequestSchema] = Field(default_factory=list)


class RecipeIngredientResponseSchema(CamelModel):
    id: str
    recipe_id: str
    inventory_item_id: str
    quantity: Decimal
    unit: str
    created_at: datetime


class RecipeResponseSchema(CamelModel):
    id: str
    tenant_id: str
    name: str
    version: int
    created_at: datetime
    superseded_by_id: str | None
    ingredients: list[RecipeIngredientResponseSchema]
