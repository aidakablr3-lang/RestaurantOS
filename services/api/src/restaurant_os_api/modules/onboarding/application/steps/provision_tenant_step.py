"""ProvisionTenantStep -- Phase 1 design doc §A.4/§A.7.

The root of the graph (``requires=()``). Wraps
``TenantProvisioningService.provision()`` exactly as written for §E
step 3 -- this step adds no new writes of its own, only the
``OnboardingStep`` contract around an already-atomic operation.

``verify()`` is where the four assertions the atomicity guarantee is
actually *for* live: a successful ``execute()`` only proves the writes
were attempted, not that the tenant is in a state the rest of the graph
can safely build on. Checks, in order: the tenant exists and is
``active`` with the expected currency; the owner exists and is
``invited``; the owner concretely holds ``roles.assign`` (proving the
Owner role grant landed and still carries the permission, not just that
some role by that name exists); the activation token is still
unexpired and unused. Any one of these failing -- including "the owner
user was deleted after creation" or "the Owner role grant was revoked"
-- is exactly the "record deleted out from under it" case this method
exists to catch.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.identity.application.services.tenant_provisioning_service import (
    TenantProvisioningService,
)
from restaurant_os_api.modules.identity.application.use_cases.get_owner_activation_token_status import (
    GetOwnerActivationTokenStatusUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.get_tenant import GetTenantUseCase
from restaurant_os_api.modules.identity.application.use_cases.get_user import GetUserUseCase
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import (
    TenantNotFoundError,
    UserNotFoundError,
)
from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)

_OWNER_ASSIGN_PERMISSION = "roles.assign"


class ProvisionTenantStepInput(BaseModel):
    legal_name: str
    display_name: str
    default_currency_code: str
    owner_email: str
    owner_phone: str | None = None


@dataclass(slots=True)
class ProvisionTenantStepOutput:
    tenant_id: str
    owner_id: str
    activation_token: str


class ProvisionTenantStep:
    # Instance attributes, not class-body constants -- OnboardingStep's
    # Protocol declares id/title/requires/collect_schema/autonomous as
    # plain instance variables (step_contract.py), and mypy strict
    # already flags exactly this mismatch elsewhere in this codebase
    # (DomainEvent's own Protocol members vs. its implementers' class
    # variables) as a real type error, not a style nit. Setting them in
    # __init__ sidesteps that class entirely rather than reproducing it.
    def __init__(
        self,
        *,
        provisioning_service: TenantProvisioningService,
        get_tenant_use_case: GetTenantUseCase,
        get_user_use_case: GetUserUseCase,
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
        get_owner_activation_token_status_use_case: GetOwnerActivationTokenStatusUseCase,
    ) -> None:
        self.id = StepId.PROVISION_TENANT
        self.title = "Provision tenant, Owner, and activation token"
        self.requires: tuple[StepId, ...] = ()
        self.collect_schema = ProvisionTenantStepInput
        self.autonomous = False

        self._provisioning_service = provisioning_service
        self._get_tenant_use_case = get_tenant_use_case
        self._get_user_use_case = get_user_use_case
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case
        self._get_owner_activation_token_status_use_case = (
            get_owner_activation_token_status_use_case
        )

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: ProvisionTenantStepInput, ctx: OnboardingRunContext
    ) -> ProvisionTenantStepOutput:
        tenant, owner, raw_token = await self._provisioning_service.provision(
            legal_name=input.legal_name,
            display_name=input.display_name,
            default_currency_code=input.default_currency_code,
            owner_email=input.owner_email,
            owner_phone=input.owner_phone,
        )
        return ProvisionTenantStepOutput(
            tenant_id=tenant.id, owner_id=owner.id, activation_token=raw_token
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.owner_id is None:
            return VerifyFailure(
                reason="tenant_id/owner_id not yet in context -- execute() has not run"
            )

        try:
            tenant = await self._get_tenant_use_case.execute(ctx.tenant_id)
        except TenantNotFoundError:
            return VerifyFailure(reason=f"tenant {ctx.tenant_id} not found on read-back")
        if tenant.status != "active":
            return VerifyFailure(
                reason=f"tenant {ctx.tenant_id} is '{tenant.status}', not 'active'"
            )
        if (
            ctx.expected_currency_code is not None
            and tenant.default_currency_code != ctx.expected_currency_code
        ):
            return VerifyFailure(
                reason=(
                    f"tenant currency '{tenant.default_currency_code}' does not match "
                    f"expected '{ctx.expected_currency_code}'"
                )
            )

        try:
            owner = await self._get_user_use_case.execute(ctx.tenant_id, ctx.owner_id)
        except UserNotFoundError:
            return VerifyFailure(reason=f"owner user {ctx.owner_id} not found on read-back")
        if owner.status != "invited":
            return VerifyFailure(
                reason=f"owner user {ctx.owner_id} is '{owner.status}', not 'invited'"
            )

        owner_permissions = await self._resolve_user_permissions_use_case.execute(
            ctx.tenant_id, ctx.owner_id
        )
        if not owner_permissions.has(_OWNER_ASSIGN_PERMISSION):
            return VerifyFailure(
                reason=f"owner user {ctx.owner_id} does not hold '{_OWNER_ASSIGN_PERMISSION}'"
            )

        token_active = await self._get_owner_activation_token_status_use_case.execute(
            ctx.tenant_id, ctx.owner_id
        )
        if not token_active:
            return VerifyFailure(reason="no unexpired, unused activation token for owner")

        return VerifySuccess(
            evidence=(
                f"tenant {ctx.tenant_id} active (currency {tenant.default_currency_code}); "
                f"owner {ctx.owner_id} invited with {_OWNER_ASSIGN_PERMISSION}; "
                "activation token unexpired"
            )
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "ProvisionTenantStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet, and compensating a tenant/Owner/token write atomically "
            "is scripts/purge_tenant.py's job, not the step contract's."
        )
