"""Repository port for MenuItemModifierGroup."""

from __future__ import annotations

from typing import Protocol


class MenuItemModifierGroupRepository(Protocol):
    async def list_modifier_group_ids_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> frozenset[str]: ...

    async def replace_for_menu_item(
        self, tenant_id: str, menu_item_id: str, modifier_group_ids: frozenset[str]
    ) -> None:
        """Atomically replace a menu item's full modifier-group set --
        backs ``PUT /menu-items/{id}/modifier-groups`` (Restaurant
        Platform Architecture SS7), which replaces rather than
        incrementally patches (matching
        ``RolePermissionRepository.replace_for_role``'s own pattern)."""
        ...
