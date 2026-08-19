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


def reblock_transitive_dependents(
    step_states: dict[StepId, StepStatus],
    failed_step_id: StepId,
    direct_dependents_graph: dict[StepId, tuple[StepId, ...]],
) -> dict[StepId, StepStatus]:
    """Walks every transitive dependent of ``failed_step_id`` and demotes
    any currently ``ready`` one back to ``blocked`` — the orchestrator's
    (§E step 6) counterpart to ``recompute_ready_steps``, called instead
    of it when a step's ``verify()`` returns ``VerifyFailure`` (or
    ``execute()`` raises) rather than after a success.

    ``direct_dependents_graph`` maps a step to the steps that directly
    require it — the inverse of ``recompute_ready_steps``'s own
    ``requires_graph``, e.g. built from
    ``{step_id: registry.direct_dependents(step_id) for step_id in
    registry.all_step_ids()}`` by the caller into plain data, same
    "domain never imports application" reason ``recompute_ready_steps``
    already documents for taking ``requires_graph`` instead of the
    registry itself.

    Under the reconciler's own invariant (a step only reaches ``ready``
    once every one of its ``requires`` is ``verified``), no dependent of
    a step that has just moved to ``failed`` — as opposed to
    ``verified`` — could have reached ``ready`` through *this*
    dependency in the first place; this function still runs
    unconditionally on every failure rather than being skipped as
    unreachable, so it stays correct if a *previously verified* step is
    later re-attempted and fails, without needing to know which case
    it is.
    """
    updated = dict(step_states)
    frontier = [failed_step_id]
    seen = {failed_step_id}
    while frontier:
        current = frontier.pop()
        for dependent_id in direct_dependents_graph.get(current, ()):
            if updated.get(dependent_id) == StepStatus.READY:
                updated[dependent_id] = StepStatus.BLOCKED
            if dependent_id not in seen:
                seen.add(dependent_id)
                frontier.append(dependent_id)
    return updated
