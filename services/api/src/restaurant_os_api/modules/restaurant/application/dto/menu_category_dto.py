"""Application-layer DTOs for MenuCategory CRUD (Sprint 5 Step 4.8)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class CreateMenuCategoryRequestDTO:
    restaurant_id: str
    name: str
    display_order: int = 0


@dataclass(frozen=True, slots=True)
class UpdateMenuCategoryRequestDTO:
    menu_category_id: str
    restaurant_id: str
    name: str
    display_order: int


@dataclass(frozen=True, slots=True)
class MenuCategoryDTO:
    id: str
    tenant_id: str
    restaurant_id: str
    name: str
    display_order: int
    created_at: datetime


@dataclass(frozen=True, slots=True)
class MenuCategoryListResultDTO:
    menu_categories: list[MenuCategoryDTO]
    total: int
    offset: int
    limit: int
