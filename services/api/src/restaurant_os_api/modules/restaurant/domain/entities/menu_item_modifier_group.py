"""MenuItemModifierGroup entity.

Restaurant Platform Architecture SS3.1: the join resolving
``MenuItem``<->``ModifierGroup``'s many-to-many (Data Architecture v2.0
Group F). A pure association row -- no independent audit weight, no
lifecycle methods, matching ``RolePermission``'s own classification in
the RBAC module.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(slots=True)
class MenuItemModifierGroup:
    id: str
    tenant_id: str
    menu_item_id: str
    modifier_group_id: str
    created_at: datetime
