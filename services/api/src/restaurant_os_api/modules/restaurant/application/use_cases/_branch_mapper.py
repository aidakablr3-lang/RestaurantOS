"""Shared Branch (+ optional Address) -> BranchDTO mapping.

Private to this package, matching ``_restaurant_mapper.py``'s
convention. ``address`` is passed in already-resolved (or ``None``)
rather than looked up here -- keeps this a pure mapper, no I/O.
"""

from __future__ import annotations

from restaurant_os_api.modules.restaurant.application.dto import AddressDTO, BranchDTO
from restaurant_os_api.modules.restaurant.domain.entities import Address, Branch


def address_to_dto(address: Address) -> AddressDTO:
    return AddressDTO(
        id=address.id,
        line1=address.line1,
        city=address.city,
        state=address.state,
        country_code=address.country_code,
        postal_code=address.postal_code,
    )


def branch_to_dto(branch: Branch, address: Address | None) -> BranchDTO:
    return BranchDTO(
        id=branch.id,
        tenant_id=branch.tenant_id,
        restaurant_id=branch.restaurant_id,
        name=branch.name,
        status=branch.status.value,
        address=address_to_dto(address) if address is not None else None,
        created_at=branch.created_at,
        gstin=branch.gstin,
        invoice_prefix=branch.invoice_prefix,
    )
