"""Onboarding module: the Setup Copilot's step contract, registry, and orchestration.

Phase 1 design doc (docs/PHASE1_DESIGN.md) §A.2/§A.3: drives a new
tenant through provisioning, restaurant/branch/table setup, staff
creation, and menu/tax configuration by wrapping the existing use cases
of ``identity``, ``restaurant``, and ``operations`` — it owns no
business data of its own beyond run/step bookkeeping (§A.1). Depends on
all three of those modules; none of them depend on this one.
"""
