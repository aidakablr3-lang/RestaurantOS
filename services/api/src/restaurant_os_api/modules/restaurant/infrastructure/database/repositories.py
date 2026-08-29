"""SQLAlchemy implementations of the restaurant module's domain ports.

Mirrors ``modules.identity.infrastructure.database.repositories``'s
conventions exactly: tenant-scoping and soft-delete filtering are
applied here, inside the repository, never left to individual callers
to remember. Each method maps between the ORM model (Infrastructure)
and the domain entity (Domain) explicitly.
"""

from __future__ import annotations

from sqlalchemy import delete, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from restaurant_os_api.core.ids import generate_ulid
from restaurant_os_api.modules.restaurant.domain.entities import (
    Address,
    Branch,
    BranchStatus,
    MenuCategory,
    MenuItem,
    MenuItemAvailability,
    MenuItemBranchPrice,
    MenuItemStation,
    Modifier,
    ModifierGroup,
    ModifierSelectionType,
    OperatingHours,
    QRCode,
    QRCodeStatus,
    Reservation,
    ReservationStatus,
    Restaurant,
    RestaurantStatus,
    Table,
    TableStatus,
    TableZone,
)
from restaurant_os_api.modules.restaurant.infrastructure.database.models import (
    AddressModel,
    BranchModel,
    MenuCategoryModel,
    MenuItemAvailabilityModel,
    MenuItemBranchPriceModel,
    MenuItemModel,
    MenuItemModifierGroupModel,
    ModifierGroupModel,
    ModifierModel,
    OperatingHoursModel,
    QRCodeModel,
    ReservationModel,
    RestaurantModel,
    TableModel,
    TableZoneModel,
)


def _restaurant_from_model(model: RestaurantModel) -> Restaurant:
    return Restaurant(
        id=model.id,
        tenant_id=model.tenant_id,
        legal_name=model.legal_name,
        display_name=model.display_name,
        default_currency_code=model.default_currency_code,
        status=RestaurantStatus(model.status),
        created_at=model.created_at,
    )


def _address_from_model(model: AddressModel) -> Address:
    return Address(
        id=model.id,
        tenant_id=model.tenant_id,
        created_at=model.created_at,
        line1=model.line1,
        city=model.city,
        country_code=model.country_code,
        postal_code=model.postal_code,
    )


def _branch_from_model(model: BranchModel) -> Branch:
    return Branch(
        id=model.id,
        tenant_id=model.tenant_id,
        restaurant_id=model.restaurant_id,
        name=model.name,
        status=BranchStatus(model.status),
        created_at=model.created_at,
        address_id=model.address_id,
        allow_negative_stock=model.allow_negative_stock,
        gstin=model.gstin,
        invoice_prefix=model.invoice_prefix,
    )


def _operating_hours_from_model(model: OperatingHoursModel) -> OperatingHours:
    return OperatingHours(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        day_of_week=model.day_of_week,
        is_closed=model.is_closed,
        created_at=model.created_at,
        opens_at=model.opens_at,
        closes_at=model.closes_at,
    )


def _table_zone_from_model(model: TableZoneModel) -> TableZone:
    return TableZone(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        name=model.name,
        display_order=model.display_order,
        created_at=model.created_at,
    )


def _table_from_model(model: TableModel) -> Table:
    return Table(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        table_zone_id=model.table_zone_id,
        table_number=model.table_number,
        capacity=model.capacity,
        status=TableStatus(model.status),
        sync_version=model.sync_version,
        created_at=model.created_at,
    )


def _qr_code_from_model(model: QRCodeModel) -> QRCode:
    return QRCode(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        table_id=model.table_id,
        token=model.token,
        status=QRCodeStatus(model.status),
        created_at=model.created_at,
    )


def _menu_category_from_model(model: MenuCategoryModel) -> MenuCategory:
    return MenuCategory(
        id=model.id,
        tenant_id=model.tenant_id,
        restaurant_id=model.restaurant_id,
        name=model.name,
        display_order=model.display_order,
        created_at=model.created_at,
    )


def _menu_item_from_model(model: MenuItemModel) -> MenuItem:
    return MenuItem(
        id=model.id,
        tenant_id=model.tenant_id,
        menu_category_id=model.menu_category_id,
        name=model.name,
        price_amount=model.price_amount,
        currency_code=model.currency_code,
        is_available=model.is_available,
        display_order=model.display_order,
        created_at=model.created_at,
        recipe_id=model.recipe_id,
        station=MenuItemStation(model.station),
    )


def _modifier_group_from_model(model: ModifierGroupModel) -> ModifierGroup:
    return ModifierGroup(
        id=model.id,
        tenant_id=model.tenant_id,
        name=model.name,
        selection_type=ModifierSelectionType(model.selection_type),
        created_at=model.created_at,
    )


def _modifier_from_model(model: ModifierModel) -> Modifier:
    return Modifier(
        id=model.id,
        tenant_id=model.tenant_id,
        modifier_group_id=model.modifier_group_id,
        name=model.name,
        created_at=model.created_at,
        price_delta=model.price_delta,
    )


def _menu_item_branch_price_from_model(model: MenuItemBranchPriceModel) -> MenuItemBranchPrice:
    return MenuItemBranchPrice(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        menu_item_id=model.menu_item_id,
        price_amount=model.price_amount,
        effective_from=model.effective_from,
        created_at=model.created_at,
        effective_to=model.effective_to,
    )


def _menu_item_availability_from_model(model: MenuItemAvailabilityModel) -> MenuItemAvailability:
    return MenuItemAvailability(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        menu_item_id=model.menu_item_id,
        is_available=model.is_available,
        effective_from=model.effective_from,
        created_at=model.created_at,
        effective_to=model.effective_to,
    )


def _reservation_from_model(model: ReservationModel) -> Reservation:
    return Reservation(
        id=model.id,
        tenant_id=model.tenant_id,
        branch_id=model.branch_id,
        party_size=model.party_size,
        requested_at=model.requested_at,
        status=ReservationStatus(model.status),
        sync_version=model.sync_version,
        created_at=model.created_at,
        table_id=model.table_id,
        customer_id=model.customer_id,
    )


class SQLAlchemyRestaurantRepository:
    """Implements ``RestaurantRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, restaurant_id: str) -> Restaurant | None:
        stmt = select(RestaurantModel).where(
            RestaurantModel.id == restaurant_id,
            RestaurantModel.tenant_id == tenant_id,
            RestaurantModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _restaurant_from_model(model) if model is not None else None

    async def create(self, restaurant: Restaurant) -> Restaurant:
        model = RestaurantModel(
            id=restaurant.id,
            tenant_id=restaurant.tenant_id,
            legal_name=restaurant.legal_name,
            display_name=restaurant.display_name,
            default_currency_code=restaurant.default_currency_code,
            status=restaurant.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _restaurant_from_model(model)

    async def update(self, restaurant: Restaurant) -> Restaurant:
        stmt = (
            update(RestaurantModel)
            .where(
                RestaurantModel.id == restaurant.id,
                RestaurantModel.tenant_id == restaurant.tenant_id,
            )
            .values(
                legal_name=restaurant.legal_name,
                display_name=restaurant.display_name,
                default_currency_code=restaurant.default_currency_code,
                status=restaurant.status.value,
            )
        )
        await self._session.execute(stmt)
        return restaurant

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Restaurant], int]:
        filters = (RestaurantModel.tenant_id == tenant_id, RestaurantModel.deleted_at.is_(None))
        count_stmt = select(func.count()).select_from(RestaurantModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(RestaurantModel)
            .where(*filters)
            .order_by(RestaurantModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_restaurant_from_model(m) for m in models], total


class SQLAlchemyAddressRepository:
    """Implements ``AddressRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, address_id: str) -> Address | None:
        stmt = select(AddressModel).where(
            AddressModel.id == address_id,
            AddressModel.tenant_id == tenant_id,
            AddressModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _address_from_model(model) if model is not None else None

    async def create(self, address: Address) -> Address:
        model = AddressModel(
            id=address.id,
            tenant_id=address.tenant_id,
            line1=address.line1,
            city=address.city,
            country_code=address.country_code,
            postal_code=address.postal_code,
        )
        self._session.add(model)
        await self._session.flush()
        return _address_from_model(model)

    async def update(self, address: Address) -> Address:
        stmt = (
            update(AddressModel)
            .where(AddressModel.id == address.id, AddressModel.tenant_id == address.tenant_id)
            .values(
                line1=address.line1,
                city=address.city,
                country_code=address.country_code,
                postal_code=address.postal_code,
            )
        )
        await self._session.execute(stmt)
        return address


class SQLAlchemyBranchRepository:
    """Implements ``BranchRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, branch_id: str) -> Branch | None:
        stmt = select(BranchModel).where(
            BranchModel.id == branch_id,
            BranchModel.tenant_id == tenant_id,
            BranchModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _branch_from_model(model) if model is not None else None

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> Branch | None:
        stmt = select(BranchModel).where(
            BranchModel.tenant_id == tenant_id,
            BranchModel.restaurant_id == restaurant_id,
            BranchModel.name == name,
            BranchModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _branch_from_model(model) if model is not None else None

    async def get_by_gstin_and_invoice_prefix(
        self, tenant_id: str, gstin: str, invoice_prefix: str, *, exclude_branch_id: str | None = None
    ) -> Branch | None:
        stmt = select(BranchModel).where(
            BranchModel.tenant_id == tenant_id,
            BranchModel.gstin == gstin,
            BranchModel.invoice_prefix == invoice_prefix,
            BranchModel.deleted_at.is_(None),
        )
        if exclude_branch_id is not None:
            stmt = stmt.where(BranchModel.id != exclude_branch_id)
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _branch_from_model(model) if model is not None else None

    async def create(self, branch: Branch) -> Branch:
        model = BranchModel(
            id=branch.id,
            tenant_id=branch.tenant_id,
            restaurant_id=branch.restaurant_id,
            address_id=branch.address_id,
            name=branch.name,
            status=branch.status.value,
            gstin=branch.gstin,
            invoice_prefix=branch.invoice_prefix,
        )
        self._session.add(model)
        await self._session.flush()
        return _branch_from_model(model)

    async def update(self, branch: Branch) -> Branch:
        stmt = (
            update(BranchModel)
            .where(BranchModel.id == branch.id, BranchModel.tenant_id == branch.tenant_id)
            .values(
                address_id=branch.address_id,
                name=branch.name,
                status=branch.status.value,
                gstin=branch.gstin,
                invoice_prefix=branch.invoice_prefix,
            )
        )
        await self._session.execute(stmt)
        return branch

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Branch], int]:
        filters = (
            BranchModel.tenant_id == tenant_id,
            BranchModel.restaurant_id == restaurant_id,
            BranchModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(BranchModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(BranchModel)
            .where(*filters)
            .order_by(BranchModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_branch_from_model(m) for m in models], total

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[Branch], int]:
        """Every branch across every restaurant the tenant owns --
        backs the tenant-wide-grant case of ``ListAccessibleBranchesUseCase``
        (Step 4 Decision Lock, Decision 2: a tenant-wide permission holder
        sees all of the tenant's branches, not just one restaurant's)."""
        filters = (BranchModel.tenant_id == tenant_id, BranchModel.deleted_at.is_(None))
        count_stmt = select(func.count()).select_from(BranchModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(BranchModel)
            .where(*filters)
            .order_by(BranchModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_branch_from_model(m) for m in models], total

    async def list_by_ids(self, tenant_id: str, branch_ids: frozenset[str]) -> list[Branch]:
        """Backs the branch-scoped-grant case of
        ``ListAccessibleBranchesUseCase`` -- resolves the caller's own
        specific, unioned set of granted branch ids (RBAC's
        ``ResolvedPermissions.branch_ids_with()``) into full ``Branch``
        rows, still tenant-filtered as the belt-and-suspenders check
        (RLS is the other half)."""
        if not branch_ids:
            return []
        stmt = select(BranchModel).where(
            BranchModel.tenant_id == tenant_id,
            BranchModel.id.in_(branch_ids),
            BranchModel.deleted_at.is_(None),
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_branch_from_model(m) for m in models]


class SQLAlchemyOperatingHoursRepository:
    """Implements ``OperatingHoursRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_for_branch(self, tenant_id: str, branch_id: str) -> list[OperatingHours]:
        stmt = (
            select(OperatingHoursModel)
            .where(
                OperatingHoursModel.tenant_id == tenant_id,
                OperatingHoursModel.branch_id == branch_id,
                OperatingHoursModel.deleted_at.is_(None),
            )
            .order_by(OperatingHoursModel.day_of_week)
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_operating_hours_from_model(m) for m in models]

    async def replace_for_branch(
        self, tenant_id: str, branch_id: str, rows: list[OperatingHours]
    ) -> None:
        await self._session.execute(
            delete(OperatingHoursModel).where(
                OperatingHoursModel.tenant_id == tenant_id,
                OperatingHoursModel.branch_id == branch_id,
            )
        )
        for row in rows:
            self._session.add(
                OperatingHoursModel(
                    id=row.id,
                    tenant_id=tenant_id,
                    branch_id=branch_id,
                    day_of_week=row.day_of_week,
                    opens_at=row.opens_at,
                    closes_at=row.closes_at,
                    is_closed=row.is_closed,
                )
            )
        await self._session.flush()


class SQLAlchemyTableZoneRepository:
    """Implements ``TableZoneRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, table_zone_id: str) -> TableZone | None:
        stmt = select(TableZoneModel).where(
            TableZoneModel.id == table_zone_id,
            TableZoneModel.tenant_id == tenant_id,
            TableZoneModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _table_zone_from_model(model) if model is not None else None

    async def get_by_branch_id_and_name(
        self, tenant_id: str, branch_id: str, name: str
    ) -> TableZone | None:
        stmt = select(TableZoneModel).where(
            TableZoneModel.tenant_id == tenant_id,
            TableZoneModel.branch_id == branch_id,
            TableZoneModel.name == name,
            TableZoneModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _table_zone_from_model(model) if model is not None else None

    async def create(self, table_zone: TableZone) -> TableZone:
        model = TableZoneModel(
            id=table_zone.id,
            tenant_id=table_zone.tenant_id,
            branch_id=table_zone.branch_id,
            name=table_zone.name,
            display_order=table_zone.display_order,
        )
        self._session.add(model)
        await self._session.flush()
        return _table_zone_from_model(model)

    async def update(self, table_zone: TableZone) -> TableZone:
        stmt = (
            update(TableZoneModel)
            .where(
                TableZoneModel.id == table_zone.id, TableZoneModel.tenant_id == table_zone.tenant_id
            )
            .values(name=table_zone.name, display_order=table_zone.display_order)
        )
        await self._session.execute(stmt)
        return table_zone

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[TableZone], int]:
        filters = (
            TableZoneModel.tenant_id == tenant_id,
            TableZoneModel.branch_id == branch_id,
            TableZoneModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(TableZoneModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(TableZoneModel)
            .where(*filters)
            .order_by(TableZoneModel.display_order)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_table_zone_from_model(m) for m in models], total


class SQLAlchemyTableRepository:
    """Implements ``TableRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, table_id: str) -> Table | None:
        stmt = select(TableModel).where(
            TableModel.id == table_id,
            TableModel.tenant_id == tenant_id,
            TableModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _table_from_model(model) if model is not None else None

    async def get_by_branch_id_and_table_number(
        self, tenant_id: str, branch_id: str, table_number: str
    ) -> Table | None:
        stmt = select(TableModel).where(
            TableModel.tenant_id == tenant_id,
            TableModel.branch_id == branch_id,
            TableModel.table_number == table_number,
            TableModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _table_from_model(model) if model is not None else None

    async def create(self, table: Table) -> Table:
        model = TableModel(
            id=table.id,
            tenant_id=table.tenant_id,
            branch_id=table.branch_id,
            table_zone_id=table.table_zone_id,
            table_number=table.table_number,
            capacity=table.capacity,
            status=table.status.value,
            sync_version=table.sync_version,
        )
        self._session.add(model)
        await self._session.flush()
        return _table_from_model(model)

    async def update(self, table: Table) -> Table:
        stmt = (
            update(TableModel)
            .where(TableModel.id == table.id, TableModel.tenant_id == table.tenant_id)
            .values(
                table_zone_id=table.table_zone_id,
                table_number=table.table_number,
                capacity=table.capacity,
                status=table.status.value,
                sync_version=table.sync_version,
            )
        )
        await self._session.execute(stmt)
        return table

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Table], int]:
        filters = (
            TableModel.tenant_id == tenant_id,
            TableModel.branch_id == branch_id,
            TableModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(TableModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(TableModel)
            .where(*filters)
            .order_by(TableModel.table_number)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_table_from_model(m) for m in models], total

    async def list_for_table_zone(self, tenant_id: str, table_zone_id: str) -> list[Table]:
        stmt = select(TableModel).where(
            TableModel.tenant_id == tenant_id,
            TableModel.table_zone_id == table_zone_id,
            TableModel.deleted_at.is_(None),
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_table_from_model(m) for m in models]


class SQLAlchemyQRCodeRepository:
    """Implements ``QRCodeRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, qr_code_id: str) -> QRCode | None:
        stmt = select(QRCodeModel).where(
            QRCodeModel.id == qr_code_id,
            QRCodeModel.tenant_id == tenant_id,
            QRCodeModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _qr_code_from_model(model) if model is not None else None

    async def get_by_token(self, token: str) -> QRCode | None:
        stmt = select(QRCodeModel).where(
            QRCodeModel.token == token, QRCodeModel.deleted_at.is_(None)
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _qr_code_from_model(model) if model is not None else None

    async def create(self, qr_code: QRCode) -> QRCode:
        model = QRCodeModel(
            id=qr_code.id,
            tenant_id=qr_code.tenant_id,
            branch_id=qr_code.branch_id,
            table_id=qr_code.table_id,
            token=qr_code.token,
            status=qr_code.status.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _qr_code_from_model(model)

    async def update(self, qr_code: QRCode) -> QRCode:
        stmt = (
            update(QRCodeModel)
            .where(QRCodeModel.id == qr_code.id, QRCodeModel.tenant_id == qr_code.tenant_id)
            .values(status=qr_code.status.value)
        )
        await self._session.execute(stmt)
        return qr_code

    async def list_for_table(self, tenant_id: str, table_id: str) -> list[QRCode]:
        stmt = (
            select(QRCodeModel)
            .where(
                QRCodeModel.tenant_id == tenant_id,
                QRCodeModel.table_id == table_id,
                QRCodeModel.deleted_at.is_(None),
            )
            .order_by(QRCodeModel.created_at.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_qr_code_from_model(m) for m in models]


class SQLAlchemyMenuCategoryRepository:
    """Implements ``MenuCategoryRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, menu_category_id: str) -> MenuCategory | None:
        stmt = select(MenuCategoryModel).where(
            MenuCategoryModel.id == menu_category_id,
            MenuCategoryModel.tenant_id == tenant_id,
            MenuCategoryModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _menu_category_from_model(model) if model is not None else None

    async def get_by_restaurant_id_and_name(
        self, tenant_id: str, restaurant_id: str, name: str
    ) -> MenuCategory | None:
        stmt = select(MenuCategoryModel).where(
            MenuCategoryModel.tenant_id == tenant_id,
            MenuCategoryModel.restaurant_id == restaurant_id,
            MenuCategoryModel.name == name,
            MenuCategoryModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _menu_category_from_model(model) if model is not None else None

    async def create(self, menu_category: MenuCategory) -> MenuCategory:
        model = MenuCategoryModel(
            id=menu_category.id,
            tenant_id=menu_category.tenant_id,
            restaurant_id=menu_category.restaurant_id,
            name=menu_category.name,
            display_order=menu_category.display_order,
        )
        self._session.add(model)
        await self._session.flush()
        return _menu_category_from_model(model)

    async def update(self, menu_category: MenuCategory) -> MenuCategory:
        stmt = (
            update(MenuCategoryModel)
            .where(
                MenuCategoryModel.id == menu_category.id,
                MenuCategoryModel.tenant_id == menu_category.tenant_id,
            )
            .values(name=menu_category.name, display_order=menu_category.display_order)
        )
        await self._session.execute(stmt)
        return menu_category

    async def list_for_restaurant(
        self, tenant_id: str, restaurant_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuCategory], int]:
        filters = (
            MenuCategoryModel.tenant_id == tenant_id,
            MenuCategoryModel.restaurant_id == restaurant_id,
            MenuCategoryModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(MenuCategoryModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(MenuCategoryModel)
            .where(*filters)
            .order_by(MenuCategoryModel.display_order)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_menu_category_from_model(m) for m in models], total


class SQLAlchemyMenuItemRepository:
    """Implements ``MenuItemRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, menu_item_id: str) -> MenuItem | None:
        stmt = select(MenuItemModel).where(
            MenuItemModel.id == menu_item_id,
            MenuItemModel.tenant_id == tenant_id,
            MenuItemModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _menu_item_from_model(model) if model is not None else None

    async def create(self, menu_item: MenuItem) -> MenuItem:
        model = MenuItemModel(
            id=menu_item.id,
            tenant_id=menu_item.tenant_id,
            menu_category_id=menu_item.menu_category_id,
            name=menu_item.name,
            price_amount=menu_item.price_amount,
            currency_code=menu_item.currency_code,
            is_available=menu_item.is_available,
            display_order=menu_item.display_order,
            recipe_id=menu_item.recipe_id,
            station=menu_item.station.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _menu_item_from_model(model)

    async def update(self, menu_item: MenuItem) -> MenuItem:
        stmt = (
            update(MenuItemModel)
            .where(MenuItemModel.id == menu_item.id, MenuItemModel.tenant_id == menu_item.tenant_id)
            .values(
                name=menu_item.name,
                price_amount=menu_item.price_amount,
                currency_code=menu_item.currency_code,
                is_available=menu_item.is_available,
                display_order=menu_item.display_order,
                recipe_id=menu_item.recipe_id,
                station=menu_item.station.value,
            )
        )
        await self._session.execute(stmt)
        return menu_item

    async def list_for_category(
        self, tenant_id: str, menu_category_id: str, *, offset: int, limit: int
    ) -> tuple[list[MenuItem], int]:
        filters = (
            MenuItemModel.tenant_id == tenant_id,
            MenuItemModel.menu_category_id == menu_category_id,
            MenuItemModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(MenuItemModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(MenuItemModel)
            .where(*filters)
            .order_by(MenuItemModel.display_order)
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_menu_item_from_model(m) for m in models], total


class SQLAlchemyModifierGroupRepository:
    """Implements ``ModifierGroupRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, modifier_group_id: str) -> ModifierGroup | None:
        stmt = select(ModifierGroupModel).where(
            ModifierGroupModel.id == modifier_group_id,
            ModifierGroupModel.tenant_id == tenant_id,
            ModifierGroupModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _modifier_group_from_model(model) if model is not None else None

    async def create(self, modifier_group: ModifierGroup) -> ModifierGroup:
        model = ModifierGroupModel(
            id=modifier_group.id,
            tenant_id=modifier_group.tenant_id,
            name=modifier_group.name,
            selection_type=modifier_group.selection_type.value,
        )
        self._session.add(model)
        await self._session.flush()
        return _modifier_group_from_model(model)

    async def update(self, modifier_group: ModifierGroup) -> ModifierGroup:
        stmt = (
            update(ModifierGroupModel)
            .where(
                ModifierGroupModel.id == modifier_group.id,
                ModifierGroupModel.tenant_id == modifier_group.tenant_id,
            )
            .values(name=modifier_group.name, selection_type=modifier_group.selection_type.value)
        )
        await self._session.execute(stmt)
        return modifier_group

    async def list_for_tenant(
        self, tenant_id: str, *, offset: int, limit: int
    ) -> tuple[list[ModifierGroup], int]:
        filters = (
            ModifierGroupModel.tenant_id == tenant_id,
            ModifierGroupModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(ModifierGroupModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(ModifierGroupModel)
            .where(*filters)
            .order_by(ModifierGroupModel.created_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_modifier_group_from_model(m) for m in models], total


class SQLAlchemyModifierRepository:
    """Implements ``ModifierRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, modifier_id: str) -> Modifier | None:
        stmt = select(ModifierModel).where(
            ModifierModel.id == modifier_id,
            ModifierModel.tenant_id == tenant_id,
            ModifierModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _modifier_from_model(model) if model is not None else None

    async def create(self, modifier: Modifier) -> Modifier:
        model = ModifierModel(
            id=modifier.id,
            tenant_id=modifier.tenant_id,
            modifier_group_id=modifier.modifier_group_id,
            name=modifier.name,
            price_delta=modifier.price_delta,
        )
        self._session.add(model)
        await self._session.flush()
        return _modifier_from_model(model)

    async def update(self, modifier: Modifier) -> Modifier:
        stmt = (
            update(ModifierModel)
            .where(ModifierModel.id == modifier.id, ModifierModel.tenant_id == modifier.tenant_id)
            .values(name=modifier.name, price_delta=modifier.price_delta)
        )
        await self._session.execute(stmt)
        return modifier

    async def list_for_group(self, tenant_id: str, modifier_group_id: str) -> list[Modifier]:
        stmt = select(ModifierModel).where(
            ModifierModel.tenant_id == tenant_id,
            ModifierModel.modifier_group_id == modifier_group_id,
            ModifierModel.deleted_at.is_(None),
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_modifier_from_model(m) for m in models]


class SQLAlchemyMenuItemModifierGroupRepository:
    """Implements ``MenuItemModifierGroupRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def list_modifier_group_ids_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> frozenset[str]:
        stmt = select(MenuItemModifierGroupModel.modifier_group_id).where(
            MenuItemModifierGroupModel.tenant_id == tenant_id,
            MenuItemModifierGroupModel.menu_item_id == menu_item_id,
        )
        ids = (await self._session.execute(stmt)).scalars().all()
        return frozenset(ids)

    async def replace_for_menu_item(
        self, tenant_id: str, menu_item_id: str, modifier_group_ids: frozenset[str]
    ) -> None:
        await self._session.execute(
            delete(MenuItemModifierGroupModel).where(
                MenuItemModifierGroupModel.tenant_id == tenant_id,
                MenuItemModifierGroupModel.menu_item_id == menu_item_id,
            )
        )
        for modifier_group_id in modifier_group_ids:
            self._session.add(
                MenuItemModifierGroupModel(
                    id=generate_ulid(),
                    tenant_id=tenant_id,
                    menu_item_id=menu_item_id,
                    modifier_group_id=modifier_group_id,
                )
            )
        await self._session.flush()


class SQLAlchemyMenuItemBranchPriceRepository:
    """Implements ``MenuItemBranchPriceRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemBranchPrice | None:
        stmt = select(MenuItemBranchPriceModel).where(
            MenuItemBranchPriceModel.id == row_id,
            MenuItemBranchPriceModel.tenant_id == tenant_id,
            MenuItemBranchPriceModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _menu_item_branch_price_from_model(model) if model is not None else None

    async def create(self, row: MenuItemBranchPrice) -> MenuItemBranchPrice:
        model = MenuItemBranchPriceModel(
            id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            menu_item_id=row.menu_item_id,
            price_amount=row.price_amount,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        self._session.add(model)
        await self._session.flush()
        return _menu_item_branch_price_from_model(model)

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemBranchPrice]:
        stmt = (
            select(MenuItemBranchPriceModel)
            .where(
                MenuItemBranchPriceModel.tenant_id == tenant_id,
                MenuItemBranchPriceModel.menu_item_id == menu_item_id,
                MenuItemBranchPriceModel.deleted_at.is_(None),
            )
            .order_by(MenuItemBranchPriceModel.effective_from.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_menu_item_branch_price_from_model(m) for m in models]


class SQLAlchemyMenuItemAvailabilityRepository:
    """Implements ``MenuItemAvailabilityRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, row_id: str) -> MenuItemAvailability | None:
        stmt = select(MenuItemAvailabilityModel).where(
            MenuItemAvailabilityModel.id == row_id,
            MenuItemAvailabilityModel.tenant_id == tenant_id,
            MenuItemAvailabilityModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _menu_item_availability_from_model(model) if model is not None else None

    async def create(self, row: MenuItemAvailability) -> MenuItemAvailability:
        model = MenuItemAvailabilityModel(
            id=row.id,
            tenant_id=row.tenant_id,
            branch_id=row.branch_id,
            menu_item_id=row.menu_item_id,
            is_available=row.is_available,
            effective_from=row.effective_from,
            effective_to=row.effective_to,
        )
        self._session.add(model)
        await self._session.flush()
        return _menu_item_availability_from_model(model)

    async def list_for_menu_item(
        self, tenant_id: str, menu_item_id: str
    ) -> list[MenuItemAvailability]:
        stmt = (
            select(MenuItemAvailabilityModel)
            .where(
                MenuItemAvailabilityModel.tenant_id == tenant_id,
                MenuItemAvailabilityModel.menu_item_id == menu_item_id,
                MenuItemAvailabilityModel.deleted_at.is_(None),
            )
            .order_by(MenuItemAvailabilityModel.effective_from.desc())
        )
        models = (await self._session.execute(stmt)).scalars().all()
        return [_menu_item_availability_from_model(m) for m in models]


class SQLAlchemyReservationRepository:
    """Implements ``ReservationRepository``."""

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def get_by_id(self, tenant_id: str, reservation_id: str) -> Reservation | None:
        stmt = select(ReservationModel).where(
            ReservationModel.id == reservation_id,
            ReservationModel.tenant_id == tenant_id,
            ReservationModel.deleted_at.is_(None),
        )
        model = (await self._session.execute(stmt)).scalar_one_or_none()
        return _reservation_from_model(model) if model is not None else None

    async def create(self, reservation: Reservation) -> Reservation:
        model = ReservationModel(
            id=reservation.id,
            tenant_id=reservation.tenant_id,
            branch_id=reservation.branch_id,
            table_id=reservation.table_id,
            customer_id=reservation.customer_id,
            party_size=reservation.party_size,
            requested_at=reservation.requested_at,
            status=reservation.status.value,
            sync_version=reservation.sync_version,
        )
        self._session.add(model)
        await self._session.flush()
        return _reservation_from_model(model)

    async def update(self, reservation: Reservation) -> Reservation:
        stmt = (
            update(ReservationModel)
            .where(
                ReservationModel.id == reservation.id,
                ReservationModel.tenant_id == reservation.tenant_id,
            )
            .values(
                table_id=reservation.table_id,
                customer_id=reservation.customer_id,
                party_size=reservation.party_size,
                status=reservation.status.value,
                sync_version=reservation.sync_version,
            )
        )
        await self._session.execute(stmt)
        return reservation

    async def list_for_branch(
        self, tenant_id: str, branch_id: str, *, offset: int, limit: int
    ) -> tuple[list[Reservation], int]:
        filters = (
            ReservationModel.tenant_id == tenant_id,
            ReservationModel.branch_id == branch_id,
            ReservationModel.deleted_at.is_(None),
        )
        count_stmt = select(func.count()).select_from(ReservationModel).where(*filters)
        total = (await self._session.execute(count_stmt)).scalar_one()

        page_stmt = (
            select(ReservationModel)
            .where(*filters)
            .order_by(ReservationModel.requested_at.desc())
            .offset(offset)
            .limit(limit)
        )
        models = (await self._session.execute(page_stmt)).scalars().all()
        return [_reservation_from_model(m) for m in models], total


__all__ = [
    "SQLAlchemyAddressRepository",
    "SQLAlchemyBranchRepository",
    "SQLAlchemyMenuCategoryRepository",
    "SQLAlchemyMenuItemAvailabilityRepository",
    "SQLAlchemyMenuItemBranchPriceRepository",
    "SQLAlchemyMenuItemModifierGroupRepository",
    "SQLAlchemyMenuItemRepository",
    "SQLAlchemyModifierGroupRepository",
    "SQLAlchemyModifierRepository",
    "SQLAlchemyOperatingHoursRepository",
    "SQLAlchemyQRCodeRepository",
    "SQLAlchemyReservationRepository",
    "SQLAlchemyRestaurantRepository",
    "SQLAlchemyTableRepository",
    "SQLAlchemyTableZoneRepository",
]
