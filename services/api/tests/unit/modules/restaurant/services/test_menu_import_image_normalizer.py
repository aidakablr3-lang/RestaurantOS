"""Unit tests for normalize_to_png -- generates its own tiny fixture
images with Pillow rather than shipping binary fixture files."""

from __future__ import annotations

import io

import pytest
from PIL import Image

from restaurant_os_api.modules.restaurant.application.services.menu_import_image_normalizer import (
    normalize_to_png,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportUnsupportedFileError,
)


def _encode(fmt: str, mode: str = "RGB") -> bytes:
    image = Image.new(mode, (4, 4), color="red")
    buffer = io.BytesIO()
    image.save(buffer, format=fmt)
    return buffer.getvalue()


@pytest.mark.parametrize("fmt", ["JPEG", "PNG", "WEBP", "BMP", "GIF"])
def test_normalizes_common_formats_to_a_decodable_png(fmt: str) -> None:
    result = normalize_to_png("photo", _encode(fmt))
    with Image.open(io.BytesIO(result)) as decoded:
        assert decoded.format == "PNG"
        assert decoded.size == (4, 4)


def test_flattens_a_palette_mode_image_to_rgb() -> None:
    result = normalize_to_png("photo", _encode("GIF", mode="P"))
    with Image.open(io.BytesIO(result)) as decoded:
        assert decoded.mode == "RGB"


def test_raises_for_bytes_that_are_not_a_decodable_image() -> None:
    with pytest.raises(MenuImportUnsupportedFileError):
        normalize_to_png("not-a-photo.txt", b"this is definitely not an image")
