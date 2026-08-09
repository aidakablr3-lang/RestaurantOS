"""Pydantic request/response schemas for the MenuItem<->ModifierGroup
attachment endpoint (Sprint 5 Step 4.9).

``modifier_group_ids`` arrives as a JSON list (the wire format has no
native set type) and is converted to a ``frozenset`` in the router
before reaching the use case -- duplicate ids in the request body
collapse naturally rather than being rejected or double-inserted.
"""

from __future__ import annotations

from pydantic import Field

from restaurant_os_api.core.response import CamelModel


class ReplaceMenuItemModifierGroupsRequestSchema(CamelModel):
    modifier_group_ids: list[str] = Field(default_factory=list)


class MenuItemModifierGroupsResponseSchema(CamelModel):
    menu_item_id: str
    modifier_group_ids: list[str]
