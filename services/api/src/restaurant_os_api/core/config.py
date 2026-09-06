"""Application configuration.

Technical Architecture v2.0 SS5.1: a single ``Settings`` object, sourced
from environment variables, grouped into nested typed models so a
consumer only has to type-hint the subset it actually needs. Only the
settings needed by the identity module's login/refresh/logout slice are
defined here — later modules extend this file additively, they do not
replace it.
"""

from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

# Every nested BaseSettings class below needs its OWN `env_file`/`extra`
# -- pydantic-settings does not propagate the outer Settings class's
# model_config to a field typed as another BaseSettings, even when it's
# built via default_factory. Without this, a nested class silently reads
# only real process env vars and never the .env file at all (found the
# hard way: ANTHROPIC_API_KEY/GEMINI_API_KEY both sat in .env and were
# both silently ignored). `extra="ignore"` is required alongside
# `env_file` for the same reason as the outer class: once a nested class
# reads .env itself, it sees every other class's variables in that same
# file too and must not reject them as unknown.
_ENV_FILE_CONFIG = SettingsConfigDict(env_file=".env", extra="ignore")


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(**_ENV_FILE_CONFIG, env_prefix="DATABASE_")

    url: str = Field(
        default="postgresql+asyncpg://restaurantos:restaurantos@localhost:5432/restaurantos",
        description="Async SQLAlchemy connection URL for the primary database.",
    )
    pool_size: int = Field(default=10, ge=1)


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(**_ENV_FILE_CONFIG, env_prefix="JWT_")

    private_key: str = Field(
        description="RS256 private key (PEM). Required in every environment "
        "except local development, where a generated dev keypair is used."
    )
    public_key: str = Field(description="RS256 public key (PEM), matching private_key.")
    access_ttl_seconds: int = Field(default=900, description="15 minutes, per TAD v2.0 Group C.")
    refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, description="30 days.")
    issuer: str = Field(default="restaurantos")


class AnthropicSettings(BaseSettings):
    model_config = SettingsConfigDict(**_ENV_FILE_CONFIG, env_prefix="ANTHROPIC_")

    api_key: str | None = Field(
        default=None,
        description="Required only when MENU_IMPORT_VISION_PROVIDER=anthropic. Every "
        "other route works without it; menu import returns 503 if the selected "
        "provider's key is unset.",
    )


class GeminiSettings(BaseSettings):
    model_config = SettingsConfigDict(**_ENV_FILE_CONFIG, env_prefix="GEMINI_")

    api_key: str | None = Field(
        default=None,
        description="Required only when MENU_IMPORT_VISION_PROVIDER=gemini. Every "
        "other route works without it; menu import returns 503 if the selected "
        "provider's key is unset.",
    )


class Settings(BaseSettings):
    model_config = _ENV_FILE_CONFIG

    app_env: str = Field(default="development", alias="APP_ENV")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)  # type: ignore[arg-type]
    anthropic: AnthropicSettings = Field(default_factory=AnthropicSettings)
    gemini: GeminiSettings = Field(default_factory=GeminiSettings)
    menu_import_vision_provider: Literal["anthropic", "gemini"] = Field(
        default="anthropic",
        alias="MENU_IMPORT_VISION_PROVIDER",
        description="Which vision provider POST .../menu-imports/extract calls for "
        "photo/PDF extraction. A config value, not a plugin registry -- exactly one "
        "of AnthropicVisionExtractor/GeminiVisionExtractor is wired up at a time.",
    )
    # A plain, comma-separated `str` -- not `list[str]` -- because
    # pydantic-settings parses any complex-typed env var as JSON by
    # default, which rejects a plain comma-separated value outright.
    # `cors_allowed_origins` below does the splitting.
    cors_allowed_origins_csv: str = Field(
        default="http://localhost:3000",
        alias="CORS_ALLOWED_ORIGINS",
        description="Comma-separated browser origins allowed to call this "
        "API cross-origin (e.g. apps/admin-web's dev server).",
    )

    @property
    def cors_allowed_origins(self) -> list[str]:
        return [
            origin.strip() for origin in self.cors_allowed_origins_csv.split(",") if origin.strip()
        ]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached so Settings is parsed/validated exactly once per process
    (Technical Architecture v2.0 SS5.1: "fail-fast validation... instantiated
    once, injected via DI") rather than re-read from the environment on
    every request.
    """
    return Settings()
