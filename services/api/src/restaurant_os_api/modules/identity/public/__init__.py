"""The identity module's public contract.

Technical Architecture v2.0 Group E: this is the *only* package another
module may import from when it needs something from ``identity`` — direct
imports of ``identity.domain``, ``identity.application``, or
``identity.infrastructure`` internals from another module fail the CI
architecture-boundary check.

Empty for now: no other module exists yet to consume a contract from
here. The first cross-module dependency (e.g., the Restaurant module
needing to verify a user belongs to a tenant) adds its function/class
here, not a direct reach into ``identity.domain``.
"""
