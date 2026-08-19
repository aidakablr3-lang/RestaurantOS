"""Part B -- real registry wiring (Phase 1 design doc SSA.2).

Constructs all 14 *real* step instances (the same wiring Part A's tests
use, via the shared ``make_*_step`` functions in ``conftest.py`` -- not
the fakes from ``tests/unit/modules/onboarding/fakes.py``), registers
them into a real ``OnboardingStepRegistry``, and proves the graph is
real and consistent:

- ``topological_order()`` succeeds (no cycle) and returns all 14
  ``StepId`` values, each appearing only after everything in its own
  ``requires`` tuple.
- ``requires_graph()`` matches the ``requires`` tuple declared on each
  real step instance exactly.

No database writes happen here -- constructing a step only wires
use cases to a ``session_factory``, it doesn't call any of them. The
``session_factory`` fixture (and therefore a real, migrated Postgres)
is still required because building it requires the session-scoped
``engine`` fixture from ``tests/integration/conftest.py``.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.domain.enums import StepId

from .conftest import build_real_registry as _build_real_registry


async def test_real_registry_topological_order_covers_all_14_steps_in_valid_order(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = _build_real_registry(session_factory)

    order = registry.topological_order()

    assert set(order) == set(StepId)
    assert len(order) == 14

    position = {step_id: index for index, step_id in enumerate(order)}
    for step_id in order:
        step = registry[step_id]
        for required_id in step.requires:
            assert position[required_id] < position[step_id], (
                f"{step_id} appears before its own requirement {required_id}"
            )


async def test_real_registry_requires_graph_matches_each_real_steps_requires(
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    registry = _build_real_registry(session_factory)

    graph = registry.requires_graph()

    assert graph == {
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

    # Also proven generically (not just against the hardcoded table
    # above), directly from each real step instance's own .requires --
    # this is what actually makes the test "real wiring", not just a
    # restatement of the design doc's SSA.7 table.
    for step_id in StepId:
        assert graph[step_id] == registry[step_id].requires
