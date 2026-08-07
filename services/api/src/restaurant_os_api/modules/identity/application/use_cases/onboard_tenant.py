"""OnboardTenantUseCase — a thin adapter over TenantProvisioningService.

Per the approved plan: the use case's only job is translating between
the DTO and the service call. All orchestration logic lives in the
service (see its docstring for why).
"""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.dto import OnboardTenantRequestDTO, TenantDTO
from restaurant_os_api.modules.identity.application.services import TenantProvisioningService
from restaurant_os_api.modules.identity.application.use_cases._tenant_mapper import tenant_to_dto


class OnboardTenantUseCase:
    def __init__(self, *, provisioning_service: TenantProvisioningService) -> None:
        self._provisioning_service = provisioning_service

    async def execute(self, request: OnboardTenantRequestDTO) -> TenantDTO:
        tenant = await self._provisioning_service.provision(
            legal_name=request.legal_name,
            display_name=request.display_name,
            default_currency_code=request.default_currency_code,
        )
        return tenant_to_dto(tenant)
