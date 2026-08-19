"""TenantProvisioningService — orchestrates everything a new tenant needs.

Per the approved Sprint 4.1 plan: kept as its own service, separate from
``OnboardTenantUseCase``, so the use case stays a thin adapter (parse
request, call the service, shape the response) while every step of
"what does provisioning a tenant actually involve" lives in one place
that can grow (more seed data, more defaults) without the use case
itself changing shape.

Everything below runs inside **one** transaction: the tenant row, its
starter subscription, its Tenant Directory entry, its default feature
flag, and the ``TenantCreated`` outbox event either all commit together
or none do — Technical Architecture v2.0 Group B's atomicity guarantee,
applied to the multi-step provisioning workflow specifically because a
tenant left half-provisioned (a row in `tenants` with no subscription)
is a worse failure mode than the whole signup simply failing and being
retried.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.identity.application.interfaces import TokenService
from restaurant_os_api.modules.identity.domain.entities import (
    FeatureFlag,
    OwnerActivationToken,
    Role,
    RoleScope,
    Subscription,
    SubscriptionStatus,
    Tenant,
    TenantDirectoryEntry,
    TenantStatus,
    TenantTier,
    User,
    UserRole,
    UserStatus,
)
from restaurant_os_api.modules.identity.domain.events import RoleCreated, TenantCreated
from restaurant_os_api.modules.identity.domain.events.user_events import UserCreated
from restaurant_os_api.modules.identity.domain.exceptions import TenantLegalNameConflictError
from restaurant_os_api.modules.identity.domain.ports import (
    FeatureFlagRepository,
    OwnerActivationTokenRepository,
    RolePermissionRepository,
    RoleRepository,
    SubscriptionRepository,
    TenantDirectoryRepository,
    TenantRepository,
    UserRepository,
    UserRoleRepository,
)
from restaurant_os_api.platform.database import UnitOfWork
from restaurant_os_api.platform.outbox import OutboxWriter
from restaurant_os_api.platform.tenancy import TenantContext

# Sprint 4.1's one concrete "default feature flag provisioning" seed:
# every new tenant starts with quota enforcement (Commit 6's
# GetTenantQuotaUsageUseCase) explicitly on, as its own tenant-scoped
# flag rather than assumed unconditionally — so a support/ops workflow
# can flip it off per-tenant later (e.g., during a plan-migration
# window) without that being a special case in the quota-checking code
# itself. This is a real, load-bearing default, not a placeholder
# example — there are no other named platform features to seed yet.
_DEFAULT_FEATURE_FLAGS: tuple[str, ...] = ("quota_enforcement_enabled",)

_DEFAULT_TRIAL_DAYS = 14
_DEFAULT_PLAN_CODE = "starter"
_DEFAULT_SHARD_KEY = "shard-01"
_DEFAULT_CONNECTION_REF = "primary"
# One week to click the activation link -- long enough to cover a
# realistic onboarding-team handover delay, short enough that a leaked
# link (email forwarded, screenshot shared) doesn't stay live for months.
_OWNER_ACTIVATION_TTL_HOURS = 168

# RBAC Foundation Architecture SS6.3: the 7 default role -> permission
# mappings, seeded fresh for every new tenant. This seeds the Role and
# RolePermission catalogue rows only -- `seed_default_roles` itself takes
# no user information and grants nothing.
#
# UPDATED, Phase 1 design doc SSA.4: `provision()` below now creates the
# tenant's first Owner user AND its "Tenant Owner" UserRole grant
# atomically, in the same transaction as this seed call -- no tenant
# provisioned through this path is ever left without an owner, even
# momentarily. This is a widening of an already-accepted precedent:
# `provision()` bypasses `RoleGrantPolicy` for this one grant, the exact
# same bypass `scripts/backfill_tenant_owner.py` already uses and
# justifies ("a tenant with zero roles has no roles.assign holder to run
# the check against in the first place"). That script remains the
# recovery path for tenants provisioned *before* this change, and for
# any tenant (old or new) that later degrades back to zero `roles.assign`
# holders -- this atomicity fix guarantees the invariant only at
# creation time, not for all time (see the script's own updated
# docstring).
#
# A conflict check against existing roles (like CreateRoleUseCase does)
# is not needed here: `tenant_id` was just minted a few lines above in
# `provision()`, so no role can already exist for it -- the
# `UNIQUE NULLS NOT DISTINCT (tenant_id, name)` constraint has nothing
# to collide with.
#
# Per SS6.3's own disclosed limitation: new permissions added by future
# modules do not automatically flow into these role definitions. Each
# future module's migration must explicitly re-grant its permissions to
# the roles below (a `RolePermission` insert against the existing row).
#
# `billing.refund` is deliberately NOT granted to any role below (P0
# correction, 2026-08-12): RestaurantOS v1 retired its customer refund
# workflow -- there is no route left that checks this permission (see
# `payment_router.py`'s own docstring), so granting it would only imply
# a capability that doesn't exist. The permission code itself is left
# in the catalogue undeleted (no migration/data change), and any tenant
# provisioned before this change keeps whatever grant it already has --
# harmless, since the route it once authorized no longer exists either.
_DEFAULT_ROLE_CATALOGUE: tuple[tuple[str, str, RoleScope, frozenset[str]], ...] = (
    (
        "Tenant Owner",
        "Full access across every Restaurant Platform resource; can grant and revoke roles.",
        RoleScope.TENANT,
        frozenset(
            {
                "restaurant.read",
                "restaurant.manage",
                "branch.read",
                "branch.manage",
                "table.read",
                "table.manage",
                "menu.read",
                "menu.manage",
                "reservation.read",
                "reservation.manage",
                "roles.assign",
                "order.read",
                "order.manage",
                "kitchen.read",
                "kitchen.manage",
                "billing.read",
                "billing.manage",
                "ledger.read",
                "inventory.read",
                "inventory.manage",
                "inventory_food.read",
                "inventory_food.manage",
                "purchasing.read",
                "purchasing.manage",
                "reports.read",
            }
        ),
    ),
    (
        "Restaurant Manager",
        (
            "Manages a restaurant's branches, tables, menu, and reservations. Granted "
            "per branch (one UserRole row per branch) -- UserRole has no "
            "restaurant-wide scope."
        ),
        RoleScope.BRANCH,
        frozenset(
            {
                "restaurant.read",
                "restaurant.manage",
                "branch.read",
                "branch.manage",
                "table.read",
                "table.manage",
                "menu.read",
                "menu.manage",
                "reservation.read",
                "reservation.manage",
                "order.read",
                "order.manage",
                "kitchen.read",
                "kitchen.manage",
                "billing.read",
                "billing.manage",
                "ledger.read",
                "inventory.read",
                "inventory.manage",
                "inventory_food.read",
                "inventory_food.manage",
                "purchasing.read",
                "purchasing.manage",
                "reports.read",
            }
        ),
    ),
    (
        "Branch Manager",
        (
            "Manages one branch's tables, reservations, orders, and kitchen tickets; "
            "reads (does not edit) the menu."
        ),
        RoleScope.BRANCH,
        frozenset(
            {
                "branch.read",
                "table.read",
                "table.manage",
                "menu.read",
                "reservation.read",
                "reservation.manage",
                "order.read",
                "order.manage",
                "kitchen.read",
                "kitchen.manage",
                "billing.read",
                "billing.manage",
                "inventory.read",
                "inventory.manage",
                "purchasing.read",
                "purchasing.manage",
                "reports.read",
            }
        ),
    ),
    (
        "Waiter",
        "Reads tables and the menu; manages reservations and orders.",
        RoleScope.BRANCH,
        frozenset({"table.read", "menu.read", "reservation.manage", "order.read", "order.manage"}),
    ),
    (
        "Cashier",
        (
            "Reads tables and the menu; takes and manages orders; bills and takes "
            "payment (cannot issue refunds)."
        ),
        RoleScope.BRANCH,
        frozenset(
            {
                "table.read",
                "menu.read",
                "order.read",
                "order.manage",
                "billing.read",
                "billing.manage",
            }
        ),
    ),
    (
        "Kitchen Staff",
        "Reads the menu (availability/86-status); reads and updates kitchen tickets.",
        RoleScope.BRANCH,
        frozenset({"menu.read", "kitchen.read", "kitchen.manage"}),
    ),
    (
        "Bartender",
        (
            "Reads the menu (drink-menu subset); reads and updates kitchen "
            "tickets (no separate bar-ticket queue exists yet, so this is the "
            "same kitchen.read/kitchen.manage grant Kitchen Staff holds)."
        ),
        RoleScope.BRANCH,
        frozenset({"menu.read", "kitchen.read", "kitchen.manage"}),
    ),
    (
        "Inventory Manager",
        (
            "Manages stock levels, recipes, and purchasing; no POS or payroll "
            "access (architecture doc SS10's own role table). Sprint 7 Step 5 "
            "deferred purchasing.* here since Purchasing wasn't built yet -- "
            "Step 6 completes it."
        ),
        RoleScope.BRANCH,
        frozenset(
            {
                "inventory.read",
                "inventory.manage",
                "menu.read",
                "menu.manage",
                "purchasing.read",
                "purchasing.manage",
            }
        ),
    ),
    (
        "Accountant",
        (
            "Full financial reporting access (ledger, billing, purchasing); "
            "no operational (POS/KDS) actions -- architecture doc SS10's own "
            "role table. Disclosed as deferred in Sprint 7 Step 5 (purchasing "
            "wasn't built yet); added now that Step 6 completes it."
        ),
        RoleScope.BRANCH,
        frozenset({"ledger.read", "billing.read", "purchasing.read", "reports.read"}),
    ),
)


async def seed_default_roles(
    *,
    role_repo: RoleRepository,
    role_permission_repo: RolePermissionRepository,
    outbox: OutboxWriter,
    tenant_id: str,
    now: datetime,
) -> dict[str, Role]:
    """Create the SS6.3 default role catalogue for one tenant and return
    the created rows keyed by name.

    Shared by ``TenantProvisioningService.provision()`` (new tenants) and
    ``scripts/backfill_tenant_owner.py`` (tenants that predate this
    change) so the catalogue is defined in exactly one place. Callers are
    responsible for running this inside a transaction with
    ``TenantContext(tenant_id)`` set, and for confirming the tenant has
    no roles yet first -- calling this twice for the same tenant raises
    ``RoleNameConflictError`` on the second call's first insert, via the
    ``UNIQUE NULLS NOT DISTINCT (tenant_id, name)`` constraint.
    """
    roles_by_name: dict[str, Role] = {}
    for role_name, description, default_scope, permission_codes in _DEFAULT_ROLE_CATALOGUE:
        role = await role_repo.create(
            Role(
                id=generate_ulid(),
                tenant_id=tenant_id,
                name=role_name,
                description=description,
                default_scope=default_scope,
                is_system=True,
                is_active=True,
                created_at=now,
            )
        )
        await role_permission_repo.replace_for_role(role.id, permission_codes)
        await outbox.publish(
            tenant_id,
            RoleCreated(role_id=role.id, tenant_id=tenant_id, name=role.name, occurred_at=now),
        )
        roles_by_name[role_name] = role
    return roles_by_name


class TenantProvisioningService:
    def __init__(
        self,
        *,
        session_factory: async_sessionmaker[AsyncSession],
        tenant_repository_factory: Callable[[AsyncSession], TenantRepository],
        subscription_repository_factory: Callable[[AsyncSession], SubscriptionRepository],
        feature_flag_repository_factory: Callable[[AsyncSession], FeatureFlagRepository],
        directory_repository_factory: Callable[[AsyncSession], TenantDirectoryRepository],
        role_repository_factory: Callable[[AsyncSession], RoleRepository],
        role_permission_repository_factory: Callable[[AsyncSession], RolePermissionRepository],
        user_repository_factory: Callable[[AsyncSession], UserRepository],
        user_role_repository_factory: Callable[[AsyncSession], UserRoleRepository],
        owner_activation_token_repository_factory: Callable[
            [AsyncSession], OwnerActivationTokenRepository
        ],
        token_service: TokenService,
        outbox_writer_factory: Callable[[AsyncSession], OutboxWriter],
    ) -> None:
        self._session_factory = session_factory
        self._tenant_repository_factory = tenant_repository_factory
        self._subscription_repository_factory = subscription_repository_factory
        self._feature_flag_repository_factory = feature_flag_repository_factory
        self._directory_repository_factory = directory_repository_factory
        self._role_repository_factory = role_repository_factory
        self._role_permission_repository_factory = role_permission_repository_factory
        self._user_repository_factory = user_repository_factory
        self._user_role_repository_factory = user_role_repository_factory
        self._owner_activation_token_repository_factory = owner_activation_token_repository_factory
        self._token_service = token_service
        self._outbox_writer_factory = outbox_writer_factory

    async def provision(
        self,
        *,
        legal_name: str,
        display_name: str,
        default_currency_code: str,
        owner_email: str,
        owner_phone: str | None = None,
    ) -> tuple[Tenant, User, str]:
        # The third element of the return tuple is the raw one-time
        # activation token -- the only place it ever exists outside the
        # eventual client. Never logged, never stored: only its hash is
        # persisted (OwnerActivationToken.token_hash), the same
        # ``sessions.refresh_token_hash`` discipline.
        # The new tenant's id is minted up front — every RLS-protected
        # insert below (subscription, feature flag) needs
        # `SET LOCAL app.tenant_id` set to *this* value from the start
        # of the transaction, before the `tenants` row (which carries no
        # RLS policy of its own — Data Architecture v2.0 SS5.2) is even
        # inserted.
        tenant_id = generate_ulid()
        now = datetime.now(UTC)

        async with UnitOfWork(self._session_factory, TenantContext(tenant_id)) as uow:
            tenant_repo = self._tenant_repository_factory(uow.session)
            subscription_repo = self._subscription_repository_factory(uow.session)
            flag_repo = self._feature_flag_repository_factory(uow.session)
            directory_repo = self._directory_repository_factory(uow.session)
            role_repo = self._role_repository_factory(uow.session)
            role_permission_repo = self._role_permission_repository_factory(uow.session)
            outbox = self._outbox_writer_factory(uow.session)

            if await tenant_repo.get_by_legal_name(legal_name) is not None:
                raise TenantLegalNameConflictError(legal_name)

            tenant = Tenant(
                id=tenant_id,
                legal_name=legal_name,
                display_name=display_name,
                tenant_tier=TenantTier.SHARED,
                status=TenantStatus.PROVISIONING,
                default_currency_code=default_currency_code,
                created_at=now,
            )
            tenant = await tenant_repo.create(tenant)

            trial_end = now + timedelta(days=_DEFAULT_TRIAL_DAYS)
            subscription = Subscription(
                id=generate_ulid(),
                tenant_id=tenant_id,
                plan_code=_DEFAULT_PLAN_CODE,
                status=SubscriptionStatus.TRIALING,
                current_period_end=trial_end,
                created_at=now,
                trial_end=trial_end,
                next_billing_date=trial_end,
            )
            await subscription_repo.create(subscription)

            await directory_repo.create(
                TenantDirectoryEntry(
                    tenant_id=tenant_id,
                    tenant_tier=tenant.tenant_tier,
                    shard_key=_DEFAULT_SHARD_KEY,
                    connection_ref=_DEFAULT_CONNECTION_REF,
                    status=tenant.status,
                    updated_at=now,
                )
            )

            for flag_key in _DEFAULT_FEATURE_FLAGS:
                await flag_repo.create(
                    FeatureFlag(
                        id=generate_ulid(),
                        key=flag_key,
                        enabled=True,
                        created_at=now,
                        tenant_id=tenant_id,
                        rollout_percentage=100,
                    )
                )

            roles_by_name = await seed_default_roles(
                role_repo=role_repo,
                role_permission_repo=role_permission_repo,
                outbox=outbox,
                tenant_id=tenant_id,
                now=now,
            )
            owner_role = roles_by_name["Tenant Owner"]

            user_repo = self._user_repository_factory(uow.session)
            user_role_repo = self._user_role_repository_factory(uow.session)
            token_repo = self._owner_activation_token_repository_factory(uow.session)

            owner = User(
                id=generate_ulid(),
                tenant_id=tenant_id,
                email=owner_email,
                phone=owner_phone,
                password_hash=None,
                pin_hash=None,
                permission_version=1,
                status=UserStatus.INVITED,
                created_at=now,
                is_platform_admin=False,
            )
            owner = await user_repo.create(owner)

            # RoleGrantPolicy.ensure_can_grant is deliberately NOT called
            # here -- see the module-level comment above
            # `_DEFAULT_ROLE_CATALOGUE` for the full reasoning. This is a
            # system operation with no delegating actor, not a human or
            # API caller granting a role -- `granted_by_user_id=None` is
            # the domain entity's own documented shape for exactly this.
            await user_role_repo.create(
                UserRole(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    user_id=owner.id,
                    role_id=owner_role.id,
                    branch_id=None,
                    granted_at=now,
                    granted_by_user_id=None,
                )
            )

            raw_activation_token = self._token_service.generate_refresh_token()
            await token_repo.create(
                OwnerActivationToken(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    user_id=owner.id,
                    token_hash=self._token_service.hash_refresh_token(raw_activation_token),
                    issued_at=now,
                    expires_at=now + timedelta(hours=_OWNER_ACTIVATION_TTL_HOURS),
                    used_at=None,
                )
            )

            await outbox.publish(
                tenant_id,
                UserCreated(
                    user_id=owner.id,
                    tenant_id=tenant_id,
                    email=owner.email,
                    created_by_user_id=None,
                    occurred_at=now,
                ),
            )

            tenant.activate()
            tenant = await tenant_repo.update(tenant)
            await directory_repo.update_status(tenant_id, tenant.status.value)

            await outbox.publish(
                tenant_id,
                TenantCreated(
                    tenant_id=tenant_id,
                    legal_name=tenant.legal_name,
                    display_name=tenant.display_name,
                    tenant_tier=tenant.tenant_tier.value,
                    occurred_at=now,
                ),
            )

        return tenant, owner, raw_activation_token
