"""Provider-agnostic pieces of the menu-import vision extraction step.

Sends every uploaded photo/PDF page of a physical menu card to the
vision model in one message (not one call per page) so the model has
full cross-page context -- catching a category that continues across
two photos, or avoiding treating the same category name on two pages as
two different ones. Uses forced JSON-schema output rather than a
free-text prompt, so a malformed response is a hard error here, not a
silent bad parse three layers up.

Deliberately does NOT normalize the extracted price text itself --
``rawPrice`` is required to be the price exactly as printed. Normalizing
"90/-" / "₹90" / "Rs. 120" into a plain number is
`menu_import_price_parser`'s job: a pure, independently-tested function,
not something asked of the model and trusted blind.

The provider split lives in ``menu_import_vision_extractor_anthropic.py``
and ``menu_import_vision_extractor_gemini.py`` -- both implement
``VisionExtractor`` and share the schema/prompt/row-parsing defined
here, so switching providers never means the two schemas silently
drift apart. ``ExtractMenuImportUseCase`` depends only on the
``VisionExtractor`` protocol; which concrete class it gets is a
dependency-wiring decision (``presentation/dependencies.py``), driven
by one config value (``MENU_IMPORT_VISION_PROVIDER``).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Protocol, cast

from restaurant_os_api.modules.restaurant.application.dto import (
    ExtractedMenuRowDTO,
    MenuImportConfidence,
)

# Every image, whatever its source format, is normalized to this by
# menu_import_image_normalizer before it reaches here -- see that
# module's docstring. PDFs are the one format both providers read
# natively, so they bypass normalization and keep their own media type.
PNG_MEDIA_TYPE = "image/png"
PDF_MEDIA_TYPE = "application/pdf"

ROW_SCHEMA = {
    "type": "object",
    "properties": {
        "category": {"type": "string"},
        "name": {"type": "string"},
        "rawPrice": {"type": "string"},
        "dietaryType": {"type": "string", "enum": ["veg", "non_veg", "unknown"]},
        "portionLabel": {"type": "string"},
        "pricingUnit": {"type": "string", "enum": ["plate", "piece", "unknown"]},
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
        "note": {"type": "string"},
        "sourceImageIndex": {"type": "integer"},
    },
    "required": [
        "category",
        "name",
        "rawPrice",
        "dietaryType",
        "portionLabel",
        "pricingUnit",
        "confidence",
        "note",
        "sourceImageIndex",
    ],
    "additionalProperties": False,
}

RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "items": ROW_SCHEMA}},
    "required": ["rows"],
    "additionalProperties": False,
}

INSTRUCTIONS_TEMPLATE = """You are extracting a structured list of menu items from \
{count} photo(s)/page(s) of a physical restaurant menu card. The source may be \
blurry, handwritten in places, or printed in two or more columns. Read \
section-by-section and column-by-column -- do not read across a column break as \
if it were one row, since two-column menus commonly place unrelated items side by \
side.

For every menu item found, across every page/photo provided, output one row with:

- category: the exact heading text this item is listed under on the menu (e.g. \
"Veg Starters", "Soups", "Main Course"). Use the menu's own wording verbatim -- do \
not invent, standardize, or translate a category name.
- name: the dish name exactly as printed, in its original script (Kannada, Hindi, \
Devanagari, or English) -- never transliterate or translate it.
- rawPrice: the price exactly as printed, character for character (e.g. "90/-", \
"₹120", "Rs. 150", "45"). Do not normalize, convert, or compute anything here. \
If a price is genuinely illegible or missing, use an empty string rather than \
guessing a number.
- dietaryType: "veg", "non_veg", or "unknown". Infer this from explicit markers (a \
green or red dot/square symbol, a "VEG"/"NON-VEG" section heading) when present. \
Use "unknown" rather than guessing when it isn't inferable from the source.
- portionLabel: if this dish is offered in more than one size/portion (e.g. Half \
and Full, or Regular and Large), output ONE ROW PER PORTION, each sharing the same \
name, with portionLabel set to that portion's label exactly as printed (e.g. \
"Half", "Full"). If the dish has only one size, use an empty string.
- pricingUnit: "piece", "plate", or "unknown". Use "piece" only when the menu \
explicitly says so (e.g. "per piece", "/pc"). Otherwise "unknown".
- confidence: "high", "medium", or "low" -- your own honest assessment of how \
certain you are this row is read correctly. Use "low" whenever the source text is \
blurry, obscured, or you are guessing at a character.
- note: a short explanation whenever confidence is not "high" (e.g. "price \
partially obscured", "handwriting uncertain"). Empty string when confidence is \
"high".
- sourceImageIndex: the 0-based index of which image/page, in the order provided \
below, this item was read from.

Do not skip an item because you are unsure of one field -- extract it with your \
best guess for that field and mark confidence low instead.
"""


@dataclass(frozen=True, slots=True)
class MenuImagePage:
    media_type: str
    data: bytes


class VisionExtractor(Protocol):
    def extract(self, pages: list[MenuImagePage]) -> list[ExtractedMenuRowDTO]: ...


def row_from_payload(row: dict[str, object]) -> ExtractedMenuRowDTO:
    """Shared between providers -- both are forced into ``RESPONSE_SCHEMA``,
    so both produce this exact same row shape."""
    return ExtractedMenuRowDTO(
        category=str(row["category"]),
        name=str(row["name"]),
        raw_price=str(row["rawPrice"]),
        price_amount=None,  # normalized later, uniformly, by the use case
        confidence=MenuImportConfidence(str(row["confidence"])),
        source_image_index=int(cast("int | str", row["sourceImageIndex"])),
        dietary_type=str(row["dietaryType"]) or None,
        portion_label=str(row["portionLabel"]) or None,
        pricing_unit=str(row["pricingUnit"]) or None,
        note=str(row["note"]) or None,
    )


def parse_rows_response(text: str) -> list[ExtractedMenuRowDTO]:
    """Shared response-JSON parsing -- both providers hand this a JSON
    string matching ``RESPONSE_SCHEMA``."""
    payload = json.loads(text)
    return [row_from_payload(row) for row in payload["rows"]]
