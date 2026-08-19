"""Integration tests for ``ProvisionTenantStep`` (Phase 1 design doc SSA.4),
the root of the onboarding graph -- against real Postgres.

Three separate cases, one per assertion ``ProvisionTenantStep.verify()``
makes about the atomically-created state (the fourth -- tenant
active/currency-matching -- is exercised indirectly by every other test
in this suite building on ``root_ctx``, since a failure there would
break every downstream fixture):

- the activation token is deleted out from under the step
- the Owner role grant is revoked (soft-deleted) -- the one invariant
  atomic provisioning exists to guarantee, so it must be independently
  detectable, not just implied by the token check
- the owner user itself is soft-deleted

Each case provisions its own fresh tenant (via a real ``execute()``
call) rather than sharing one across cases, so the failure mode under
test is isolated -- soft-deleting the owner user, for instance, would
also make the role-grant and token checks moot if it ran against a
tenant another case had already mutated.
"""

from __future__ import annotations

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.steps.provision_tenant_step import (
    ProvisionTenantStepInput,
)
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyFailure,
    VerifySuccess,
)

from .conftest import make_provision_tenant_step, unique_email


async def _provision(
    session_factory: async_sessionmaker[AsyncSession], *, legal_name: str
) -> tuple[OnboardingRunContext, str]:
    """Runs the real step once and returns the resulting ctx plus the
    owner's email (some cases need to re-derive the Owner role id)."""
    step = make_provision_tenant_step(session_factory)
    owner_email = unique_email("provision-owner")
    output = await step.execute(
        ProvisionTenantStepInput(
            legal_name=legal_name,
            display_name=legal_name,
            default_currency_code="USD",
            owner_email=owner_email,
        ),
        OnboardingRunContext(),
    )
    ctx = OnboardingRunContext(
        tenant_id=output.tenant_id, owner_id=output.owner_id, expected_currency_code="USD"
    )
    return ctx, owner_email


async def test_provision_tenant_step_verify_detects_activation_token_deletion(
    session_factory: async_sessionmaker[AsyncSession], admin_engine: AsyncEngine
) -> None:
    step = make_provision_tenant_step(session_factory)
    ctx, _ = await _provision(session_factory, legal_name="Provision Step Test LLC")

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)
    assert result.evidence

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("DELETE FROM owner_activation_tokens WHERE tenant_id = :tid AND user_id = :uid"),
            {"tid": ctx.tenant_id, "uid": ctx.owner_id},
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    # No activation-token id is threaded through ctx to assert against
    # (the token is write-once, never read back by id elsewhere) -- the
    # entity *type* is still asserted explicitly, distinguishing this
    # from a connection error or any of the step's other three failure
    # branches, each of which names its own entity/attribute instead.
    assert "activation token" in result_after_delete.reason
    assert "owner" in result_after_delete.reason


async def test_provision_tenant_step_verify_detects_owner_role_grant_revocation(
    session_factory: async_sessionmaker[AsyncSession], admin_engine: AsyncEngine
) -> None:
    """The Owner role grant is the one invariant atomic provisioning
    (SSA.4) exists to guarantee -- if verify() can't independently
    detect its revocation, the invariant has no enforcement, only a
    write-time guarantee nothing then checks."""
    step = make_provision_tenant_step(session_factory)
    ctx, _ = await _provision(session_factory, legal_name="Role Revocation Test LLC")

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text(
                "UPDATE user_roles SET deleted_at = now() "
                "WHERE tenant_id = :tid AND user_id = :uid "
                "AND role_id IN (SELECT id FROM roles WHERE tenant_id = :tid AND name = 'Tenant Owner')"
            ),
            {"tid": ctx.tenant_id, "uid": ctx.owner_id},
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert ctx.owner_id in result_after_delete.reason
    assert "roles.assign" in result_after_delete.reason


async def test_provision_tenant_step_verify_detects_owner_user_deletion(
    session_factory: async_sessionmaker[AsyncSession], admin_engine: AsyncEngine
) -> None:
    step = make_provision_tenant_step(session_factory)
    ctx, _ = await _provision(session_factory, legal_name="Owner Deletion Test LLC")

    result = await step.verify(ctx)
    assert isinstance(result, VerifySuccess)

    async with admin_engine.begin() as conn:
        await conn.execute(
            text("UPDATE users SET deleted_at = now() WHERE id = :uid"), {"uid": ctx.owner_id}
        )

    result_after_delete = await step.verify(ctx)
    assert isinstance(result_after_delete, VerifyFailure)
    assert ctx.owner_id in result_after_delete.reason
    assert "not found" in result_after_delete.reason
