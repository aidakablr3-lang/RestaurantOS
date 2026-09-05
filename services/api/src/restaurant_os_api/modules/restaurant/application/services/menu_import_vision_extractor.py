"""Claude vision extraction for the menu-import feature.

Sends every uploaded photo/PDF page of a physical menu card to Claude in
one message (not one call per page) so the model has full cross-page
context -- catching a category that continues across two photos, or
avoiding treating the same category name on two pages as two different
ones. Uses forced JSON-schema output (``output_config.format``) rather
than a free-text prompt, so a malformed response is a hard error here,
not a silent bad parse three layers up.

Deliberately does NOT normalize the extracted price text itself --
``rawPrice`` is required to be the price exactly as printed. Normalizing
"90/-" / "₹90" / "Rs. 120" into a plain number is `menu_import_price_parser`'s
job: a pure, independently-tested function, not something asked of the
model and trusted blind.
"""

from __future__ import annotations

import base64
import json
from dataclasses import dataclass
from typing import cast

import anthropic

from restaurant_os_api.modules.restaurant.application.dto import (
    ExtractedMenuRowDTO,
    MenuImportConfidence,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportExtractionFailedError,
)

MODEL_ID = "claude-opus-5"

SUPPORTED_IMAGE_MEDIA_TYPES = frozenset({"image/jpeg", "image/png", "image/webp", "image/gif"})
PDF_MEDIA_TYPE = "application/pdf"

_ROW_SCHEMA = {
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

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {"rows": {"type": "array", "items": _ROW_SCHEMA}},
    "required": ["rows"],
    "additionalProperties": False,
}

_INSTRUCTIONS_TEMPLATE = """You are extracting a structured list of menu items from \
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


class MenuImportVisionExtractor:
    def __init__(self, *, api_key: str) -> None:
        self._client = anthropic.Anthropic(api_key=api_key)

    def extract(self, pages: list[MenuImagePage]) -> list[ExtractedMenuRowDTO]:
        content: list[dict[str, object]] = []
        for page in pages:
            block_type = "document" if page.media_type == PDF_MEDIA_TYPE else "image"
            content.append(
                {
                    "type": block_type,
                    "source": {
                        "type": "base64",
                        "media_type": page.media_type,
                        "data": base64.standard_b64encode(page.data).decode("ascii"),
                    },
                }
            )
        content.append({"type": "text", "text": _INSTRUCTIONS_TEMPLATE.format(count=len(pages))})

        try:
            # The SDK's overloaded, heavily-TypedDict'd signature can't be
            # matched by a dynamically-built plain-dict payload without
            # importing every nested param type just for this one call --
            # the shape below is exactly the documented json_schema +
            # multi-image pattern, verified at runtime by the try/except
            # below rather than by mypy here.
            response = self._client.messages.create(  # type: ignore[call-overload]
                model=MODEL_ID,
                max_tokens=16000,
                output_config={"format": {"type": "json_schema", "schema": _RESPONSE_SCHEMA}},
                messages=[{"role": "user", "content": content}],
            )
        except anthropic.RateLimitError as exc:
            raise MenuImportExtractionFailedError("rate limited, try again shortly") from exc
        except anthropic.APIStatusError as exc:
            raise MenuImportExtractionFailedError(f"upstream error ({exc.status_code})") from exc
        except anthropic.APIConnectionError as exc:
            raise MenuImportExtractionFailedError("couldn't reach the extraction service") from exc

        try:
            text = next(b.text for b in response.content if b.type == "text")
            payload = json.loads(text)
            rows = payload["rows"]
        except (StopIteration, KeyError, json.JSONDecodeError) as exc:
            raise MenuImportExtractionFailedError("received an unreadable response") from exc

        return [_row_from_payload(row) for row in rows]


def _row_from_payload(row: dict[str, object]) -> ExtractedMenuRowDTO:
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
