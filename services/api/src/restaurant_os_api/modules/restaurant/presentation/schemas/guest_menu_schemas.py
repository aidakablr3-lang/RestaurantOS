"""Response schema for the guest QR-ordering menu view (guest ordering).

Standard ``ApiResponse[T]``/``CamelModel`` envelope, unlike
``QRResolutionResponseSchema`` -- ADR 0001's minimal, non-enveloped
contract binds specifically to ``GET /api/v1/qr/{token}`` (the bootstrap
lookup), not to every future route keyed by a QR token. This is a
distinct, newer feature with no such constraint, so it follows every
other endpoint's own standard shape instead.
"""

from __future__ import annotations

from decimal import Decimal

from restaurant_os_api.core.response import CamelModel


class GuestMenuItemResponseSchema(CamelModel):
    id: str
    name: str
    price_amount: Decimal
    currency_code: str


class GuestMenuCategoryResponseSchema(CamelModel):
    id: str
    name: str
    display_order: int
    items: list[GuestMenuItemResponseSchema]


class GuestMenuResponseSchema(CamelModel):
    branch_id: str
    table_id: str
    restaurant_name: str
    branch_name: str
    table_number: str
    categories: list[GuestMenuCategoryResponseSchema]
