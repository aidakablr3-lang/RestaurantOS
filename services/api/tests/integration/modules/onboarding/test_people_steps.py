"""Integration tests for the People track -- ``CreateManagerStep``,
``CreateWaitersStep``, ``CreateKitchenStaffStep`` (Phase 1 design doc
SSA.7) -- against real Postgres.

All three run in parallel off ``branch_ctx`` (``requires=[create_branch]``
each, per the design doc's own table) and follow the identical
"deleted out from under it" shape as the other tracks -- except here
the invalidation is a role-grant *revocation* (soft-deleting the real
``user_roles`` row ``AssignUserRoleUseCase`` created), which is the
"otherwise invalidates" case the task's own instructions call out
explicitly, since ``verify()`` for these three steps checks
``ResolveUserPermissionsUseCase`` output, not just that the user row
exists.

``CreateWaitersStep``/``CreateKitchenStaffStep`` each create two staff
and revoke only the second one's grant -- proving partial loss is
caught, not just total loss.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.steps.create_kitchen_staff_step import (
    CreateKitchenStaffStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_kitchen_staff_step import (
    StaffSpec as KitchenStaffSpec,
)
from restaurant_os_api.modules.onboarding.application.steps.create_manager_step import (
    CreateManagerStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_waiters_step import (
    CreateWaitersStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_waiters_step import (
    StaffSpec as WaiterSpec,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifySuccess,
)

from .conftest import (
    make_create_kitchen_staff_step,
    make_create_manager_step,
    make_create_waiters_step,
    unique_email,
)


async def _revoke_role_grant(admin_engine: AsyncEngine, tenant_id: str, user_id: str) -> None:
    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE user_roles SET deleted_at = now() "
                "WHERE tenant_id = :tid AND user_id = :uid AND deleted_at IS NULL"
            ),
            {"tid": tenant_id, "uid": user_id},
        )


async def test_create_manager_step_verify_detects_role_revocation(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    step = make_create_manager_step(session_factory)

    output = await step.execute(CreateManagerStepInput(email=unique_email("manager")), branch_ctx)
    ctx = branch_ctx.model_copy(update={"manager_id": output.user_id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    assert ctx.tenant_id is not None
    await _revoke_role_grant(admin_engine, ctx.tenant_id, output.user_id)

    result_after_revoke = await step.verify(ctx)
    assert isinstance(result_after_revoke, VerifyFailure)
    assert output.user_id in result_after_revoke.reason
    assert "table.manage" in result_after_revoke.reason


async def test_create_waiters_step_verify_detects_partial_role_revocation(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    step = make_create_waiters_step(session_factory)

    results = await step.execute(
        CreateWaitersStepInput(
            waiters=[
                WaiterSpec(email=unique_email("waiter-1")),
                WaiterSpec(email=unique_email("waiter-2")),
            ]
        ),
        branch_ctx,
    )
    ctx = branch_ctx.model_copy(update={"waiter_ids": tuple(r.user_id for r in results)})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    # Only the second waiter's grant is revoked.
    assert ctx.tenant_id is not None
    await _revoke_role_grant(admin_engine, ctx.tenant_id, results[1].user_id)

    result_after_revoke = await step.verify(ctx)
    assert isinstance(result_after_revoke, VerifyFailure)
    assert results[1].user_id in result_after_revoke.reason
    assert results[0].user_id not in result_after_revoke.reason
    assert "order.manage" in result_after_revoke.reason


async def test_create_kitchen_staff_step_verify_detects_partial_role_revocation(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    step = make_create_kitchen_staff_step(session_factory)

    results = await step.execute(
        CreateKitchenStaffStepInput(
            kitchen_staff=[
                KitchenStaffSpec(email=unique_email("kitchen-1")),
                KitchenStaffSpec(email=unique_email("kitchen-2")),
            ]
        ),
        branch_ctx,
    )
    ctx = branch_ctx.model_copy(update={"kitchen_staff_ids": tuple(r.user_id for r in results)})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    # Only the second kitchen-staff member's grant is revoked.
    assert ctx.tenant_id is not None
    await _revoke_role_grant(admin_engine, ctx.tenant_id, results[1].user_id)

    result_after_revoke = await step.verify(ctx)
    assert isinstance(result_after_revoke, VerifyFailure)
    assert results[1].user_id in result_after_revoke.reason
    assert results[0].user_id not in result_after_revoke.reason
    assert "kitchen.manage" in result_after_revoke.reason
