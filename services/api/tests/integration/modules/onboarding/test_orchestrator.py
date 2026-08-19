"""Integration tests for ``OnboardingOrchestrator`` -- Phase 1 design doc
§A.3 / §E step 6, against real PostgreSQL.

Exactly the three scenarios the build for this step called out
explicitly, no more:

- A run interrupted mid-execute, reloaded, and resumed produces no
  duplicate records -- the same test shape as the Idempotency-Key
  tests in step 3 (``tests/integration/platform/test_idempotency.py``'s
  own "concurrent duplicate cannot execute the use case twice" test).
- A step whose ``verify()`` returns ``VerifyFailure`` leaves the run
  resumable, not wedged.
- ``provision_tenant`` failing leaves zero rows across all three
  onboarding tables and no partial tenant.

Each test reuses the real 14-step registry and real orchestrator wiring
from ``conftest.py`` -- no fakes, no mocks, matching every other test in
this directory.
"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.domain.exceptions import TenantLegalNameConflictError
from restaurant_os_api.modules.onboarding.application.registry import OnboardingStepRegistry
from restaurant_os_api.modules.onboarding.application.steps.provision_tenant_step import (
    ProvisionTenantStepInput,
)
from restaurant_os_api.modules.onboarding.domain.enums import StepId, StepStatus
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
)
from restaurant_os_api.modules.onboarding.infrastructure.database.repositories import (
    SQLAlchemyOnboardingAuditLogRepository,
    SQLAlchemyOnboardingRunRepository,
    SQLAlchemyOnboardingStepStateRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.tenancy import TenantContext

from .conftest import (
    CrashOnExecuteAuditRepository,
    DeleteAfterExecuteBranchStep,
    build_real_registry,
    make_orchestrator,
    make_provision_tenant_step,
    seed_platform_user,
    unique_email,
)


async def _count_restaurants(
    session_factory: async_sessionmaker[AsyncSession], tenant_id: str
) -> int:
    async with UnitOfWork(session_factory, TenantContext(tenant_id)) as uow:
        result = await uow.session.execute(
            text("SELECT COUNT(*) FROM restaurants WHERE tenant_id = :tenant_id"),
            {"tenant_id": tenant_id},
        )
        return result.scalar_one()


async def _count_tenants_by_legal_name(
    session_factory: async_sessionmaker[AsyncSession], legal_name: str
) -> int:
    async with UnitOfWork(session_factory) as uow:
        result = await uow.session.execute(
            text("SELECT COUNT(*) FROM tenants WHERE legal_name = :legal_name"),
            {"legal_name": legal_name},
        )
        return result.scalar_one()


class TestMidExecuteCrashResume:
    """A run interrupted mid-execute, reloaded, and resumed produces no
    duplicate records."""

    async def test_resume_replays_the_cached_execute_instead_of_re_executing(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        registry = build_real_registry(session_factory)
        admin_user_id = await seed_platform_user(session_factory)

        orchestrator = make_orchestrator(session_factory, registry=registry)
        run = await orchestrator.start_run(admin_user_id)

        provisioned = await orchestrator.execute_step(
            run.id,
            StepId.PROVISION_TENANT,
            {
                "legal_name": f"Crash Co {generate_ulid()}",
                "display_name": "Crash Co",
                "default_currency_code": "USD",
                "owner_email": unique_email("owner"),
            },
        )
        assert provisioned.status == StepStatus.VERIFIED
        tenant_id = provisioned.context.tenant_id
        assert tenant_id is not None

        # A second orchestrator, identical except its audit-log
        # repository raises on create_restaurant's own "execute" audit
        # entry -- the first *unguarded* write after the real
        # CreateRestaurantUseCase (and the idempotency guard's own
        # response record) have already committed. An unhandled
        # exception right there is exactly what a real process crash in
        # that window would leave behind: real work committed, the step
        # state still 'executing'. See conftest.make_orchestrator's own
        # docstring.
        crashing_registry = build_real_registry(session_factory)
        crashing_orchestrator = make_orchestrator(
            session_factory,
            registry=crashing_registry,
            audit_log_repository_factory=lambda session: CrashOnExecuteAuditRepository(
                session, crash_step_id=StepId.CREATE_RESTAURANT
            ),
        )
        with pytest.raises(RuntimeError, match="simulated crash"):
            await crashing_orchestrator.execute_step(
                run.id,
                StepId.CREATE_RESTAURANT,
                {
                    "legal_name": "Crash Restaurant",
                    "display_name": "Crash Restaurant",
                    "default_currency_code": "USD",
                },
            )

        # The real side effect survived the "crash" -- exactly one
        # restaurant row exists -- and the step is stuck 'executing'
        # with no output recorded yet.
        assert await _count_restaurants(session_factory, tenant_id) == 1
        async with UnitOfWork(session_factory) as uow:
            state_repo = SQLAlchemyOnboardingStepStateRepository(uow.session)
            crashed_state = await state_repo.get(run.id, StepId.CREATE_RESTAURANT)
        assert crashed_state is not None
        assert crashed_state.status == StepStatus.EXECUTING
        assert crashed_state.output is None
        assert crashed_state.attempts == 1

        # Resume with a normal (non-crashing) orchestrator sharing the
        # same underlying database -- the identical idempotency key
        # means the guard replays the already-recorded response rather
        # than calling CreateRestaurantUseCase a second time.
        normal_orchestrator = make_orchestrator(session_factory, registry=registry)
        snapshot = await normal_orchestrator.resume_run(run.id)

        assert snapshot.steps[StepId.CREATE_RESTAURANT].status == StepStatus.VERIFIED
        assert await _count_restaurants(session_factory, tenant_id) == 1, (
            "resume must replay the crashed attempt's cached result, not create a second restaurant"
        )


class TestVerifyFailureLeavesRunResumable:
    """A step whose ``verify()`` returns ``VerifyFailure`` leaves the run
    resumable, not wedged -- proven by (a) the run staying ``in_progress``
    and reloadable via ``resume_run`` rather than being torn down, and
    (b) an independent track of the same run (``configure_tax``, which
    only requires ``provision_tenant``, not ``create_branch``) still
    being executable to completion afterward."""

    async def test_a_failed_steps_run_stays_in_progress_and_other_tracks_still_complete(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        real_registry = build_real_registry(session_factory)
        admin_user_id = await seed_platform_user(session_factory)

        # A registry identical to the real one except create_branch is
        # wrapped to hard-delete its own just-created row immediately
        # after a real execute() -- the same "deleted out from under
        # it" scenario CreateBranchStep.verify() is already tested
        # against directly, reproduced through the orchestrator's own
        # single execute-then-verify call (see conftest's own
        # DeleteAfterExecuteBranchStep docstring).
        sabotaged_steps = {
            step_id: (
                DeleteAfterExecuteBranchStep(real_registry[step_id], session_factory)
                if step_id == StepId.CREATE_BRANCH
                else real_registry[step_id]
            )
            for step_id in real_registry.all_step_ids()
        }
        sabotaged_registry = OnboardingStepRegistry(sabotaged_steps)
        orchestrator = make_orchestrator(session_factory, registry=sabotaged_registry)

        run = await orchestrator.start_run(admin_user_id)
        provisioned = await orchestrator.execute_step(
            run.id,
            StepId.PROVISION_TENANT,
            {
                "legal_name": f"Wedge Co {generate_ulid()}",
                "display_name": "Wedge Co",
                "default_currency_code": "USD",
                "owner_email": unique_email("owner"),
            },
        )
        assert provisioned.status == StepStatus.VERIFIED

        restaurant_result = await orchestrator.execute_step(
            run.id,
            StepId.CREATE_RESTAURANT,
            {
                "legal_name": "Wedge Restaurant",
                "display_name": "Wedge Restaurant",
                "default_currency_code": "USD",
            },
        )
        assert restaurant_result.status == StepStatus.VERIFIED

        branch_result = await orchestrator.execute_step(
            run.id, StepId.CREATE_BRANCH, {"name": "Doomed Branch"}
        )

        assert branch_result.status == StepStatus.FAILED
        assert isinstance(branch_result.verify_result, VerifyFailure)
        assert "not found on read-back" in branch_result.verify_result.reason

        # The run itself is untouched -- still there, still in_progress,
        # not deleted (the one deliberate exception to that is
        # provision_tenant alone -- see the orchestrator's own
        # docstring).
        async with UnitOfWork(session_factory) as uow:
            run_repo = SQLAlchemyOnboardingRunRepository(uow.session)
            reloaded_run = await run_repo.get_by_id(run.id)
        assert reloaded_run is not None
        assert reloaded_run.status.value == "in_progress"

        # resume_run() itself succeeds cleanly (not wedged) and
        # accurately reports the failed step rather than erroring.
        snapshot = await orchestrator.resume_run(run.id)
        assert snapshot.steps[StepId.CREATE_BRANCH].status == StepStatus.FAILED
        assert snapshot.steps[StepId.CREATE_BRANCH].error is not None

        # An independent track of the same run -- configure_tax only
        # requires provision_tenant, not create_branch -- is still
        # executable to completion, proving the *run* isn't wedged even
        # though one step is permanently failed.
        assert snapshot.steps[StepId.CONFIGURE_TAX].status == StepStatus.READY
        tax_result = await orchestrator.execute_step(
            run.id, StepId.CONFIGURE_TAX, {"name": "VAT", "rate": "0.05"}
        )
        assert tax_result.status == StepStatus.VERIFIED


class TestProvisionTenantFailureLeavesZeroRows:
    """``provision_tenant`` failing leaves zero rows across all three
    onboarding tables and no partial tenant."""

    async def test_a_legal_name_conflict_deletes_the_run_and_leaves_no_partial_tenant(
        self, session_factory: async_sessionmaker[AsyncSession]
    ) -> None:
        registry = build_real_registry(session_factory)
        admin_user_id = await seed_platform_user(session_factory)

        # Seed a real tenant the run-under-test's own provision_tenant
        # attempt will collide with. TenantProvisioningService.provision()
        # checks get_by_legal_name() as the very first statement inside
        # its own atomic transaction and raises
        # TenantLegalNameConflictError before any insert happens (see
        # that service's own docstring) -- execute() is guaranteed to
        # fail with zero partial writes of its own, so this test proves
        # the orchestrator's own cleanup, not a side effect of the
        # provisioning service's atomicity.
        legal_name = f"Dup Co {generate_ulid()}"
        seed_step = make_provision_tenant_step(session_factory)
        await seed_step.execute(
            ProvisionTenantStepInput(
                legal_name=legal_name,
                display_name=legal_name,
                default_currency_code="USD",
                owner_email=unique_email("owner"),
            ),
            OnboardingRunContext(),
        )
        assert await _count_tenants_by_legal_name(session_factory, legal_name) == 1

        orchestrator = make_orchestrator(session_factory, registry=registry)
        run = await orchestrator.start_run(admin_user_id)

        result = await orchestrator.execute_step(
            run.id,
            StepId.PROVISION_TENANT,
            {
                "legal_name": legal_name,
                "display_name": legal_name,
                "default_currency_code": "USD",
                "owner_email": unique_email("owner"),
            },
        )

        assert result.status == StepStatus.FAILED
        assert isinstance(result.verify_result, VerifyFailure)
        assert TenantLegalNameConflictError(legal_name).args[0] in result.verify_result.reason

        # The run, every step state, and every audit entry are gone --
        # provision_tenant is the graph's root, so nothing else could
        # have executed first; there is no prior state worth preserving
        # (see the orchestrator's own module docstring).
        async with UnitOfWork(session_factory) as uow:
            run_repo = SQLAlchemyOnboardingRunRepository(uow.session)
            state_repo = SQLAlchemyOnboardingStepStateRepository(uow.session)
            audit_repo = SQLAlchemyOnboardingAuditLogRepository(uow.session)
            assert await run_repo.get_by_id(run.id) is None
            assert await state_repo.list_for_run(run.id) == []
            assert await audit_repo.list_for_run(run.id) == []

        # No partial or duplicate tenant either -- only the one seeded
        # above, exactly as before the failed attempt.
        assert await _count_tenants_by_legal_name(session_factory, legal_name) == 1
