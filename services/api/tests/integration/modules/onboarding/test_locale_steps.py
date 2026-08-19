"""Integration tests for the Locale track's remaining steps --
``CreateRestaurantStep``, ``CreateBranchStep``, ``ConfigureTaxStep``
(Phase 1 design doc SSA.7) -- against real Postgres.

Each test builds its real prerequisite state via the shared ``*_ctx``
fixtures (which themselves execute the real, earlier steps), then
constructs and executes the step under test directly, proves
``verify()`` succeeds against the freshly-created row, soft-deletes
that row via the table-owner ``admin_engine`` connection, and proves
``verify()`` now fails.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.steps.configure_tax_step import (
    ConfigureTaxStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_branch_step import (
    CreateBranchStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.create_restaurant_step import (
    CreateRestaurantStepInput,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifySuccess,
)

from .conftest import (
    make_configure_tax_step,
    make_create_branch_step,
    make_create_restaurant_step,
)


async def test_create_restaurant_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    root_ctx: OnboardingRunContext,
) -> None:
    step = make_create_restaurant_step(session_factory)

    restaurant = await step.execute(
        CreateRestaurantStepInput(
            legal_name="Locale Test Restaurant",
            display_name="Locale Test",
            default_currency_code="USD",
        ),
        root_ctx,
    )
    ctx = root_ctx.model_copy(update={"restaurant_id": restaurant.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE restaurants SET deleted_at = now() WHERE id = :id"), {"id": restaurant.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert restaurant.id in result_after_delete.reason
    assert "restaurant" in result_after_delete.reason


async def test_create_branch_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    restaurant_ctx: OnboardingRunContext,
) -> None:
    step = make_create_branch_step(session_factory)

    branch = await step.execute(CreateBranchStepInput(name="Locale Test Branch"), restaurant_ctx)
    ctx = restaurant_ctx.model_copy(update={"branch_id": branch.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE branches SET deleted_at = now() WHERE id = :id"), {"id": branch.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert branch.id in result_after_delete.reason
    assert "branch" in result_after_delete.reason


async def test_configure_tax_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    root_ctx: OnboardingRunContext,
) -> None:
    step = make_configure_tax_step(session_factory)

    tax = await step.execute(ConfigureTaxStepInput(name="GST", rate="0.18"), root_ctx)
    ctx = root_ctx.model_copy(update={"tax_id": tax.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE taxes SET deleted_at = now() WHERE id = :id"), {"id": tax.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert tax.id in result_after_delete.reason
    assert "tax" in result_after_delete.reason
