"""Argon2id password/PIN hashing.

Data Architecture v2.0 SS11.4: Argon2id is the default choice for new
development (memory-hard, resistant to GPU/ASIC cracking), over bcrypt.
The work-factor parameters below are the library's current recommended
defaults for an interactive login path — reviewed periodically as
hardware improves (Technical Architecture v2.0 SS8.4), not hardcoded
forever.
"""

from __future__ import annotations

from argon2 import PasswordHasher as _Argon2PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError


class Argon2PasswordHasher:
    """Implements the ``PasswordHasher`` application port."""

    def __init__(self) -> None:
        self._hasher = _Argon2PasswordHasher()

    def hash(self, plain_text: str) -> str:
        return self._hasher.hash(plain_text)

    def verify(self, plain_text: str, hashed: str) -> bool:
        try:
            self._hasher.verify(hashed, plain_text)
        except (VerifyMismatchError, InvalidHashError):
            return False
        return True
