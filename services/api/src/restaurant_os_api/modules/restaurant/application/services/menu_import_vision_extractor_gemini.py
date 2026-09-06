"""Gemini implementation of ``VisionExtractor`` (menu_import_vision_extractor.py).

Simpler than the Anthropic implementation in two ways: one ``Part``
constructor covers both images and PDFs (no separate "document" block
type), and ``Part.from_bytes`` takes raw bytes directly -- no manual
base64 encoding into the request body.

``MODEL_ID`` was picked from real calls against a live key
(2026-09-06), not from docs or ``client.models.list()`` alone -- the
model list includes models the key cannot actually use, which only
shows up by calling them:

- ``gemini-2.5-pro`` / ``gemini-2.5-flash`` (the GA "stability bar"
  choice, matching a pinned ``claude-opus-*`` ID) -- both 404
  "no longer available to new users" on this key, each redirecting to
  a specific newer model in the error message itself.
- ``gemini-3.1-pro-preview`` (the "pro" reasoning tier, matching the
  Anthropic side's Opus-not-Sonnet choice) -- listed as available, but
  429s with an explicit `limit: 0` free-tier quota for the whole
  `gemini-3.1-pro` metric family. Not "rate limited, retry later" --
  a hard tier wall.
- ``gemini-3.6-flash`` -- the one model in this generation that actually
  completes a call on this key, confirmed against both a plain prompt
  and the real ``RESPONSE_SCHEMA`` (enums, ``additionalProperties:
  false``, nested array -- the parts flagged as risky -- included).

So this is the flash tier, not pro, despite the Anthropic side using
Opus -- not a matched reasoning-tier choice, a "this is what the key
can actually run" one. If billing is upgraded past the free tier later,
re-run this same probe (call each candidate model for real, don't just
read `client.models.list()`) before assuming a "pro" model is usable.
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

MODEL_ID = "gemini-3.6-flash"


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
