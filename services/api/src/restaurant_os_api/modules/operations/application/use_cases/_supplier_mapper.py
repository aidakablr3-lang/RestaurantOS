from __future__ import annotations

from restaurant_os_api.modules.operations.application.dto import SupplierDTO
from restaurant_os_api.modules.operations.domain.entities import Supplier
from restaurant_os_api.modules.restaurant.application.dto import AddressDTO
from restaurant_os_api.modules.restaurant.domain.entities import Address


def address_to_dto(address: Address) -> AddressDTO:
    return AddressDTO(
        id=address.id,
        line1=address.line1,
        city=address.city,
        state=address.state,
        country_code=address.country_code,
        postal_code=address.postal_code,
    )


def supplier_to_dto(supplier: Supplier, address: Address | None) -> SupplierDTO:
    return SupplierDTO(
        id=supplier.id,
        tenant_id=supplier.tenant_id,
        name=supplier.name,
        status=supplier.status.value,
        created_at=supplier.created_at,
        address=address_to_dto(address) if address is not None else None,
    )
