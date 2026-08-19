"""Test doubles for the onboarding module.

``FakeOnboardingStep`` and ``build_phase1_step_graph()`` exist to give
``test_registry.py``/``test_reconciler.py`` a realistic, non-trivial
graph to exercise without depending on any real concrete step (§E step
5, not built yet) — the registry and reconciler only ever read a step's
``.id``/``.requires``, so a fake this thin is enough.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import (
    OnboardingRunContext,
    VerifyResult,
)


class _EmptyStepInput(BaseModel):
    pass


class FakeOnboardingStep:
    """A minimal ``OnboardingStep``. ``execute()``/``verify()``/``undo()``
    are never called by registry/reconciler tests (those only read
    ``.id``/``.requires``), so they raise rather than silently doing
    nothing -- a test that accidentally exercises one fails loudly
    instead of passing on a no-op."""

    collect_schema: type[BaseModel] = _EmptyStepInput
    autonomous = False

    def __init__(self, step_id: StepId, requires: tuple[StepId, ...] = ()) -> None:
        self.id = step_id
        self.title = step_id.value
        self.requires = requires

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        return {}

    async def execute(self, input: BaseModel, ctx: OnboardingRunContext) -> Any:
        raise NotImplementedError("FakeOnboardingStep.execute() is not exercised by these tests")

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        raise NotImplementedError("FakeOnboardingStep.verify() is not exercised by these tests")

    async def undo(self, ctx: OnboardingRunContext) -> None:
        raise NotImplementedError("FakeOnboardingStep.undo() is not exercised by these tests")


def build_phase1_step_graph() -> dict[StepId, tuple[StepId, ...]]:
    """The full Phase 1 design doc §A.7 registry table, ``requires``
    edges only. Shared by ``test_registry.py`` (wrapped in
    ``FakeOnboardingStep`` instances) and ``test_reconciler.py`` (used
    directly as a plain graph) so both suites exercise the same
    real-shaped graph, not a synthetic toy one."""
    return {
        StepId.PROVISION_TENANT: (),
        StepId.CREATE_RESTAURANT: (StepId.PROVISION_TENANT,),
        StepId.CREATE_BRANCH: (StepId.CREATE_RESTAURANT,),
        StepId.CONFIGURE_TAX: (StepId.PROVISION_TENANT,),
        StepId.CREATE_TABLE_ZONE: (StepId.CREATE_BRANCH,),
        StepId.CREATE_TABLE: (StepId.CREATE_TABLE_ZONE,),
        StepId.GENERATE_QR_CODES: (StepId.CREATE_TABLE,),
        StepId.CREATE_MANAGER: (StepId.CREATE_BRANCH,),
        StepId.CREATE_WAITERS: (StepId.CREATE_BRANCH,),
        StepId.CREATE_KITCHEN_STAFF: (StepId.CREATE_BRANCH,),
        StepId.CREATE_MENU_CATEGORY: (StepId.CREATE_RESTAURANT,),
        StepId.CREATE_MENU_ITEMS: (StepId.CREATE_MENU_CATEGORY,),
        StepId.ADD_INVENTORY: (StepId.CREATE_BRANCH,),
        StepId.ADD_RECIPES: (StepId.CREATE_MENU_ITEMS, StepId.ADD_INVENTORY),
    }


def build_fake_registry_steps(
    graph: dict[StepId, tuple[StepId, ...]] | None = None,
) -> dict[StepId, FakeOnboardingStep]:
    graph = graph if graph is not None else build_phase1_step_graph()
    return {step_id: FakeOnboardingStep(step_id, requires) for step_id, requires in graph.items()}
