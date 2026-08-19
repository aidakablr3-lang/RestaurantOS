"""The OnboardingStep contract — Phase 1 design doc §A.2.

Spec §3's TypeScript/Zod ``OnboardingStep`` interface translated into
this codebase's idiom: ``Protocol`` (not ``ABC`` — this codebase already
uses ``Protocol`` for every port with multiple implementations, e.g.
``UserRepository`` in ``identity/domain/ports/``, and uses ``ABC``
nowhere), Pydantic models in place of Zod schemas (``collect_schema:
type[TInput]`` — Pydantic *is* the schema-as-a-type mechanism already;
there's no separate "schema instance" object the way Zod has one), and a
Pydantic discriminated union in place of the TS discriminated union for
``VerifyResult``.

Every concrete step (e.g. ``CreateRestaurantStep``, in
``application/steps/`` — Phase 1 design doc §E step 5, not built yet)
implements this Protocol by wrapping an existing use case: ``execute()``
adapts ``TInput`` + ``ctx`` into the use case's own request DTO and
calls it; ``verify()`` reads the record back through the corresponding
``Get*UseCase``/``List*UseCase``. This *is* "reuse the existing service
layer," not a principle bolted on afterward.
"""

from __future__ import annotations

from typing import Any, Literal, Protocol

from pydantic import BaseModel

from restaurant_os_api.modules.onboarding.domain.enums import StepId


class OnboardingRunContext(BaseModel):
    """The accumulated, typed state one run carries between steps.

    Mirrors ``onboarding_runs.context``'s JSONB storage shape (Phase 1
    design doc §A.1) — this is what gets constructed *from* that column
    and handed to steps at runtime; steps never see a bag of ``Any``.

    Two kinds of fields live here, not just one: ids an *earlier* step's
    output that a *later* step's ``execute()`` needs (e.g. ``branch_id``
    for ``create_table_zone``), and ids a step's *own* ``verify()``
    needs to re-check a specific record by identity rather than by a
    weaker match on name/attributes (e.g. ``tax_id`` — nothing else in
    the graph requires ``configure_tax``, but ``verify()`` still needs
    to know *which* tax it created). ``verify(self, ctx)`` takes no
    other argument, so anything it must check precisely has to live in
    ``ctx``, populated by the orchestrator (§E step 6, not built yet)
    from the step's own output before ``verify()`` is called.
    """

    tenant_id: str | None = None
    owner_id: str | None = None
    expected_currency_code: str | None = None
    restaurant_id: str | None = None
    branch_id: str | None = None
    table_zone_id: str | None = None
    table_ids: tuple[str, ...] = ()
    tax_id: str | None = None
    manager_id: str | None = None
    waiter_ids: tuple[str, ...] = ()
    kitchen_staff_ids: tuple[str, ...] = ()
    menu_category_id: str | None = None
    menu_item_ids: tuple[str, ...] = ()
    inventory_item_id: str | None = None
    recipe_menu_item_id: str | None = None


class VerifySuccess(BaseModel):
    ok: Literal[True] = True
    evidence: str


class VerifyFailure(BaseModel):
    ok: Literal[False] = False
    reason: str
    remediation: str | None = None


VerifyResult = VerifySuccess | VerifyFailure


class OnboardingStep[TInput: BaseModel, TOutput](Protocol):
    id: StepId
    title: str
    requires: tuple[StepId, ...]
    collect_schema: type[TInput]
    autonomous: bool

    def autofill(self, ctx: OnboardingRunContext) -> dict[str, Any]:
        """Defaults offered before ``raw_input`` is validated against
        ``collect_schema`` (§A.3 step 2) — e.g. ``provision_tenant``
        autofilling a currency from the owner's country. Steps with
        nothing to autofill return ``{}``."""
        ...

    async def execute(self, input: TInput, ctx: OnboardingRunContext) -> TOutput:
        """Perform the step's real write by calling an existing use
        case — never new business logic (§9's non-negotiable)."""
        ...

    async def verify(self, ctx: OnboardingRunContext) -> VerifyResult:
        """Read the write back through an existing ``Get*``/``List*``
        use case. The sole authority on whether the step actually
        landed (§A.3 step 6) — a successful ``execute()`` with a
        failing ``verify()`` is ``failed``, not ``verified``."""
        ...

    async def undo(self, ctx: OnboardingRunContext) -> None:
        """Best-effort compensation for a run abandoned after this step
        already executed. Not exercised by Phase 1 (no caller abandons
        a run yet — §E step 6 is orchestration only); declared on the
        contract now so no concrete step (§E step 5) is built against a
        Protocol it will need to widen later."""
        ...
