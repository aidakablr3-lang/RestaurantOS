"""Restaurant Platform domain events (Restaurant Platform Architecture SS11).

Framework-agnostic plain data (Technical Architecture v2.0 SS2.2: no
Infrastructure imports in Domain) — each satisfies the
``platform.events.DomainEvent`` structural contract, matching
``modules.identity.domain.events.tenant_events``'s exact convention.

Sprint 5 Step 3 is data-layer only: these are contracts, defined so the
repository layer's shape is complete, but nothing in this step
publishes them yet — that requires the use cases Step 4 (backend
domain & application services) builds. No new event mechanism, no
Redis Streams relay.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any, ClassVar


@dataclass(frozen=True, slots=True)
class RestaurantCreated:
    restaurant_id: str
    tenant_id: str
    legal_name: str
    display_name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "RestaurantCreated"
    aggregate_type: ClassVar[str] = "restaurant"

    @property
    def aggregate_id(self) -> str:
        return self.restaurant_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "restaurantId": self.restaurant_id,
            "tenantId": self.tenant_id,
            "legalName": self.legal_name,
            "displayName": self.display_name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BranchCreated:
    branch_id: str
    restaurant_id: str
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "BranchCreated"
    aggregate_type: ClassVar[str] = "branch"

    @property
    def aggregate_id(self) -> str:
        return self.branch_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "branchId": self.branch_id,
            "restaurantId": self.restaurant_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class BranchUpdated:
    branch_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "BranchUpdated"
    aggregate_type: ClassVar[str] = "branch"

    @property
    def aggregate_id(self) -> str:
        return self.branch_id

    def to_payload(self) -> dict[str, Any]:
        return {"branchId": self.branch_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class BranchClosed:
    branch_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "BranchClosed"
    aggregate_type: ClassVar[str] = "branch"

    @property
    def aggregate_id(self) -> str:
        return self.branch_id

    def to_payload(self) -> dict[str, Any]:
        return {"branchId": self.branch_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class BranchReopened:
    branch_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "BranchReopened"
    aggregate_type: ClassVar[str] = "branch"

    @property
    def aggregate_id(self) -> str:
        return self.branch_id

    def to_payload(self) -> dict[str, Any]:
        return {"branchId": self.branch_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class TableZoneCreated:
    table_zone_id: str
    branch_id: str
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TableZoneCreated"
    aggregate_type: ClassVar[str] = "table_zone"

    @property
    def aggregate_id(self) -> str:
        return self.table_zone_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "tableZoneId": self.table_zone_id,
            "branchId": self.branch_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TableCreated:
    table_id: str
    branch_id: str
    table_zone_id: str
    table_number: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TableCreated"
    aggregate_type: ClassVar[str] = "table"

    @property
    def aggregate_id(self) -> str:
        return self.table_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "tableId": self.table_id,
            "branchId": self.branch_id,
            "tableZoneId": self.table_zone_id,
            "tableNumber": self.table_number,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class TableUpdated:
    """Non-status edits (number, capacity, zone) -- see TableStatusChanged."""

    table_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TableUpdated"
    aggregate_type: ClassVar[str] = "table"

    @property
    def aggregate_id(self) -> str:
        return self.table_id

    def to_payload(self) -> dict[str, Any]:
        return {"tableId": self.table_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class TableStatusChanged:
    """Separate from TableUpdated because this is the one field a future
    consumer (WebSocket fan-out to a live floor-plan view) needs to
    subscribe to independently of everything else about the table."""

    table_id: str
    previous_status: str
    new_status: str
    occurred_at: datetime

    event_type: ClassVar[str] = "TableStatusChanged"
    aggregate_type: ClassVar[str] = "table"

    @property
    def aggregate_id(self) -> str:
        return self.table_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "tableId": self.table_id,
            "previousStatus": self.previous_status,
            "newStatus": self.new_status,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class QRCodeGenerated:
    qr_code_id: str
    table_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "QRCodeGenerated"
    aggregate_type: ClassVar[str] = "qr_code"

    @property
    def aggregate_id(self) -> str:
        return self.qr_code_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "qrCodeId": self.qr_code_id,
            "tableId": self.table_id,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class QRCodeRevoked:
    qr_code_id: str
    table_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "QRCodeRevoked"
    aggregate_type: ClassVar[str] = "qr_code"

    @property
    def aggregate_id(self) -> str:
        return self.qr_code_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "qrCodeId": self.qr_code_id,
            "tableId": self.table_id,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MenuCategoryCreated:
    menu_category_id: str
    restaurant_id: str
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "MenuCategoryCreated"
    aggregate_type: ClassVar[str] = "menu_category"

    @property
    def aggregate_id(self) -> str:
        return self.menu_category_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "menuCategoryId": self.menu_category_id,
            "restaurantId": self.restaurant_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MenuItemCreated:
    menu_item_id: str
    menu_category_id: str
    name: str
    price_amount: Decimal
    occurred_at: datetime

    event_type: ClassVar[str] = "MenuItemCreated"
    aggregate_type: ClassVar[str] = "menu_item"

    @property
    def aggregate_id(self) -> str:
        return self.menu_item_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "menuItemId": self.menu_item_id,
            "menuCategoryId": self.menu_category_id,
            "name": self.name,
            "priceAmount": str(self.price_amount),
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MenuItemUpdated:
    menu_item_id: str
    occurred_at: datetime

    event_type: ClassVar[str] = "MenuItemUpdated"
    aggregate_type: ClassVar[str] = "menu_item"

    @property
    def aggregate_id(self) -> str:
        return self.menu_item_id

    def to_payload(self) -> dict[str, Any]:
        return {"menuItemId": self.menu_item_id, "occurredAt": self.occurred_at.isoformat()}


@dataclass(frozen=True, slots=True)
class MenuItemAvailabilityChanged:
    """The literal event a future KDS/QR-ordering cache-invalidation
    consumer subscribes to. ``branch_id`` is nullable: global vs.
    branch-scoped change."""

    menu_item_id: str
    is_available: bool
    occurred_at: datetime
    branch_id: str | None = None

    event_type: ClassVar[str] = "MenuItemAvailabilityChanged"
    aggregate_type: ClassVar[str] = "menu_item"

    @property
    def aggregate_id(self) -> str:
        return self.menu_item_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "menuItemId": self.menu_item_id,
            "branchId": self.branch_id,
            "isAvailable": self.is_available,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class MenuItemBranchPriceChanged:
    menu_item_id: str
    branch_id: str
    price_amount: Decimal
    effective_from: datetime
    occurred_at: datetime

    event_type: ClassVar[str] = "MenuItemBranchPriceChanged"
    aggregate_type: ClassVar[str] = "menu_item"

    @property
    def aggregate_id(self) -> str:
        return self.menu_item_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "menuItemId": self.menu_item_id,
            "branchId": self.branch_id,
            "priceAmount": str(self.price_amount),
            "effectiveFrom": self.effective_from.isoformat(),
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ModifierGroupCreated:
    modifier_group_id: str
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "ModifierGroupCreated"
    aggregate_type: ClassVar[str] = "modifier_group"

    @property
    def aggregate_id(self) -> str:
        return self.modifier_group_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "modifierGroupId": self.modifier_group_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ModifierCreated:
    modifier_id: str
    modifier_group_id: str
    name: str
    occurred_at: datetime

    event_type: ClassVar[str] = "ModifierCreated"
    aggregate_type: ClassVar[str] = "modifier"

    @property
    def aggregate_id(self) -> str:
        return self.modifier_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "modifierId": self.modifier_id,
            "modifierGroupId": self.modifier_group_id,
            "name": self.name,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ReservationCreated:
    reservation_id: str
    branch_id: str
    party_size: int
    occurred_at: datetime

    event_type: ClassVar[str] = "ReservationCreated"
    aggregate_type: ClassVar[str] = "reservation"

    @property
    def aggregate_id(self) -> str:
        return self.reservation_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "reservationId": self.reservation_id,
            "branchId": self.branch_id,
            "partySize": self.party_size,
            "occurredAt": self.occurred_at.isoformat(),
        }


@dataclass(frozen=True, slots=True)
class ReservationStatusChanged:
    reservation_id: str
    previous_status: str
    new_status: str
    occurred_at: datetime

    event_type: ClassVar[str] = "ReservationStatusChanged"
    aggregate_type: ClassVar[str] = "reservation"

    @property
    def aggregate_id(self) -> str:
        return self.reservation_id

    def to_payload(self) -> dict[str, Any]:
        return {
            "reservationId": self.reservation_id,
            "previousStatus": self.previous_status,
            "newStatus": self.new_status,
            "occurredAt": self.occurred_at.isoformat(),
        }
