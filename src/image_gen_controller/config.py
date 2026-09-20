"""Runtime settings from the environment."""

from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    typesafe_api_key: str = Field(default="", description="TypeSafe API key")
    jev_model: str = Field(default="jev-1.13.0")
    jev_timeout_seconds: float = Field(default=8.0, ge=1.0, le=60.0)
    log_level: str = Field(default="INFO")
    host: str = Field(default="127.0.0.1")
    port: int = Field(default=8000, ge=1, le=65535)
    remaining_budget_usd: float = Field(default=0.05, ge=0.0)
    gemini_api_key: str = Field(default="")
    gemini_image_model_lite: str = Field(default="gemini-3.1-flash-lite-image")
    gemini_image_model_premium: str = Field(default="gemini-3-pro-image-preview")


def get_settings() -> Settings:
    return Settings()
