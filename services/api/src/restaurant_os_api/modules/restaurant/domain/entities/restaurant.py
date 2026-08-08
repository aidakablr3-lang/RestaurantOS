"""Restaurant entity.

Restaurant Platform Architecture SS3.1: a tenant's named business
concept/brand. A tenant may operate more than one.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from enum import StrEnum

from restaurant_os_api.modules.restaurant.domain.exceptions import (
    InvalidRestaurantStatusTransitionError,
)


class RestaurantStatus(StrEnum):
    ACTIVE = "active"
    DISCONTINUED = "discontinued"


@dataclass(slots=True)
class Restaurant:
    id: str
    tenant_id: str
    legal_name: str
    display_name: str
    default_currency_code: str
    status: RestaurantStatus
    created_at: datetime

    def discontinue(self) -> None:
        """Mirrors ``Tenant``'s own status-enum pattern (SS3.1) -- a
        Restaurant doesn't need the full 5-state Tenant lifecycle, since
        it isn't a billing/infrastructure unit."""
        if self.status != RestaurantStatus.ACTIVE:
            raise InvalidRestaurantStatusTransitionError(
                self.id, self.status.value, RestaurantStatus.DISCONTINUED.value
            )
        self.status = RestaurantStatus.DISCONTINUED
