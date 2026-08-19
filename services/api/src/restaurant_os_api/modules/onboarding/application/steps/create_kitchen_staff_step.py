"""CreateKitchenStaffStep -- Phase 1 design doc §A.7.

Same shape as ``CreateWaitersStep`` (``CreateUserUseCase`` +
``AssignUserRoleUseCase``, role **"Kitchen Staff"**,
``granter_user_id=ctx.owner_id``, ``RoleScope.BRANCH``), looped once
per entry in ``input.kitchen_staff``.

``verify()`` checks every id in ``ctx.kitchen_staff_ids`` is
``active`` and holds ``kitchen.manage`` at ``ctx.branch_id`` -- a
permission Waiter does not hold.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pydantic import BaseModel, Field

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

_ROLE_NAME = "Kitchen Staff"
_VERIFY_PERMISSION = "kitchen.manage"


class StaffSpec(BaseModel):
    email: str
    phone: str | None = None


class CreateKitchenStaffStepInput(BaseModel):
    kitchen_staff: list[StaffSpec] = Field(min_length=1)


@dataclass(slots=True)
class CreateKitchenStaffResult:
    user_id: str
    user_role_id: str
    generated_password: str | None


class CreateKitchenStaffStep:
    def __init__(
        self,
        *,
        create_user_use_case: CreateUserUseCase,
        get_role_by_name_use_case: GetRoleByNameUseCase,
        assign_user_role_use_case: AssignUserRoleUseCase,
        get_user_use_case: GetUserUseCase,
        resolve_user_permissions_use_case: ResolveUserPermissionsUseCase,
    ) -> None:
        self.id = StepId.CREATE_KITCHEN_STAFF
        self.title = "Create kitchen staff"
        self.requires: tuple[StepId, ...] = (StepId.CREATE_BRANCH,)
        self.collect_schema = CreateKitchenStaffStepInput
        self.autonomous = False

        self._create_user_use_case = create_user_use_case
        self._get_role_by_name_use_case = get_role_by_name_use_case
        self._assign_user_role_use_case = assign_user_role_use_case
        self._get_user_use_case = get_user_use_case
        self._resolve_user_permissions_use_case = resolve_user_permissions_use_case

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(
        self, input: CreateKitchenStaffStepInput, ctx: OnboardingRunContext
    ) -> tuple[CreateKitchenStaffResult, ...]:
        assert ctx.tenant_id is not None and ctx.owner_id is not None and ctx.branch_id is not None, (
            "create_kitchen_staff requires create_branch first"
        )
        role = await self._get_role_by_name_use_case.execute(ctx.tenant_id, _ROLE_NAME)
        results: list[CreateKitchenStaffResult] = []
        for spec in input.kitchen_staff:
            user = await self._create_user_use_case.execute(
                ctx.tenant_id,
                CreateUserRequestDTO(
                    creator_user_id=ctx.owner_id, email=spec.email, phone=spec.phone
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
            results.append(
                CreateKitchenStaffResult(
                    user_id=user.id,
                    user_role_id=user_role.id,
                    generated_password=user.generated_password,
                )
            )
        return tuple(results)

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        if ctx.tenant_id is None or ctx.branch_id is None:
            return VerifyFailure(reason="tenant_id/branch_id not yet in context")
        if not ctx.kitchen_staff_ids:
            return VerifyFailure(reason="no kitchen_staff_ids recorded in context")

        for user_id in ctx.kitchen_staff_ids:
            try:
                staff = await self._get_user_use_case.execute(ctx.tenant_id, user_id)
            except UserNotFoundError:
                return VerifyFailure(reason=f"kitchen staff user {user_id} not found on read-back")
            if staff.status != "active":
                return VerifyFailure(
                    reason=f"kitchen staff user {user_id} is '{staff.status}', not 'active'"
                )

            # NOTE: this asserts permission *effect*, not role identity --
            # it proves the user holds kitchen.manage at this branch, not
            # that they specifically still hold the Kitchen Staff grant
            # this step created. kitchen.manage is NOT unique to Kitchen
            # Staff in the default role catalogue -- Bartender holds the
            # identical permission set. If this same user were ever also
            # granted Bartender (no step in this graph does that today,
            # but nothing prevents it later), revoking only the Kitchen
            # Staff grant would leave kitchen.manage intact via the
            # Bartender grant, and this check would report VerifySuccess
            # even though the Kitchen Staff assignment specifically was
            # revoked. Same failure mode if the default role catalogue
            # itself changes to add kitchen.manage to another branch
            # role. Detecting that precisely would need a use case that
            # checks role-grant identity directly, which doesn't exist yet.
            permissions = await self._resolve_user_permissions_use_case.execute(
                ctx.tenant_id, user_id
            )
            if not permissions.has(_VERIFY_PERMISSION, branch_id=ctx.branch_id):
                return VerifyFailure(
                    reason=(
                        f"kitchen staff user {user_id} does not hold '{_VERIFY_PERMISSION}' "
                        f"at branch {ctx.branch_id}"
                    )
                )

        return VerifySuccess(
            evidence=(
                f"{len(ctx.kitchen_staff_ids)} kitchen staff active and hold "
                f"'{_VERIFY_PERMISSION}' at branch {ctx.branch_id}"
            )
        )

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError(
            "CreateKitchenStaffStep.undo() is not implemented in Phase 1 -- no caller "
            "abandons a run yet."
        )
