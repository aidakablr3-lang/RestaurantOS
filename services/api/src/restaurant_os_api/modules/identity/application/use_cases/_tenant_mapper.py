"""Shared Tenant (domain entity) -> TenantDTO mapping.

Private to this package (leading underscore) — every tenant lifecycle
use case needs the exact same mapping, and duplicating it six times
across onboard/get/list/update/suspend/reactivate/offboard would be the
kind of copy-paste that drifts the moment one of them forgets to update
after a `TenantDTO` field changes.
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.dto import TenantDTO
from restaurant_os_api.modules.identity.domain.entities import Tenant


def tenant_to_dto(tenant: Tenant) -> TenantDTO:
    return TenantDTO(
        id=tenant.id,
        legal_name=tenant.legal_name,
        display_name=tenant.display_name,
        tenant_tier=tenant.tenant_tier.value,
        status=tenant.status.value,
        default_currency_code=tenant.default_currency_code,
        metadata=tenant.metadata,
        created_at=tenant.created_at,
    )
