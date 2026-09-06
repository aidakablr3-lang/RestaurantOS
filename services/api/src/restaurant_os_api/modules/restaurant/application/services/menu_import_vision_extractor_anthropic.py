"""Claude implementation of ``VisionExtractor`` (menu_import_vision_extractor.py).

Anthropic's ``content`` is a list of typed blocks -- images and PDFs
each need their own block ``type`` ("image" vs "document"), and the
bytes must be base64-encoded into the JSON body ourselves. See
``menu_import_vision_extractor_gemini.py`` for the contrast: Gemini's
SDK collapses both into one ``Part.from_bytes`` call and encodes
internally.
"""

from __future__ import annotations

import base64

import anthropic

from restaurant_os_api.modules.restaurant.application.dto import ExtractedMenuRowDTO
from restaurant_os_api.modules.restaurant.application.services.menu_import_vision_extractor import (
    INSTRUCTIONS_TEMPLATE,
    PDF_MEDIA_TYPE,
    RESPONSE_SCHEMA,
    MenuImagePage,
    parse_rows_response,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportExtractionFailedError,
)

MODEL_ID = "claude-opus-5"


class AnthropicVisionExtractor:
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
        content.append({"type": "text", "text": INSTRUCTIONS_TEMPLATE.format(count=len(pages))})

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
                output_config={"format": {"type": "json_schema", "schema": RESPONSE_SCHEMA}},
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
            return parse_rows_response(text)
        except (StopIteration, KeyError, ValueError) as exc:
            raise MenuImportExtractionFailedError("received an unreadable response") from exc
