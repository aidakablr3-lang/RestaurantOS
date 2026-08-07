"""Exports the running app's OpenAPI schema to docs/api/openapi.json.

FastAPI generates this schema from route/schema definitions already --
this script just writes it to a committed file so it's diffable in code
review and consumable by external tooling (client generators, API
documentation sites) without needing a running server. Regenerate and
commit whenever a route's request/response shape changes; nothing
enforces that automatically yet (see docs/RELEASE_CHECKLIST.md).

Usage:
    JWT_PRIVATE_KEY=dummy JWT_PUBLIC_KEY=dummy python scripts/export_openapi.py
"""

from __future__ import annotations

import json
from pathlib import Path

from restaurant_os_api.main import app

_OUTPUT_PATH = Path(__file__).resolve().parents[3] / "docs" / "api" / "openapi.json"


def main() -> None:
    schema = app.openapi()
    _OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    _OUTPUT_PATH.write_text(json.dumps(schema, indent=2, sort_keys=True) + "\n")
    print(f"Wrote {_OUTPUT_PATH}")


if __name__ == "__main__":
    main()
