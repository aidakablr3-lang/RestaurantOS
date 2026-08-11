"""RecipeIngredient -- a static bill-of-materials row (Architecture doc
SS3.6). Plain value data, append-only in practice: a recipe revision
creates a wholly new set of rows tied to the new ``Recipe`` id rather
than mutating the old version's rows in place."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal


@dataclass(slots=True)
class RecipeIngredient:
    id: str
    tenant_id: str
    recipe_id: str
    inventory_item_id: str
    quantity: Decimal
    unit: str
    created_at: datetime
