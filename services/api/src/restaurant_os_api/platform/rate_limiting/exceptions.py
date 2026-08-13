"""Exceptions for ``platform/rate_limiting``.

Deliberately not a subclass of any module's domain-exception hierarchy
(``IdentityDomainError``/``RestaurantDomainError``) -- those are all
routed through ``core/exceptions.py``'s global handlers into the
standard ``ApiErrorResponse`` envelope, which is the wrong shape for
the one route this exists for (``GET /api/v1/qr/{token}``, ADR 0001's
deliberately minimal, non-enveloped bootstrap response). This is
caught directly by that route instead.
"""

from __future__ import annotations


class RateLimitExceededError(Exception):
    """Raised when a bucket (source IP or token) has exceeded its
    configured limit within the current window."""
