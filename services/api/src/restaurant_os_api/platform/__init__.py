"""Shared kernel: cross-cutting infrastructure every module depends on.

Deliberately kept minimal (Technical Architecture v2.0 Group E) — only
genuinely cross-cutting concerns (database base/mixins, tenancy context,
outbox, idempotency, audit) belong here. A module-specific concern
belongs inside that module, not here.
"""
