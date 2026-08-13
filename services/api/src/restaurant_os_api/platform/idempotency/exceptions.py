"""Exceptions for the shared idempotency wrapper.

Mirrors ``modules/identity/domain/exceptions.py``'s shape (a stable
``error_code`` plus a human ``message``, no HTTP concepts) so
``core/exceptions.py``'s global handler can map these the same way it
already maps every module's own domain errors.
"""

from __future__ import annotations


class IdempotencyError(Exception):
    """Base class for every exception raised by the idempotency wrapper."""

    error_code: str = "IDEMPOTENCY_ERROR"

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class IdempotencyKeyConflictError(IdempotencyError):
    """The same ``Idempotency-Key`` was reused with a materially
    different request body (a different fingerprint) -- almost always a
    client bug (key reuse across unrelated requests), never silently
    honored as if it were a retry of the original request."""

    error_code = "IDEMPOTENCY_KEY_CONFLICT"

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"Idempotency-Key '{idempotency_key}' was already used for a different request."
        )
        self.idempotency_key = idempotency_key


class IdempotentRequestInProgressError(IdempotencyError):
    """A request with this exact ``Idempotency-Key`` is already being
    processed (its placeholder row exists but has no recorded response
    yet) -- returned instead of either blocking indefinitely or racing
    the in-flight request's own use case execution. The caller is
    expected to retry; by then the in-flight request will either have
    completed (and the retry replays its result) or still be running
    (and the retry sees this same error again)."""

    error_code = "IDEMPOTENT_REQUEST_IN_PROGRESS"

    def __init__(self, idempotency_key: str) -> None:
        super().__init__(
            f"A request with Idempotency-Key '{idempotency_key}' is already in progress."
        )
        self.idempotency_key = idempotency_key
