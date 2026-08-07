from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.domain.entities import Tenant, TenantStatus, TenantTier
from restaurant_os_api.modules.identity.domain.exceptions import TenantNotActiveError


def _make_tenant(status: TenantStatus) -> Tenant:
    return Tenant(
        id="01ARZ3NDEKTSV4RRFFQ69G5FAV",
        legal_name="Acme Restaurants Inc.",
        display_name="Acme",
        tenant_tier=TenantTier.SHARED,
        status=status,
        default_currency_code="USD",
        created_at=datetime.now(UTC),
    )


@pytest.mark.parametrize("status", [TenantStatus.ACTIVE, TenantStatus.MIGRATING])
def test_ensure_can_authenticate_allows_active_and_migrating(status: TenantStatus) -> None:
    _make_tenant(status).ensure_can_authenticate()  # must not raise


@pytest.mark.parametrize(
    "status",
    [TenantStatus.PROVISIONING, TenantStatus.SUSPENDED, TenantStatus.OFFBOARDED],
)
def test_ensure_can_authenticate_rejects_other_statuses(status: TenantStatus) -> None:
    with pytest.raises(TenantNotActiveError) as exc_info:
        _make_tenant(status).ensure_can_authenticate()
    assert exc_info.value.status == status.value
