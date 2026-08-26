"""CreateManagerStep -- Phase 1 design doc §A.7.

``requires=[create_branch]`` -- parallel with ``create_waiters``/
``create_kitchen_staff``, per §A.7's own table. Wraps two existing use
cases in sequence, exactly as the design doc specifies:
``CreateUserUseCase`` (bare account, no access) then
``AssignUserRoleUseCase`` with ``granter_user_id=ctx.owner_id`` (the
atomically-created Owner from ``provision_tenant`` is always the
granter for every staff-creation step in Phase 1 -- there is no other
authenticated actor in-process yet).

Role name: **"Branch Manager"**, seeded per-tenant by
``seed_default_roles`` inside ``TenantProvisioningService.provision()``
(so it already exists by the time this step can run, since
``provision_tenant`` is an ancestor of every other step). Resolved via
``GetRoleByNameUseCase`` -- never a repository. ``Branch Manager`` is
``RoleScope.BRANCH`` (confirmed against
``tenant_provisioning_service.py``'s own role catalogue), so the grant
is scoped to ``ctx.branch_id``, not tenant-wide.

``verify()`` checks the created user is ``active`` and concretely
holds ``table.manage`` at ``ctx.branch_id`` -- a permission Branch
Manager holds but Waiter/Kitchen Staff do not, so this also confirms
the *right* role landed, not just *some* role.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.identity.application.dto import (
    AssignUserRoleRequestDTO,
    CreateUserRequestDTO,
)
from restaurant_os_api.modules.identity.application.use_cases.assign_user_role import (
    AssignUserRoleUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.create_user import CreateUserUseCase
from restaurant_os_api.modules.identity.application.use_cases.get_role_by_name import (
    GetRoleByNameUseCase,
)
from restaurant_os_api.modules.identity.application.use_cases.get_user import GetUserUseCase
from restaurant_os_api.modules.identity.application.use_cases.resolve_user_permissions import (
    ResolveUserPermissionsUseCase,
)
from restaurant_os_api.modules.identity.domain.exceptions import UserNotFoundError
from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifyResult,
    VerifySuccess,
)

_ROLE_NAME = "Branch Manager"
_VERIFY_PERMISSION = "table.manage"


class CreateManagerStepInput(BaseModel):
    email: str
    phone: str | None = None


@dataclass(slots=True)
class CreateManagerStepOutput:
    user_id: str
    user_role_id: str
    generated_password: str | None


class CreateManagerStep:
    def __init__(
        self,
        *,
        create_user_use_case: CreateUserUseCase,
        get_role_by_name_use_case: GetRoleByNameUseCase,
        assign_user_role_use_case: AssignUserRoleUseCase,
        get_user_use_case: GetUserUseCase,
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
    ) -> None:
        self.id = StepId.CREATE_MANAGER
        self.title = "Create branch manager"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_BRANCH,)
        self.collect_schema = CreateManagerStepInput
        self.autonomous = False

        self._create_user_use_case = create_user_use_case
        self._get_role_by_name_use_case = get_role_by_name_use_case
        self._assign_user_role_use_case = assign_user_role_use_case
        self._get_user_use_case = get_user_use_case
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateManagerStepInput, ctx: OnboardingRunContext
    ) -> CreateManagerStepOutput:
        assert (
            ctx.tenant_id is not None and ctx.owner_id is not None and ctx.branch_id is not None
        ), "create_manager requires create_branch first"
        role = await self._get_role_by_name_use_case.execute(ctx.tenant_id, _ROLE_NAME)
        user = await self._create_user_use_case.execute(
            ctx.tenant_id,
            CreateUserRequestDTO(
                creator_user_id=ctx.owner_id, email=input.email, phone=input.phone
            ),
        )
        user_role = await self._assign_user_role_use_case.execute(
            ctx.tenant_id,
            AssignUserRoleRequestDTO(
                granter_user_id=ctx.owner_id,
                target_user_id=user.id,
                role_id=role.id,
                branch_id=ctx.branch_id,
            ),
        )
        return CreateManagerStepOutput(
            user_id=user.id,
            user_role_id=user_role.id,
            generated_password=user.generated_password,
        )

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.branch_id is None or ctx.manager_id is None:
            return VerifyFailure(reason="tenant_id/branch_id/manager_id not yet in context")

        try:
            manager = await self._get_user_use_case.execute(ctx.tenant_id, ctx.manager_id)
        except UserNotFoundError:
            return VerifyFailure(reason=f"manager user {ctx.manager_id} not found on read-back")
        if manager.status != "active":
            return VerifyFailure(
                reason=f"manager user {ctx.manager_id} is '{manager.status}', not 'active'"
            )

        # NOTE: this asserts permission *effect*, not role identity -- it
        # proves the user holds table.manage at this branch, not that
        # they specifically still hold the Branch Manager grant this
        # step created. table.manage happens to be Branch-Manager-only
        # in the current default role catalogue, so the two are
        # equivalent today. That equivalence breaks if either (a) some
        # other step in a future run grants this same user a role that
        # also carries table.manage at this branch (no default role
        # does today), or (b) the default role catalogue itself changes
        # to add table.manage to another role -- either would let
        # verify() report VerifySuccess even after the Branch Manager
        # grant specifically was revoked. Detecting that precisely would
        # need a use case that checks role-grant identity directly
        # (e.g. "does user X hold role Y"), which doesn't exist yet.
        permissions = await self._resolve_user_permissions_use_case.execute(
            ctx.tenant_id, ctx.manager_id
        )
        if not permissions.has(_VERIFY_PERMISSION, branch_id=ctx.branch_id):
            return VerifyFailure(
                reason=(
                    f"manager user {ctx.manager_id} does not hold '{_VERIFY_PERMISSION}' "
                    f"at branch {ctx.branch_id}"
                )
            )

        return VerifySuccess(
            evidence=f"user {ctx.manager_id} active and holds '{_VERIFY_PERMISSION}' at branch {ctx.branch_id}"
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateManagerStep.undo() is not implemented in Phase 1 -- no caller abandons "
            "a run yet."
        )
