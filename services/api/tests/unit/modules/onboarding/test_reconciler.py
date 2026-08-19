"""Unit tests for the reconciler -- Phase 1 design doc §A.2.

Covers graph reconciliation, including the two parallel-track shapes
that matter most for this design: a simple single-dependency chain, and
``add_recipes``' join (it needs *both* ``create_menu_items`` and
``add_inventory`` verified, not just one).
"""

from __future__ import annotations

from restaurant_os_api.modules.onboarding.application.registry import OnboardingStepRegistry
from restaurant_os_api.modules.onboarding.domain.enums import StepId, StepStatus
from restaurant_os_api.modules.onboarding.domain.reconciler import recompute_ready_steps
from tests.unit.modules.onboarding.fakes import build_fake_registry_steps


def test_promotes_a_blocked_step_whose_single_dependency_is_verified() -> None:
    step_states = {
        StepId.PROVISION_TENANT: StepStatus.VERIFIED,
        StepId.CREATE_RESTAURANT: StepStatus.BLOCKED,
    }
    graph = {StepId.CREATE_RESTAURANT: (StepId.PROVISION_TENANT,)}

    updated = recompute_ready_steps(step_states, graph)

    assert updated[StepId.CREATE_RESTAURANT] == StepStatus.READY


def test_leaves_a_join_step_blocked_while_any_dependency_is_unverified() -> None:
    step_states = {
        StepId.CREATE_MENU_ITEMS: StepStatus.VERIFIED,
        StepId.ADD_INVENTORY: StepStatus.BLOCKED,
        StepId.ADD_RECIPES: StepStatus.BLOCKED,
    }
    graph = {StepId.ADD_RECIPES: (StepId.CREATE_MENU_ITEMS, StepId.ADD_INVENTORY)}

    updated = recompute_ready_steps(step_states, graph)

    assert updated[StepId.ADD_RECIPES] == StepStatus.BLOCKED


def test_promotes_a_join_step_only_once_every_dependency_is_verified() -> None:
    step_states = {
        StepId.CREATE_MENU_ITEMS: StepStatus.VERIFIED,
        StepId.ADD_INVENTORY: StepStatus.VERIFIED,
        StepId.ADD_RECIPES: StepStatus.BLOCKED,
    }
    graph = {StepId.ADD_RECIPES: (StepId.CREATE_MENU_ITEMS, StepId.ADD_INVENTORY)}

    updated = recompute_ready_steps(step_states, graph)

    assert updated[StepId.ADD_RECIPES] == StepStatus.READY


def test_leaves_every_non_blocked_status_untouched() -> None:
    for status in (
        StepStatus.READY,
        StepStatus.COLLECTING,
        StepStatus.EXECUTING,
        StepStatus.VERIFIED,
        StepStatus.FAILED,
        StepStatus.SKIPPED,
    ):
        updated = recompute_ready_steps({StepId.CREATE_RESTAURANT: status}, {})
        assert updated[StepId.CREATE_RESTAURANT] == status


def test_root_step_with_no_requires_promotes_immediately() -> None:
    updated = recompute_ready_steps(
        {StepId.PROVISION_TENANT: StepStatus.BLOCKED}, {StepId.PROVISION_TENANT: ()}
    )

    assert updated[StepId.PROVISION_TENANT] == StepStatus.READY


def test_does_not_mutate_the_input_mapping() -> None:
    step_states = {StepId.PROVISION_TENANT: StepStatus.BLOCKED}
    original = dict(step_states)

    recompute_ready_steps(step_states, {StepId.PROVISION_TENANT: ()})

    assert step_states == original


def test_promoting_a_step_to_ready_does_not_unblock_its_own_dependents_in_the_same_call() -> None:
    """ready != verified -- a dependent only unblocks in a *later* call,
    once the newly-ready step is actually executed and verified."""
    step_states = {
        StepId.PROVISION_TENANT: StepStatus.VERIFIED,
        StepId.CREATE_RESTAURANT: StepStatus.BLOCKED,
        StepId.CREATE_BRANCH: StepStatus.BLOCKED,
    }
    graph = {
        StepId.CREATE_RESTAURANT: (StepId.PROVISION_TENANT,),
        StepId.CREATE_BRANCH: (StepId.CREATE_RESTAURANT,),
    }

    updated = recompute_ready_steps(step_states, graph)

    assert updated[StepId.CREATE_RESTAURANT] == StepStatus.READY
    assert updated[StepId.CREATE_BRANCH] == StepStatus.BLOCKED


def test_recompute_against_a_real_registrys_requires_graph() -> None:
    """Ties registry and reconciler together on the real §A.7 graph --
    proves both parallel tracks (Locale/Floor via configure_tax, and the
    Catalog track) unblock directly off provision_tenant, per the
    amendment correcting configure_tax's `requires`."""
    registry = OnboardingStepRegistry(build_fake_registry_steps())
    step_states = {step_id: StepStatus.BLOCKED for step_id in StepId}
    step_states[StepId.PROVISION_TENANT] = StepStatus.VERIFIED

    updated = recompute_ready_steps(step_states, registry.requires_graph())

    assert updated[StepId.CREATE_RESTAURANT] == StepStatus.READY
    assert updated[StepId.CONFIGURE_TAX] == StepStatus.READY
    # create_branch still needs create_restaurant verified, not just ready.
    assert updated[StepId.CREATE_BRANCH] == StepStatus.BLOCKED
