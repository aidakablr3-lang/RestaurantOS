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

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class DatabaseSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="DATABASE_")

    url: str = Field(
        default="postgresql+asyncpg://restaurantos:restaurantos@localhost:5432/restaurantos",
        description="Async SQLAlchemy connection URL for the primary database.",
    )
    pool_size: int = Field(default=10, ge=1)


class JWTSettings(BaseSettings):
    model_config = SettingsConfigDict(env_prefix="JWT_")

    private_key: str = Field(
        description="RS256 private key (PEM). Required in every environment "
        "except local development, where a generated dev keypair is used."
    )
    public_key: str = Field(description="RS256 public key (PEM), matching private_key.")
    access_ttl_seconds: int = Field(default=900, description="15 minutes, per TAD v2.0 Group C.")
    refresh_ttl_seconds: int = Field(default=60 * 60 * 24 * 30, description="30 days.")
    issuer: str = Field(default="restaurantos")


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_env: str = Field(default="development", alias="APP_ENV")
    database: DatabaseSettings = Field(default_factory=DatabaseSettings)
    jwt: JWTSettings = Field(default_factory=JWTSettings)  # type: ignore[arg-type]


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return the process-wide Settings singleton.

    Cached so Settings is parsed/validated exactly once per process
    (Technical Architecture v2.0 SS5.1: "fail-fast validation... instantiated
    once, injected via DI") rather than re-read from the environment on
    every request.
    """
    return Settings()  # type: ignore[call-arg]
