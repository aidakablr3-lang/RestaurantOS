"""Application-layer DTOs for Restaurant CRUD.

Technical Architecture v2.0 SS5.6: distinct from the presentation
layer's Pydantic schemas, matching ``modules.identity.application.dto.
tenant_dto``'s exact convention -- a use case's unit tests never need
FastAPI/Pydantic installed.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateRestaurantRequestDTO:
    legal_name: str
    display_name: str
    default_currency_code: str


@dataclass(frozen=True, slots=True)
class UpdateRestaurantRequestDTO:
    restaurant_id: str
    legal_name: str
    display_name: str
    default_currency_code: str


@dataclass(frozen=True, slots=True)
class RestaurantDTO:
    id: str
    tenant_id: str
    legal_name: str
    display_name: str
    default_currency_code: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class RestaurantListResultDTO:
    restaurants: list[RestaurantDTO]
    total: int
    offset: int
    limit: int
