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

from collections.abc import Callable
from dataclasses import dataclass, replace

from restaurant_os_api.modules.restaurant.application.dto import (
    ExtractedMenuRowDTO,
    MenuImportConfidence,
    MenuImportExtractResultDTO,
)
from restaurant_os_api.modules.restaurant.application.services.menu_import_image_normalizer import (
    normalize_to_png,
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
    PNG_MEDIA_TYPE,
    MenuImagePage,
    VisionExtractor,
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
    def __init__(self, *, vision_extractor_factory: Callable[[], VisionExtractor] | None) -> None:
        # A factory, not an already-built extractor, so nothing is
        # constructed (no client, no auth check) unless a file in this
        # particular request actually needs vision extraction -- a
        # CSV/XLSX-only import works even with no vision provider
        # configured at all.
        self._vision_extractor_factory = vision_extractor_factory

    def execute(self, files: list[UploadedMenuFile]) -> MenuImportExtractResultDTO:
        vision_pages: list[MenuImagePage] = []
        rows: list[ExtractedMenuRowDTO] = []

        for file in files:
            if file.content_type == PDF_MEDIA_TYPE:
                vision_pages.append(MenuImagePage(media_type=PDF_MEDIA_TYPE, data=file.data))
            elif file.content_type.startswith("image/") or _looks_like_image_filename(
                file.filename
            ):
                # Re-encoded to PNG regardless of source format (AVIF,
                # HEIC, WEBP, ...) -- see the normalizer's own docstring
                # for why this isn't a format allow-list.
                png_data = normalize_to_png(file.filename, file.data)
                vision_pages.append(MenuImagePage(media_type=PNG_MEDIA_TYPE, data=png_data))
            elif file.content_type in _CSV_CONTENT_TYPES:
                rows.extend(parse_csv(file.data))
            elif file.content_type in _XLSX_CONTENT_TYPES:
                rows.extend(parse_xlsx(file.data))
            else:
                raise MenuImportUnsupportedFileError(file.filename, file.content_type)

        if vision_pages:
            if self._vision_extractor_factory is None:
                raise MenuImportNotConfiguredError()
            extractor = self._vision_extractor_factory()
            rows.extend(extractor.extract(vision_pages))

        return MenuImportExtractResultDTO(rows=[_normalize_price(row) for row in rows])


_IMAGE_EXTENSIONS = (
    ".jpg",
    ".jpeg",
    ".png",
    ".gif",
    ".webp",
    ".avif",
    ".heic",
    ".heif",
    ".bmp",
    ".tiff",
)


def _looks_like_image_filename(filename: str) -> bool:
    """Fallback for a browser/OS that sends a generic content-type
    (``application/octet-stream``) for a less common image format --
    seen in practice for AVIF and HEIC. The normalizer itself is the
    real validator; this only decides whether to attempt it."""
    return filename.lower().endswith(_IMAGE_EXTENSIONS)


def _normalize_price(row: ExtractedMenuRowDTO) -> ExtractedMenuRowDTO:
    raw_price = row.raw_price.strip()
    if not raw_price:
        return row

    price_amount = parse_menu_price(raw_price)
    if price_amount is not None:
        return replace(row, price_amount=price_amount)

    note = row.note or "Price text didn't match a known format -- check against the source."
    return replace(row, price_amount=None, confidence=MenuImportConfidence.LOW, note=note)
