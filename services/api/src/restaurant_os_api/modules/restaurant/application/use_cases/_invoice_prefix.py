"""Auto-generated invoice_prefix default for a newly-created Branch.

Only used when the caller doesn't supply one explicitly -- an owner
can always override it, at creation or later via update.
"""

from __future__ import annotations

import re

_NON_ALNUM = re.compile(r"[^A-Za-z0-9]")


def default_invoice_prefix(name: str, branch_id: str) -> str:
    """``"Downtown"`` -> ``"DOWN"``. Falls back to a slice of the branch's own
    id when the name has too few alphanumeric characters to make a
    useful prefix (an emoji-only or CJK-only name, for example) --
    invoice numbering should never be silently blocked by an unusual
    branch name."""
    candidate = _NON_ALNUM.sub("", name).upper()[:4]
    if len(candidate) >= 2:
        return candidate
    return f"BR{branch_id[-4:].upper()}"
