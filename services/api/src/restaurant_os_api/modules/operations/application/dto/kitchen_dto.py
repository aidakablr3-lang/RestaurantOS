"""Application-layer DTOs for KitchenTicket/KitchenItem (Sprint 7 Step 3)."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass(frozen=True, slots=True)
class KitchenItemDTO:
    id: str
    kitchen_ticket_id: str
    order_item_id: str
    status: str
    created_at: datetime


@dataclass(frozen=True, slots=True)
class KitchenTicketDTO:
    id: str
    tenant_id: str
    order_id: str
    station: str
    status: str
    created_at: datetime
    items: list[KitchenItemDTO]


@dataclass(frozen=True, slots=True)
class KitchenTicketListResultDTO:
    tickets: list[KitchenTicketDTO]
    total: int
    offset: int
    limit: int


@dataclass(frozen=True, slots=True)
class ChangeKitchenTicketStatusRequestDTO:
    kitchen_ticket_id: str
    status: str


@dataclass(frozen=True, slots=True)
class ChangeKitchenItemStatusRequestDTO:
    kitchen_item_id: str
    status: str
