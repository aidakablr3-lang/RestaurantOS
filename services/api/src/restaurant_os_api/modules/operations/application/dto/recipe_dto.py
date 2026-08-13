"""Application-layer DTOs for Recipe + RecipeIngredient (Sprint 7 Step 5)."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal


@dataclass(frozen=True, slots=True)
class ReviseRecipeIngredientRequestDTO:
    inventory_item_id: str
    quantity: Decimal
    unit: str


@dataclass(frozen=True, slots=True)
class ReviseRecipeRequestDTO:
    menu_item_id: str
    name: str
    ingredients: list[ReviseRecipeIngredientRequestDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class RecipeIngredientDTO:
    id: str
    recipe_id: str
    inventory_item_id: str
    quantity: Decimal
    unit: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RecipeDTO:
    id: str
    tenant_id: str
    name: str
    version: int
    created_at: datetime
    superseded_by_id: str | None
    ingredients: list[RecipeIngredientDTO]
