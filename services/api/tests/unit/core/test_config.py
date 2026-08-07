"""Unit tests for ``Settings.cors_allowed_origins``.

Regression coverage for a defect found during Sprint 4.1 Step 3 browser
verification: the FastAPI app had no CORS middleware at all, so every
browser client (admin-web included) was blocked at the preflight
`OPTIONS` request with no `Access-Control-Allow-Origin` header. The env
var is deliberately a plain, comma-separated `str`
(`cors_allowed_origins_csv`), not `list[str]` -- pydantic-settings
parses any complex-typed env var as JSON by default, which rejects a
plain comma-separated value outright.
"""

from __future__ import annotations

from restaurant_os_api.core.config import Settings


def test_default_allows_the_local_admin_web_dev_server() -> None:
    settings = Settings()  # type: ignore[call-arg]
    assert settings.cors_allowed_origins == ["http://localhost:3000"]


def test_splits_a_comma_separated_env_value(monkeypatch) -> None:
    monkeypatch.setenv(
        "CORS_ALLOWED_ORIGINS", "http://localhost:3000,https://admin.restaurantos.example"
    )
    settings = Settings()  # type: ignore[call-arg]
    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "https://admin.restaurantos.example",
    ]


def test_ignores_stray_whitespace_and_empty_entries(monkeypatch) -> None:
    monkeypatch.setenv("CORS_ALLOWED_ORIGINS", " http://localhost:3000 , ,http://localhost:5173")
    settings = Settings()  # type: ignore[call-arg]
    assert settings.cors_allowed_origins == [
        "http://localhost:3000",
        "http://localhost:5173",
    ]
