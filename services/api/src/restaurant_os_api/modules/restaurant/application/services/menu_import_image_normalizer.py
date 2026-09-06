"""Normalizes every uploaded photo to PNG before it reaches Claude.

Real menu photos arrive in whatever format the sending device/app used --
AVIF from a phone gallery or social-media export, HEIC from an iPhone,
WEBP, BMP, whatever -- not just the plain JPEG/PNG a clean test sample
would use. Rather than maintain and keep re-guessing an allow-list of
"formats Claude's vision input accepts today", this decodes anything
Pillow can open and always re-encodes as PNG, so the vision extractor
only ever has to handle one known-good image media type. PDFs bypass
this entirely -- Claude reads those natively.

``pillow_heif.register_heif_opener()`` must run before any ``Image.open``
call for HEIC/HEIF (iPhone photos) to decode; it's registered at import
time here, once per process.
"""

from __future__ import annotations

import io

import pillow_heif
from PIL import Image, UnidentifiedImageError

from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportUnsupportedFileError,
)

pillow_heif.register_heif_opener()


def normalize_to_png(filename: str, data: bytes) -> bytes:
    """Decode an image in any format Pillow supports and re-encode as PNG.

    Raises ``MenuImportUnsupportedFileError`` if the bytes aren't a
    decodable image at all (not a format problem this function can fix --
    a genuinely corrupt or non-image file).
    """
    try:
        with Image.open(io.BytesIO(data)) as image:
            # Flatten to RGB -- a PNG with an alpha channel is fine for
            # Claude, but some source formats (CMYK JPEGs, palette-mode
            # GIFs) don't round-trip cleanly through a naive re-encode
            # without this.
            rgb_image = image.convert("RGB")
            buffer = io.BytesIO()
            rgb_image.save(buffer, format="PNG")
            return buffer.getvalue()
    except UnidentifiedImageError as exc:
        raise MenuImportUnsupportedFileError(filename, "unrecognized image format") from exc
