"""Recipe entity -- versioned, never edited in place.

Architecture doc SS3.6: editing a recipe creates a *new* ``Recipe`` row
(``version`` incremented) and repoints ``MenuItem.recipe_id`` at it,
setting the old row's ``superseded_by_id`` -- so a historical
``OrderItem.recipe_cost_snapshot`` stays attributable to the exact
recipe version that was live when the order fired, even after the
recipe itself changes. ``ReviseRecipeUseCase`` is the only place that
creates a new version; this entity has no ``revise()`` method of its
own since revision requires allocating a *new* id, which belongs to
the use case (matching ``Bill``'s own "no self-replacing domain
method" shape).
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class Recipe:
    id: str
    tenant_id: str
    name: str
    version: int
    created_at: datetime
    superseded_by_id: str | None = None

    def mark_superseded(self, new_recipe_id: str) -> None:
        self.superseded_by_id = new_recipe_id
