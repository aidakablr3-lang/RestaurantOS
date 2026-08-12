"""Unit tests for TenantProvisioningService's default role catalogue --
in-memory, no DB access."""

from __future__ import annotations

from restaurant_os_api.modules.identity.application.services.tenant_provisioning_service import (
    _DEFAULT_ROLE_CATALOGUE,
)


def _permissions_for(role_name: str) -> frozenset[str]:
    return next(perms for name, _desc, _scope, perms in _DEFAULT_ROLE_CATALOGUE if name == role_name)


class TestDefaultRoleCatalogue:
    def test_bartender_can_read_and_manage_kitchen_tickets(self) -> None:
        # Regression lock: Bartender previously shipped with only
        # menu.read, which meant a real Bartender account got 403
        # PERMISSION_DENIED on the one screen (Kitchen/KDS) that shows
        # them anything to prepare -- found via live RBAC probing in
        # Sprint 7's full-day operational simulation, not a prior test.
        permissions = _permissions_for("Bartender")
        assert "kitchen.read" in permissions
        assert "kitchen.manage" in permissions
        assert "menu.read" in permissions
