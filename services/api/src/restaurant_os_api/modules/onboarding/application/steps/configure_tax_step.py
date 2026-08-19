"""ConfigureTaxStep -- Phase 1 design doc §A.7.

``CreateTaxUseCase.execute(tenant_id, name, rate)`` is deliberately
primitive-arg -- no request DTO, no outbox event (§A.6's own finding:
"``CreateTaxUseCase`` is genuinely create-only... nothing to fold it
into"). This step adapts to that shape as-is rather than refactoring
it to match the DTO-wrapping pattern the other steps use.

``requires=[provision_tenant]``, not ``[create_branch]`` -- tax is
tenant-wide, per §A.7's own amendment ("gating it behind ``create_branch``
was an artificial dependency... defeating the point of the Locale/Floor/
People/Catalog tracks running in parallel").

There is no ``GetTaxUseCase`` and none is added: ``ListTaxesUseCase``
already returns only the tenant's *active* taxes
(``tax_repository.list_active_for_tenant``), so a tax hard-deleted or
deactivated out from under this step simply stops appearing in the
list -- exactly the "deleted out from under it" signal ``verify()``
needs, through an existing read use case, with no new one required.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)
from restaurant_os_api.modules.operations.application.use_cases.create_tax import CreateTaxUseCase
from restaurant_os_api.modules.operations.application.use_cases.list_taxes import ListTaxesUseCase
from restaurant_os_api.modules.operations.domain.entities import Tax


class ConfigureTaxStepInput(BaseModel):
    name: str
    rate: str


class ConfigureTaxStep:
    def __init__(
        self,
        *,
        create_tax_use_case: CreateTaxUseCase,
        list_taxes_use_case: ListTaxesUseCase,
    ) -> None:
        self.id = StepId.CONFIGURE_TAX
        self.title = "Configure tax"
        self.requires: tuple[StepId, ...] = (StepId.PROVISION_TENANT,)
        self.collect_schema = ConfigureTaxStepInput
        self.autonomous = False

        self._create_tax_use_case = create_tax_use_case
        self._list_taxes_use_case = list_taxes_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(self, input: ConfigureTaxStepInput, ctx: OnboardingRunContext) -> Tax:
        assert ctx.tenant_id is not None, "configure_tax requires provision_tenant first"
        return await self._create_tax_use_case.execute(ctx.tenant_id, input.name, input.rate)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.tax_id is None:
            return VerifyFailure(reason="tenant_id/tax_id not yet in context")

        active_taxes = await self._list_taxes_use_case.execute(ctx.tenant_id)
        tax = next((t for t in active_taxes if t.id == ctx.tax_id), None)
        if tax is None:
            return VerifyFailure(
                reason=f"tax {ctx.tax_id} not found among tenant's active taxes on read-back"
            )

        return VerifySuccess(evidence=f"LIST taxes -> {tax.id} active, rate={tax.rate}")

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "ConfigureTaxStep.undo() is not implemented in Phase 1 -- no caller abandons "
            "a run yet."
        )
