"""Application-layer DTOs for the menu-import feature (photo/PDF/CSV/XLSX
-> extracted rows -> reviewed -> committed).

``dietary_type``/``portion_label``/``pricing_unit`` on
``ExtractedMenuRowDTO`` are extraction-only -- there is deliberately no
matching column on ``MenuItem`` yet (see ``MenuImportCommitRowDTO``,
which has no such fields). The decision, made explicit rather than
discovered later: see three or four real client menus before committing
to a schema for these, rather than guessing the right shape from one.
``portion_label`` is folded into the persisted item name at commit time
instead (``CommitMenuImportUseCase``); ``dietary_type``/``pricing_unit``
are shown in the review grid and then simply dropped.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from enum import StrEnum


class MenuImportConfidence(StrEnum):
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@dataclass(frozen=True, slots=True)
class ExtractedMenuRowDTO:
    category: str
    name: str
    raw_price: str
    price_amount: Decimal | None
    confidence: MenuImportConfidence
    source_image_index: int | None = None
    dietary_type: str | None = None
    portion_label: str | None = None
    pricing_unit: str | None = None
    note: str | None = None


@dataclass(frozen=True, slots=True)
class MenuImportExtractResultDTO:
    rows: list[ExtractedMenuRowDTO] = field(default_factory=list)


@dataclass(frozen=True, slots=True)
class MenuImportCommitRowDTO:
    """A single reviewed-and-approved row, ready to persist.

    Deliberately narrower than ``ExtractedMenuRowDTO`` -- no
    ``dietary_type``/``pricing_unit``/``confidence``/``source_image_index``,
    since those either aren't persisted (see module docstring) or only
    ever mattered during review.
    """

    category: str
    name: str
    price_amount: Decimal
    portion_label: str | None = None


@dataclass(frozen=True, slots=True)
class CommitMenuImportRequestDTO:
    restaurant_id: str
    rows: list[MenuImportCommitRowDTO]


@dataclass(frozen=True, slots=True)
class CommitMenuImportResultDTO:
    categories_created: int
    items_created: int
