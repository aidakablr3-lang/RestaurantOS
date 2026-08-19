"""Enums shared across the onboarding module.

Phase 1 design doc §A.1/§A.2: kept in their own module, unlike this
codebase's usual pattern of co-locating an enum with the one entity that
carries it (``UserStatus`` next to ``User``, etc.) — ``StepId`` and
``StepStatus`` are referenced by the step contract (§A.2), the
reconciler, the registry, and (once built) three separate persistence
entities under ``onboarding_step_states``/``onboarding_runs``/
``onboarding_audit_log``. No single entity owns them.

``StepId`` is the §A.7 registry table translated directly into code —
``create_owner`` and ``configure_currency`` are deliberately absent
(§0.1/§0.2: the former deleted outright, the latter folded into
``provision_tenant``). §A.7 itself scoped ``add_inventory``/``add_recipes``
as graph-nodes-only ("bulk parsing... Phase 3, out of scope") — a later,
explicit instruction overrode that deferral for §E step 5, and both now
have real ``execute``/``verify`` implementations
(``AddInventoryStep``/``AddRecipesStep``) for a single item/recipe per
step invocation. Bulk import parsing remains out of scope.
"""

from __future__ import annotations

from enum import StrEnum


class OnboardingRunStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    COMPLETED = "completed"
    ABANDONED = "abandoned"


class StepStatus(StrEnum):
    BLOCKED = "blocked"
    READY = "ready"
    COLLECTING = "collecting"
    EXECUTING = "executing"
    VERIFIED = "verified"
    FAILED = "failed"
    SKIPPED = "skipped"


class ActorType(StrEnum):
    HUMAN = "human"
    COPILOT = "copilot"


class StepId(StrEnum):
    PROVISION_TENANT = "provision_tenant"
    CREATE_RESTAURANT = "create_restaurant"
    CREATE_BRANCH = "create_branch"
    CONFIGURE_TAX = "configure_tax"
    CREATE_TABLE_ZONE = "create_table_zone"
    CREATE_TABLE = "create_table"
    GENERATE_QR_CODES = "generate_qr_codes"
    CREATE_MANAGER = "create_manager"
    CREATE_WAITERS = "create_waiters"
    CREATE_KITCHEN_STAFF = "create_kitchen_staff"
    CREATE_MENU_CATEGORY = "create_menu_category"
    CREATE_MENU_ITEMS = "create_menu_items"
    ADD_INVENTORY = "add_inventory"
    ADD_RECIPES = "add_recipes"
