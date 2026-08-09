"""Application-layer DTOs for the MenuItem<->ModifierGroup attachment
endpoint (Sprint 5 Step 4.9).

Restaurant Platform Architecture SS7's ``PUT /api/v1/menu-items/{id}/
modifier-groups`` -- full-set replace, not incremental patch, matching
``ReplaceRolePermissionsRequestDTO``'s own established shape for the
same "replace the whole set" semantics.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class ReplaceMenuItemModifierGroupsRequestDTO:
    menu_item_id: str
    modifier_group_ids: frozenset[str]


@dataclass(frozen=True, slots=True)
class MenuItemModifierGroupsDTO:
    menu_item_id: str
    modifier_group_ids: frozenset[str]
