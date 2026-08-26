"""OnboardingStepRegistry — Phase 1 design doc §A.2.

A plain in-memory structure wrapping the concrete ``OnboardingStep``
instances — each one built via DI, wrapping real use cases (§E step 5,
not built yet) — constructed once via DI in ``presentation/dependencies.py``
(also not built yet; no HTTP surface calls this in Phase 1 per §C). Not a
database table: the graph (``requires``) lives in code, same as every
step's own class.
"""

from __future__ import annotations

from typing import Any

from restaurant_os_api.modules.onboarding.domain.enums import StepId
from restaurant_os_api.modules.onboarding.domain.step_contract import OnboardingStep

# Every concrete step has its own TInput/TOutput; the registry holds a
# heterogeneous mix of them keyed by StepId, so it can only type each
# entry as OnboardingStep[Any, Any] -- the same shape any plugin-style
# registry of generic instances takes. Callers that need a specific
# step's real TInput/TOutput (a concrete step class's own tests) import
# that class directly rather than going through the registry.
_AnyOnboardingStep = OnboardingStep[Any, Any]


class OnboardingStepRegistry:
    def __init__(self, steps: dict[StepId, _AnyOnboardingStep]) -> None:
        self._steps = steps

    def __getitem__(self, step_id: StepId) -> _AnyOnboardingStep:
        return self._steps[step_id]

    def __contains__(self, step_id: StepId) -> bool:
        return step_id in self._steps

    def all_step_ids(self) -> tuple[StepId, ...]:
        return tuple(self._steps.keys())

    def requires_graph(self) -> dict[StepId, tuple[StepId, ...]]:
        """The dependency graph alone, as plain data — exactly what
        ``domain.reconciler.recompute_ready_steps`` needs. A thin
        accessor rather than handing the reconciler live step
        instances, so ``domain/`` never imports this ``application/``
        module — see ``reconciler.py``'s own docstring for why that
        direction matters."""
        return {step_id: step.requires for step_id, step in self._steps.items()}

    def direct_dependents(self, step_id: StepId) -> tuple[StepId, ...]:
        """Every step whose ``requires`` names ``step_id`` directly —
        not transitively."""
        return tuple(
            candidate_id for candidate_id, step in self._steps.items() if step_id in step.requires
        )

    def topological_order(self) -> tuple[StepId, ...]:
        """A valid dependency order across the whole graph (Kahn's
        algorithm) — e.g. for seeding every step's initial ``blocked``
        row up front, per spec §2's graph-view requirement ("seed every
        step as blocked up front so the UI can render the whole graph
        immediately")."""
        in_degree = {step_id: len(step.requires) for step_id, step in self._steps.items()}
        ready = sorted(step_id for step_id, degree in in_degree.items() if degree == 0)
        ordered: list[StepId] = []
        while ready:
            step_id = ready.pop(0)
            ordered.append(step_id)
            newly_ready = []
            for dependent_id in self.direct_dependents(step_id):
                in_degree[dependent_id] -= 1
                if in_degree[dependent_id] == 0:
                    newly_ready.append(dependent_id)
            ready = sorted(ready + newly_ready)
        if len(ordered) != len(self._steps):
            cyclic = sorted(set(self._steps) - set(ordered))
            raise ValueError(f"OnboardingStepRegistry has a cycle involving: {cyclic}")
        return tuple(ordered)
