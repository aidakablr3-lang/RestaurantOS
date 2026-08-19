"""Integration tests for the Floor track -- ``CreateTableZoneStep``,
``CreateTableStep``, ``GenerateQrCodesStep`` (Phase 1 design doc SSA.7)
-- against real Postgres.

``CreateTableStep`` and ``GenerateQrCodesStep`` create two items each
and soft-delete/revoke only *one*, proving partial loss is caught, not
just total loss (per the task's own multi-item-step requirement).
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.steps.create_table_step import (
    CreateTableStepInput,
    TableSpec,
)
from restaurant_os_api.modules.onboarding.application.steps.create_table_zone_step import (
    CreateTableZoneStepInput,
)
from restaurant_os_api.modules.onboarding.application.steps.generate_qr_codes_step import (
    GenerateQrCodesStepInput,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifySuccess,
)

from .conftest import (
    make_create_table_step,
    make_create_table_zone_step,
    make_generate_qr_codes_step,
)


async def test_create_table_zone_step_verify_detects_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    branch_ctx: OnboardingRunContext,
) -> None:
    step = make_create_table_zone_step(session_factory)

    zone = await step.execute(CreateTableZoneStepInput(name="Floor Test Zone"), branch_ctx)
    ctx = branch_ctx.model_copy(update={"table_zone_id": zone.id})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE table_zones SET deleted_at = now() WHERE id = :id"), {"id": zone.id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert zone.id in result_after_delete.reason
    assert "table zone" in result_after_delete.reason


async def test_create_table_step_verify_detects_partial_deletion(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    table_zone_ctx: OnboardingRunContext,
) -> None:
    step = make_create_table_step(session_factory)

    tables = await step.execute(
        CreateTableStepInput(
            tables=[
                TableSpec(table_number="F1", capacity=2),
                TableSpec(table_number="F2", capacity=4),
            ]
        ),
        table_zone_ctx,
    )
    ctx = table_zone_ctx.model_copy(update={"table_ids": tuple(t.id for t in tables)})

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    # Only the second table is soft-deleted -- proves partial loss is
    # caught, not just total loss.
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE tables SET deleted_at = now() WHERE id = :id"), {"id": tables[1].id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    # The *second* table (tables[1]) was soft-deleted -- the reason must
    # name that specific table, not just say "something" failed.
    assert tables[1].id in result_after_delete.reason
    assert tables[0].id not in result_after_delete.reason
    assert "table" in result_after_delete.reason


async def test_generate_qr_codes_step_verify_detects_partial_revocation(
    session_factory: async_sessionmaker[AsyncSession],
    admin_engine: AsyncEngine,
    tables_ctx: OnboardingRunContext,
) -> None:
    step = make_generate_qr_codes_step(session_factory)

    codes = await step.execute(GenerateQrCodesStepInput(), tables_ctx)
    assert len(codes) == 2

    result = await step.verify(tables_ctx)
    assert isinstance(result, VerifySuccess)

    # Only one table's QR code is soft-deleted -- the other table still
    # has its one active code, proving verify() catches partial loss.
    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE qr_codes SET deleted_at = now() WHERE id = :id"), {"id": codes[1].id}
        )

    result_after_delete = await step.verify(tables_ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    # tables_ctx.table_ids[1] is the table whose only QR code was
    # revoked -- the reason must name that table, not table_ids[0].
    assert tables_ctx.table_ids[1] in result_after_delete.reason
    assert tables_ctx.table_ids[0] not in result_after_delete.reason
    assert "QR code" in result_after_delete.reason
