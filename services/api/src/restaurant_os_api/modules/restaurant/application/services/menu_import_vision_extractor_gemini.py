"""Gemini implementation of ``VisionExtractor`` (menu_import_vision_extractor.py).

Simpler than the Anthropic implementation in two ways: one ``Part``
constructor covers both images and PDFs (no separate "document" block
type), and ``Part.from_bytes`` takes raw bytes directly -- no manual
base64 encoding into the request body.

``MODEL_ID`` below is a placeholder pending confirmation against a real
key via ``client.models.list()`` (the user explicitly asked not to pick
this from docs) -- do not treat it as verified until that check has
actually run.
"""

from __future__ import annotations

import json

from google import genai
from google.genai import errors as genai_errors
from google.genai import types

from restaurant_os_api.modules.restaurant.application.dto import ExtractedMenuRowDTO
from restaurant_os_api.modules.restaurant.application.services.menu_import_vision_extractor import (
    INSTRUCTIONS_TEMPLATE,
    RESPONSE_SCHEMA,
    MenuImagePage,
    parse_rows_response,
)
from restaurant_os_api.modules.restaurant.domain.exceptions import (
    MenuImportExtractionFailedError,
)

# PLACEHOLDER -- not yet confirmed against a real key. See module docstring.
MODEL_ID = "gemini-2.5-flash"


class GeminiVisionExtractor:
    def __init__(self, *, api_key: str, model: str = MODEL_ID) -> None:
        self._client = genai.Client(api_key=api_key)
        self._model = model

    def extract(self, pages: list[MenuImagePage]) -> list[ExtractedMenuRowDTO]:
        contents: list[types.Part | str] = [
            types.Part.from_bytes(data=page.data, mime_type=page.media_type) for page in pages
        ]
        contents.append(INSTRUCTIONS_TEMPLATE.format(count=len(pages)))

        try:
            # mypy's list invariance rejects list[Part | str] against the
            # SDK's own broader list[str | Image | File | FileDict | Part
            # | PartDict] parameter type, even though every element here
            # is a member of that union -- same category of mismatch as
            # menu_import_vision_extractor_anthropic.py's messages.create()
            # call (loosely-typed payload vs. a heavily-typed SDK signature).
            response = self._client.models.generate_content(
                model=self._model,
                contents=contents,  # type: ignore[arg-type]
                config=types.GenerateContentConfig(
                    response_mime_type="application/json",
                    response_json_schema=RESPONSE_SCHEMA,
                ),
            )
        except genai_errors.ClientError as exc:
            if exc.code == 429:
                raise MenuImportExtractionFailedError("rate limited, try again shortly") from exc
            raise MenuImportExtractionFailedError(f"upstream error ({exc.code})") from exc
        except genai_errors.ServerError as exc:
            raise MenuImportExtractionFailedError(f"upstream error ({exc.code})") from exc

        text = response.text
        if not text:
            raise MenuImportExtractionFailedError("received an empty response")
        try:
            return parse_rows_response(text)
        except (KeyError, json.JSONDecodeError) as exc:
            raise MenuImportExtractionFailedError("received an unreadable response") from exc
