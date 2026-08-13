"""Shared Restaurant (domain entity) -> RestaurantDTO mapping.

Private to this package, matching ``modules.identity.application.
use_cases._tenant_mapper``'s exact convention -- every Restaurant CRUD
use case needs the identical mapping.
"""

from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import RestaurantDTO
from restaurant_os_api.modules.restaurant.domain.entities import Restaurant


def restaurant_to_dto(restaurant: Restaurant) -> RestaurantDTO:
    return RestaurantDTO(
        id=restaurant.id,
        tenant_id=restaurant.tenant_id,
        legal_name=restaurant.legal_name,
        display_name=restaurant.display_name,
        default_currency_code=restaurant.default_currency_code,
        status=restaurant.status.value,
        created_at=restaurant.created_at,
    )
