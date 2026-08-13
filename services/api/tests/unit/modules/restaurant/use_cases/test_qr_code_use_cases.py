"""Unit tests for QR Code management use cases (Sprint 5 Step 4.6) --
in-memory fakes, no network/DB access.

Scoped to the authenticated management path only. Nothing here builds
or assumes any unauthenticated-resolution/rate-limiting infrastructure
(explicitly deferred to a separate step)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from restaurant_os_api.modules.identity.application.dto import ResolvedPermissions
from restaurant_os_api.modules.identity.domain.exceptions import PermissionDeniedError
from restaurant_os_api.modules.restaurant.application.use_cases import (
    CreateQRCodeUseCase,
    ListQRCodesUseCase,
)
from restaurant_os_api.modules.restaurant.domain.entities import (
    Branch,
    BranchStatus,
    QRCode,
    QRCodeStatus,
    Table,
    TableStatus,
)
from restaurant_os_api.modules.restaurant.domain.events import QRCodeGenerated, QRCodeRevoked
from restaurant_os_api.modules.restaurant.domain.exceptions import TableNotFoundError
from tests.unit.modules.restaurant.fakes import (
    FakeAsyncSession,
    FakeOutboxWriter,
    FakeResolveUserPermissionsUseCase,
    InMemoryBranchRepository,
    InMemoryQRCodeRepository,
    InMemoryTableRepository,
    fake_session_factory_returning,
)

TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAV"
OTHER_TENANT_ID = "01ARZ3NDEKTSV4RRFFQ69G5FAW"
RESTAURANT_ID = "01ARZ3NDEKTSV4RRFFQ6RESTX1"
BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH1"
OTHER_BRANCH_ID = "01ARZ3NDEKTSV4RRFFQ6BRNCH2"
TABLE_ZONE_ID = "01ARZ3NDEKTSV4RRFFQ6TZONE1"
TABLE_ID = "01ARZ3NDEKTSV4RRFFQ6TABLE1"
QR_CODE_ID = "01ARZ3NDEKTSV4RRFFQ6QRCOD1"


def _branch(**overrides) -> Branch:
    defaults = {
        "id": BRANCH_ID,
        "tenant_id": TENANT_ID,
        "restaurant_id": RESTAURANT_ID,
        "name": "Downtown",
        "status": BranchStatus.ACTIVE,
        "created_at": datetime.now(UTC),
        "address_id": None,
    }
    defaults.update(overrides)
    return Branch(**defaults)


def _table(**overrides) -> Table:
    defaults = {
        "id": TABLE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_zone_id": TABLE_ZONE_ID,
        "table_number": "12A",
        "capacity": 4,
        "status": TableStatus.AVAILABLE,
        "sync_version": 0,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return Table(**defaults)


def _qr_code(**overrides) -> QRCode:
    defaults = {
        "id": QR_CODE_ID,
        "tenant_id": TENANT_ID,
        "branch_id": BRANCH_ID,
        "table_id": TABLE_ID,
        "token": "existing-token",
        "status": QRCodeStatus.ACTIVE,
        "created_at": datetime.now(UTC),
    }
    defaults.update(overrides)
    return QRCode(**defaults)


def _session_factory():
    return fake_session_factory_returning(FakeAsyncSession())


class TestCreateQRCodeUseCase:
    def _use_case(
        self, table_repo, branch_repo, qr_code_repo, resolved, outbox
    ) -> CreateQRCodeUseCase:
        return CreateQRCodeUseCase(
            session_factory=_session_factory(),
            table_repository_factory=lambda _s: table_repo,
            branch_repository_factory=lambda _s: branch_repo,
            qr_code_repository_factory=lambda _s: qr_code_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
            outbox_writer_factory=lambda _s: outbox,
        )

    async def test_first_generation_creates_an_active_code_and_publishes_generated(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository()
        outbox = FakeOutboxWriter()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(table_repo, branch_repo, qr_code_repo, resolved, outbox)

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        assert result.status == "active"
        assert result.table_id == TABLE_ID
        assert result.branch_id == BRANCH_ID
        assert len(result.token) > 0
        assert len(outbox.published) == 1
        assert isinstance(outbox.published[0][1], QRCodeGenerated)

    async def test_the_token_is_opaque_and_not_the_qr_codes_own_id(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(
            table_repo, branch_repo, qr_code_repo, resolved, FakeOutboxWriter()
        )

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        assert result.token != result.id
        # ULIDs are 26 chars, Crockford Base32 -- a token this long and
        # from urlsafe-base64 alphabet is not mistakable for one.
        assert len(result.token) > 26

    async def test_two_consecutive_generations_produce_different_tokens(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(
            table_repo, branch_repo, qr_code_repo, resolved, FakeOutboxWriter()
        )

        first = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)
        second = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        assert first.token != second.token

    async def test_replacing_an_existing_active_code_revokes_the_previous_one(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository({QR_CODE_ID: _qr_code()})
        outbox = FakeOutboxWriter()
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(table_repo, branch_repo, qr_code_repo, resolved, outbox)

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        assert result.id != QR_CODE_ID
        assert result.status == "active"

        previous = await qr_code_repo.get_by_id(TENANT_ID, QR_CODE_ID)
        assert previous is not None
        assert previous.status == QRCodeStatus.REVOKED

        event_types = [type(e).__name__ for _t, e in outbox.published]
        assert event_types == ["QRCodeRevoked", "QRCodeGenerated"]
        revoked_event = outbox.published[0][1]
        assert isinstance(revoked_event, QRCodeRevoked)
        assert revoked_event.qr_code_id == QR_CODE_ID

    async def test_multiple_historical_codes_only_the_active_one_is_revoked(self) -> None:
        already_revoked_id = "01ARZ3NDEKTSV4RRFFQ6QRCOD2"
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository(
            {
                already_revoked_id: _qr_code(
                    id=already_revoked_id, token="old-1", status=QRCodeStatus.REVOKED
                ),
                QR_CODE_ID: _qr_code(token="old-2", status=QRCodeStatus.ACTIVE),
            }
        )
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.manage"}))
        use_case = self._use_case(
            table_repo, branch_repo, qr_code_repo, resolved, FakeOutboxWriter()
        )

        await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        all_codes = await qr_code_repo.list_for_table(TENANT_ID, TABLE_ID)
        assert len(all_codes) == 3
        statuses = {c.id: c.status for c in all_codes}
        assert statuses[already_revoked_id] == QRCodeStatus.REVOKED
        assert statuses[QR_CODE_ID] == QRCodeStatus.REVOKED

    async def test_raises_not_found_for_an_unknown_table(self) -> None:
        use_case = self._use_case(
            InMemoryTableRepository(),
            InMemoryBranchRepository(),
            InMemoryQRCodeRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"table.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_raises_not_found_for_a_cross_tenant_table(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(tenant_id=OTHER_TENANT_ID)})
        use_case = self._use_case(
            table_repo,
            InMemoryBranchRepository(),
            InMemoryQRCodeRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"table.manage"})),
            FakeOutboxWriter(),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_a_branch_scoped_manage_holder_can_generate_at_their_own_branch(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.manage"})})
        use_case = self._use_case(
            table_repo, branch_repo, InMemoryQRCodeRepository(), resolved, FakeOutboxWriter()
        )

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)
        assert result.status == "active"

    async def test_a_branch_scoped_manage_holder_cannot_generate_at_a_different_branch(
        self,
    ) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        branch_repo = InMemoryBranchRepository(
            {OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.manage"})})
        use_case = self._use_case(
            table_repo, branch_repo, InMemoryQRCodeRepository(), resolved, FakeOutboxWriter()
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_no_grant_at_all_is_denied(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            table_repo,
            branch_repo,
            InMemoryQRCodeRepository(),
            ResolvedPermissions(),
            FakeOutboxWriter(),
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_read_only_grant_is_insufficient(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.read"}))
        use_case = self._use_case(
            table_repo, branch_repo, InMemoryQRCodeRepository(), resolved, FakeOutboxWriter()
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)


class TestListQRCodesUseCase:
    def _use_case(self, table_repo, branch_repo, qr_code_repo, resolved) -> ListQRCodesUseCase:
        return ListQRCodesUseCase(
            session_factory=_session_factory(),
            table_repository_factory=lambda _s: table_repo,
            branch_repository_factory=lambda _s: branch_repo,
            qr_code_repository_factory=lambda _s: qr_code_repo,
            resolve_user_permissions=FakeResolveUserPermissionsUseCase(resolved=resolved),
        )

    async def test_returns_history_newest_first(self) -> None:
        older = _qr_code(
            id="01ARZ3NDEKTSV4RRFFQ6QRCOD2",
            token="older",
            status=QRCodeStatus.REVOKED,
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
        )
        newer = _qr_code(token="newer", created_at=datetime(2026, 6, 1, tzinfo=UTC))
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        qr_code_repo = InMemoryQRCodeRepository({older.id: older, newer.id: newer})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.read"}))
        use_case = self._use_case(table_repo, branch_repo, qr_code_repo, resolved)

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

        assert [c.id for c in result] == [newer.id, older.id]

    async def test_empty_history_for_a_table_with_no_codes(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(tenant_wide=frozenset({"table.read"}))
        use_case = self._use_case(table_repo, branch_repo, InMemoryQRCodeRepository(), resolved)

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)
        assert result == []

    async def test_raises_not_found_for_an_unknown_table(self) -> None:
        use_case = self._use_case(
            InMemoryTableRepository(),
            InMemoryBranchRepository(),
            InMemoryQRCodeRepository(),
            ResolvedPermissions(tenant_wide=frozenset({"table.read"})),
        )

        with pytest.raises(TableNotFoundError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_a_branch_scoped_read_holder_can_list_their_own_branchs_history(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.read"})})
        use_case = self._use_case(table_repo, branch_repo, InMemoryQRCodeRepository(), resolved)

        result = await use_case.execute(TENANT_ID, "user-1", TABLE_ID)
        assert result == []

    async def test_a_branch_scoped_read_holder_cannot_list_a_different_branchs_history(
        self,
    ) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table(branch_id=OTHER_BRANCH_ID)})
        branch_repo = InMemoryBranchRepository(
            {OTHER_BRANCH_ID: _branch(id=OTHER_BRANCH_ID, name="Uptown")}
        )
        resolved = ResolvedPermissions(by_branch={BRANCH_ID: frozenset({"table.read"})})
        use_case = self._use_case(table_repo, branch_repo, InMemoryQRCodeRepository(), resolved)

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)

    async def test_no_grant_at_all_is_denied(self) -> None:
        table_repo = InMemoryTableRepository({TABLE_ID: _table()})
        branch_repo = InMemoryBranchRepository({BRANCH_ID: _branch()})
        use_case = self._use_case(
            table_repo, branch_repo, InMemoryQRCodeRepository(), ResolvedPermissions()
        )

        with pytest.raises(PermissionDeniedError):
            await use_case.execute(TENANT_ID, "user-1", TABLE_ID)
