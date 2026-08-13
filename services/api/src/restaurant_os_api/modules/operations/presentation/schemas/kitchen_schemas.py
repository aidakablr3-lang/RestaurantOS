"""Pydantic request/response schemas for KitchenTicket/KitchenItem
(Sprint 7 Step 3)."""

from __future__ import annotations

from datetime import datetime

from restaurant_os_api.core.response import CamelModel
from restaurant_os_api.modules.operations.domain.entities import (
    KitchenItemStatus,
    KitchenTicketStatus,
)


class ChangeKitchenTicketStatusRequestSchema(CamelModel):
    status: KitchenTicketStatus


class ChangeKitchenItemStatusRequestSchema(CamelModel):
    status: KitchenItemStatus


class KitchenItemResponseSchema(CamelModel):
    id: str
    kitchen_ticket_id: str
    order_item_id: str
    status: str
    created_at: datetime


class KitchenTicketResponseSchema(CamelModel):
    id: str
    tenant_id: str
    order_id: str
    station: str
    status: str
    created_at: datetime
    items: list[KitchenItemResponseSchema]
