"""Unit tests for OnboardingStepRegistry -- Phase 1 design doc §A.2."""

from __future__ import annotations

import pytest

from restaurant_os_api.modules.onboarding.application.registry import OnboardingStepRegistry
from restaurant_os_api.modules.onboarding.domain.enums import StepId
from tests.unit.modules.onboarding.fakes import build_fake_registry_steps, build_phase1_step_graph


def test_requires_graph_matches_the_steps_it_was_built_from() -> None:
    graph = build_phase1_step_graph()
    registry = OnboardingStepRegistry(build_fake_registry_steps(graph))

    assert registry.requires_graph() == graph


def test_all_step_ids_returns_every_registered_step() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    assert set(registry.all_step_ids()) == set(StepId)


def test_direct_dependents_of_provision_tenant_are_its_two_immediate_children() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    dependents = set(registry.direct_dependents(StepId.PROVISION_TENANT))

    # §A.7's amendment: configure_tax unblocks directly off provision_tenant,
    # same as create_restaurant -- not gated behind create_branch.
    assert dependents == {StepId.CREATE_RESTAURANT, StepId.CONFIGURE_TAX}


def test_direct_dependents_excludes_transitive_dependents() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    # create_branch depends on create_restaurant, which depends on
    # provision_tenant -- create_branch is transitive, not direct.
    dependents = registry.direct_dependents(StepId.PROVISION_TENANT)

    assert StepId.CREATE_BRANCH not in dependents


def test_add_recipes_has_no_dependents_it_is_a_leaf() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    assert registry.direct_dependents(StepId.ADD_RECIPES) == ()


def test_topological_order_places_every_step_after_all_its_dependencies() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    order = registry.topological_order()

    assert set(order) == set(StepId)
    position = {step_id: index for index, step_id in enumerate(order)}
    for step_id in StepId:
        for dependency in registry[step_id].requires:
            assert position[dependency] < position[step_id], (
                f"{dependency} must come before {step_id} in topological order"
            )


def test_topological_order_is_deterministic_across_calls() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    assert registry.topological_order() == registry.topological_order()


def test_topological_order_raises_on_a_cycle() -> None:
    a, b = StepId.CREATE_RESTAURANT, StepId.CREATE_BRANCH
    cyclic_graph = {a: (b,), b: (a,)}
    registry = OnboardingStepRegistry(build_fake_registry_steps(cyclic_graph))

    with pytest.raises(ValueError, match="cycle"):
        registry.topological_order()


def test_getitem_and_contains() -> None:
    registry = OnboardingStepRegistry(build_fake_registry_steps())

    assert StepId.PROVISION_TENANT in registry
    assert registry[StepId.PROVISION_TENANT].id == StepId.PROVISION_TENANT


def test_contains_is_false_for_an_unregistered_step() -> None:
    empty_registry = OnboardingStepRegistry({})

    assert StepId.CREATE_TABLE not in empty_registry
