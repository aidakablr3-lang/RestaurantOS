"""The reconciler — Phase 1 design doc §A.2, modeled on ``RoleGrantPolicy``.

Same shape as ``identity/domain/services/role_grant_policy.py``: stateless
domain logic, no I/O, every input already-loaded data, the caller
persists whatever the result implies. Spec §4 calls this "a background
reconciler," but **there is no background process anywhere in this
codebase** (no scheduler, no queue — ``backfill_tenant_owner.py``'s own
docstring states this as a deliberate property). Phase 1 has no
autonomous actor to run one for yet, so this runs *synchronously*, called
by the orchestrator (§E step 6, not built yet) in the same transaction,
immediately after a step's ``verify()`` returns ``ok=True``.

Deliberately takes ``requires_graph: dict[StepId, tuple[StepId, ...]]``,
plain data, rather than an ``OnboardingStepRegistry`` (as §A.2's own
pseudocode literally shows it) — the registry lives in
``application/registry.py`` because it wraps live ``OnboardingStep``
instances built via DI over use cases, an application-layer concern.
Handing that object to a ``domain/`` function would have this layer
import ``application/``, which is backwards for every other module in
this codebase (see e.g. ``identity/public/__init__.py``'s own statement
of the rule). ``OnboardingStepRegistry.requires_graph()`` is the thin
accessor that bridges the two without breaking that direction.
"""

from __future__ import annotations

from restaurant_os_api.modules.onboarding.domain.enums import StepId, StepStatus


def recompute_ready_steps(
    step_states: dict[StepId, StepStatus],
    requires_graph: dict[StepId, tuple[StepId, ...]],
) -> dict[StepId, StepStatus]:
    """For every step currently ``blocked``, promote to ``ready`` iff
    every entry in its ``requires`` is ``verified``. Pure — returns the
    full recomputed mapping; the caller persists only what changed.

    A single pass over every step is sufficient, not just a shortcut:
    each blocked step's promotion depends only on whether its *own*
    ``requires`` are already ``verified`` in the snapshot handed in, not
    on any other step being promoted to ``ready`` within this same call
    — ``ready`` isn't ``verified``, so promoting one step never changes
    whether a *different* step's ``requires`` are satisfied in the same
    pass. A step's dependents can only unblock after it is later
    actually executed and verified — i.e. in a subsequent call to this
    function, not a further iteration of this one.
    """
    updated = dict(step_states)
    for step_id, status in step_states.items():
        if status != StepStatus.BLOCKED:
            continue
        requires = requires_graph.get(step_id, ())
        if all(updated.get(dependency) == StepStatus.VERIFIED for dependency in requires):
            updated[step_id] = StepStatus.READY
    return updated
