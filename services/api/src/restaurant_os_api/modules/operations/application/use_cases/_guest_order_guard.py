"""Shared guest-order access guard (guest QR ordering).

A guest's only credential is a QR token, re-resolved by the router on
every call into a ``(tenant_id, branch_id, table_id)`` triple (ADR 0001:
"resolution is a bootstrap step only... confers no elevated trust or
authorization beyond that" -- the same re-check discipline applies here,
per request, not just once at order-creation time). Every guest use case
that touches an existing order calls this immediately after loading it:
an order belonging to a different branch, or to a different table within
the same branch, collapses into the same ``OrderNotFoundError`` as an
order that doesn't exist at all -- the same cross-scope-is-404
discipline every other module in this codebase already follows, so nothing
here distinguishes "wrong table" from "no such order" to an unauthenticated
caller.
"""

from __future__ import annotations

from restaurant_os_api.modules.operations.domain.entities import Order
from restaurant_os_api.modules.operations.domain.exceptions import OrderNotFoundError


def ensure_guest_order_access(order: Order, *, branch_id: str, table_id: str) -> None:
    if order.branch_id != branch_id or order.table_id != table_id:
        raise OrderNotFoundError(order.id)
