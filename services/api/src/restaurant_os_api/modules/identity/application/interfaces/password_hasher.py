"""Application-layer port for password/PIN hashing.

Technical Architecture v2.0 SS2.2: the Application layer depends on this
interface only — the concrete Argon2id implementation (Infrastructure
layer) is wired in by the presentation layer's dependency providers.
"""

from __future__ import annotations

from typing import Protocol


class PasswordHasher(Protocol):
    def hash(self, plain_text: str) -> str:
        """Return a self-contained hash (salt + parameters embedded)."""
        ...

    def verify(self, plain_text: str, hashed: str) -> bool:
        """Return True iff ``plain_text`` matches ``hashed``.

        Must never raise on a mismatch — a wrong password is an expected,
        common outcome, not an exceptional one.
        """
        ...
