from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class FeatureFlagStatusDTO:
    """The *resolved* effective value of a flag for one tenant right now
    — enabled/disabled, date window, and rollout percentage already
    folded together (``FeatureFlag.is_effective_for``). A caller never
    needs to re-implement that resolution logic."""

    key: str
    enabled: bool
