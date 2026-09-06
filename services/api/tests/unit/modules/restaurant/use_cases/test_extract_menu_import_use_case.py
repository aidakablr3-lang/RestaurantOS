"""Unit tests for ExtractMenuImportUseCase -- a fake VisionExtractor
stands in for either real provider, proving the use case only depends
on the VisionExtractor protocol, never on which concrete class
implements it."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from restaurant_os_api.modules.restaurant.application.dto import (
    ExtractedMenuRowDTO,
    MenuImportConfidence,
)
from restaurant_os_api.modules.restaurant.application.services.menu_import_vision_extractor import (
    MenuImagePage,
)
from restaurant_os_api.modules.restaurant.application.use_cases import UploadedMenuFile
from restaurant_os_api.modules.restaurant.application.use_cases.extract_menu_import import (
    ExtractMenuImportUseCase,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportNotConfiguredError,
)


def _png_bytes() -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (2, 2), color="blue").save(buffer, format="PNG")
    return buffer.getvalue()


class FakeVisionExtractor:
    """Stands in for AnthropicVisionExtractor/GeminiVisionExtractor --
    both, and this fake, only need to satisfy VisionExtractor."""

    def __init__(self, rows: list[ExtractedMenuRowDTO]) -> None:
        self.rows = rows
        self.received_pages: list[MenuImagePage] | None = None

    def extract(self, pages: list[MenuImagePage]) -> list[ExtractedMenuRowDTO]:
        self.received_pages = pages
        return self.rows


def _row(**overrides: object) -> ExtractedMenuRowDTO:
    defaults: dict[str, object] = {
        "category": "Soups",
        "name": "Tomato Soup",
        "raw_price": "90/-",
        "price_amount": None,
        "confidence": MenuImportConfidence.HIGH,
        "source_image_index": 0,
        "dietary_type": None,
        "portion_label": None,
        "pricing_unit": None,
        "note": None,
    }
    defaults.update(overrides)
    return ExtractedMenuRowDTO(**defaults)  # type: ignore[arg-type]


def test_csv_only_import_works_with_no_vision_provider_configured() -> None:
    use_case = ExtractMenuImportUseCase(vision_extractor_factory=None)
    csv_data = b"Item,Price\nTomato Soup,90\n"
    result = use_case.execute(
        [UploadedMenuFile(filename="menu.csv", content_type="text/csv", data=csv_data)]
    )
    assert len(result.rows) == 1
    assert result.rows[0].name == "Tomato Soup"


def test_raises_not_configured_when_a_photo_needs_vision_but_none_is_wired_up() -> None:
    use_case = ExtractMenuImportUseCase(vision_extractor_factory=None)
    with pytest.raises(MenuImportNotConfiguredError):
        use_case.execute(
            [UploadedMenuFile(filename="menu.png", content_type="image/png", data=_png_bytes())]
        )


def test_delegates_to_whichever_vision_extractor_the_factory_provides() -> None:
    fake = FakeVisionExtractor(rows=[_row(raw_price="90/-")])
    use_case = ExtractMenuImportUseCase(vision_extractor_factory=lambda: fake)

    result = use_case.execute(
        [UploadedMenuFile(filename="menu.png", content_type="image/png", data=_png_bytes())]
    )

    assert fake.received_pages is not None
    assert len(fake.received_pages) == 1
    assert len(result.rows) == 1
    # price normalization still applies uniformly on top of whatever the
    # (fake, or either real) extractor returns
    assert str(result.rows[0].price_amount) == "90.00"
