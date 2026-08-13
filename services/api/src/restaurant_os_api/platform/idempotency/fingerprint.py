"""Canonical request fingerprinting for idempotency comparison.

A SHA-256 hex digest of the JSON body with keys sorted and separators
normalized -- two requests with the same key fields in a different
wire order (a possibility with some HTTP clients/proxies) still
fingerprint identically, while any actual content difference changes
the digest.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any


def fingerprint_request(body: dict[str, Any]) -> str:
    canonical = json.dumps(body, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()
