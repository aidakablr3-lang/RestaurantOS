"""ExtractMenuImportUseCase.

Routes each uploaded file to the vision pipeline (photos, PDF) or the
deterministic spreadsheet pipeline (CSV, XLSX) -- see
``menu_import_vision_extractor``/``menu_import_spreadsheet_parser`` for
why those are split rather than sent through one path. Every returned
row then goes through the exact same price-normalization step
regardless of which pipeline produced it, so "90/-" is parsed
identically whether it came from a photo or a spreadsheet cell.

Nothing here touches the database -- extraction produces rows for
review, never persists anything (``CommitMenuImportUseCase`` does that,
separately, only once the owner approves).
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from restaurant_os_api.modules.restaurant.application.dto import (
    ExtractedMenuRowDTO,
    MenuImportConfidence,
    MenuImportExtractResultDTO,
)
from restaurant_os_api.modules.restaurant.application.services.menu_import_price_parser import (
    parse_menu_price,
)
from restaurant_os_api.modules.restaurant.application.services.menu_import_spreadsheet_parser import (
    parse_csv,
    parse_xlsx,
)
from restaurant_os_api.modules.restaurant.application.services.menu_import_vision_extractor import (
    PDF_MEDIA_TYPE,
    SUPPORTED_IMAGE_MEDIA_TYPES,
    MenuImagePage,
    MenuImportVisionExtractor,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportNotConfiguredError,
    MenuImportUnsupportedFileError,
)

_CSV_CONTENT_TYPES = {"text/csv", "application/csv", "application/vnd.ms-excel"}
_XLSX_CONTENT_TYPES = {"application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"}


@dataclass(frozen=True, slots=True)
class UploadedMenuFile:
    filename: str
    content_type: str
    data: bytes


class ExtractMenuImportUseCase:
    def __init__(self, *, anthropic_api_key: str | None) -> None:
        self._anthropic_api_key = anthropic_api_key

    def execute(self, files: list[UploadedMenuFile]) -> MenuImportExtractResultDTO:
        vision_pages: list[MenuImagePage] = []
        rows: list[ExtractedMenuRowDTO] = []

        for file in files:
            if file.content_type in SUPPORTED_IMAGE_MEDIA_TYPES or (
                file.content_type == PDF_MEDIA_TYPE
            ):
                vision_pages.append(MenuImagePage(media_type=file.content_type, data=file.data))
            elif file.content_type in _CSV_CONTENT_TYPES:
                rows.extend(parse_csv(file.data))
            elif file.content_type in _XLSX_CONTENT_TYPES:
                rows.extend(parse_xlsx(file.data))
            else:
                raise MenuImportUnsupportedFileError(file.filename, file.content_type)

        if vision_pages:
            if not self._anthropic_api_key:
                raise MenuImportNotConfiguredError()
            extractor = MenuImportVisionExtractor(api_key=self._anthropic_api_key)
            rows.extend(extractor.extract(vision_pages))

        return MenuImportExtractResultDTO(rows=[_normalize_price(row) for row in rows])


def _normalize_price(row: ExtractedMenuRowDTO) -> ExtractedMenuRowDTO:
    raw_price = row.raw_price.strip()
    if not raw_price:
        return row

    price_amount = parse_menu_price(raw_price)
    if price_amount is not None:
        return replace(row, price_amount=price_amount)

    note = row.note or "Price text didn't match a known format -- check against the source."
    return replace(row, price_amount=None, confidence=MenuImportConfidence.LOW, note=note)
