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

from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.modules.onboarding.application.registry import OnboardingStepRegistry
from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import OnboardingStep

from .conftest import (
    make_add_inventory_step,
    make_add_recipes_step,
    make_configure_tax_step,
    make_create_branch_step,
    make_create_kitchen_staff_step,
    make_create_manager_step,
    make_create_menu_category_step,
    make_create_menu_items_step,
    make_create_restaurant_step,
    make_create_table_step,
    make_create_table_zone_step,
    make_create_waiters_step,
    make_generate_qr_codes_step,
    make_provision_tenant_step,
)


def _build_real_registry(
    session_factory: async_sessionmaker[AsyncSession],
) -> OnboardingStepRegistry:
    steps: dict[StepId, OnboardingStep[Any, Any]] = {
        StepId.PROVISION_TENANT: make_provision_tenant_step(session_factory),
        StepId.CREATE_RESTAURANT: make_create_restaurant_step(session_factory),
        StepId.CREATE_BRANCH: make_create_branch_step(session_factory),
        StepId.CONFIGURE_TAX: make_configure_tax_step(session_factory),
        StepId.CREATE_TABLE_ZONE: make_create_table_zone_step(session_factory),
        StepId.CREATE_TABLE: make_create_table_step(session_factory),
        StepId.GENERATE_QR_CODES: make_generate_qr_codes_step(session_factory),
        StepId.CREATE_MANAGER: make_create_manager_step(session_factory),
        StepId.CREATE_WAITERS: make_create_waiters_step(session_factory),
        StepId.CREATE_KITCHEN_STAFF: make_create_kitchen_staff_step(session_factory),
        StepId.CREATE_MENU_CATEGORY: make_create_menu_category_step(session_factory),
        StepId.CREATE_MENU_ITEMS: make_create_menu_items_step(session_factory),
        StepId.ADD_INVENTORY: make_add_inventory_step(session_factory),
        StepId.ADD_RECIPES: make_add_recipes_step(session_factory),
    }
    return OnboardingStepRegistry(steps)


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
