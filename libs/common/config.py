from __future__ import annotations

import inspect
import os
import re
from functools import cache
from pathlib import Path
from typing import Protocol

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


PROJECT_ROOT = Path(__file__).resolve().parents[2]


_SEP_SPLIT = re.compile(r"[\\/]+")


def _detect_bot_name_from_stack() -> str | None:
    for fr in inspect.stack():
        filename = str(getattr(fr, "filename", "") or "")
        if not filename:
            continue
        parts = [p for p in _SEP_SPLIT.split(filename) if p]
        for i, p in enumerate(parts):
            if p == "bots" and i + 2 < len(parts):
                bot = parts[i + 1]
                if "." in bot:
                    continue
                return bot
    return None


def select_env_file() -> Path:
    override = os.getenv("ENV_FILE")
    if override:
        return Path(override)

    bot = _detect_bot_name_from_stack()
    if bot:
        bot_env = PROJECT_ROOT / "bots" / bot / ".env"
        if bot_env.exists():
            return bot_env

    root_env = PROJECT_ROOT / ".env"
    return root_env if root_env.exists() else Path()


class Settings(Protocol):
    bot_token: str
    i18n_bot: str

    rate_limit_per_user: int
    rate_limit_window_sec: int

    def validate_token(self) -> None: ...


class AppSettings(BaseSettings):
    model_config = SettingsConfigDict(
        env_prefix="",
        env_file=str(select_env_file()),
        env_file_encoding="utf-8",
        extra="ignore",
    )

    bot_token: str | None = Field(default=None, alias="BOT_TOKEN")
    i18n_bot: str | None = Field(default=None, alias="I18N_BOT")

    rate_limit_per_user: int = Field(default=3, alias="RATE_LIMIT_PER_USER")
    rate_limit_window_sec: int = Field(default=1, alias="RATE_LIMIT_WINDOW_SEC")

    @model_validator(mode="after")
    def _fill_i18n_bot(self) -> AppSettings:
        detected = _detect_bot_name_from_stack() or "global"
        if self.i18n_bot is None:
            self.i18n_bot = detected
        elif self.i18n_bot != detected and detected != "global":
            raise ValueError(f"I18N_BOT='{self.i18n_bot}' не совпадает с каталогом '{detected}'")
        return self

    def validate_token(self) -> None:
        vv = (self.bot_token or "").strip()
        if not vv or vv.lower().startswith("put-your-telegram-bot-token-here"):
            raise RuntimeError(
                "BOT_TOKEN is not set (check .env). Set a real token instead of a placeholder."
            )


@cache
def get_settings(bot_name: str, strict: bool = True) -> Settings:
    settings = AppSettings()
    if strict:
        settings.validate_token()
    return settings
