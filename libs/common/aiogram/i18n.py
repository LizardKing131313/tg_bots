from __future__ import annotations

from functools import cache
from pathlib import Path

from aiogram.types import TelegramObject
from aiogram.utils.i18n import I18n, gettext as _
from aiogram.utils.i18n.middleware import I18nMiddleware

from libs.common.logger import setup_logging
from libs.common.root_resolver import resolve_root


def _resolve_locales_dir(project_root: Path, bot_name: str) -> Path:
    log = setup_logging(bot_name)

    cache_dir = project_root / ".i18n_cache" / bot_name / "locales"
    bot_dir = project_root / "bots" / bot_name / "locales"
    global_dir = project_root / "locales"

    if cache_dir.exists():
        log.debug("Real i18n cache found")
        return cache_dir
    if bot_dir.exists():
        log.warn("Real i18n cache not found. Fallback to bot *.po locales")
        return bot_dir
    if global_dir.exists():
        log.warn("Real i18n cache not found. Fallback to root *.po locales")
        return global_dir

    error = "Locales not found. Checked:\n"
    f" - {cache_dir}\n"
    f" - {bot_dir}\n"
    f" - {global_dir}\n"
    "Create locales or build cache first."

    log.exception(error)
    raise FileNotFoundError(error)


class SimpleI18nMiddleware(I18nMiddleware):
    async def get_locale(self, event: TelegramObject, data: dict) -> str:
        user = data.get("event_from_user")
        code = getattr(user, "language_code", None) if user else None
        return code or "en"


@cache
def create_i18n(bot_name: str, project_root: Path | None) -> SimpleI18nMiddleware:
    log = setup_logging(bot_name)
    log.debug(f"Creating locales for {bot_name}")

    root = project_root or resolve_root()
    log.debug(f"App root {root}")

    i18n_dir = _resolve_locales_dir(root, bot_name)
    i18n = I18n(path=str(i18n_dir), default_locale="en", domain="messages")
    log.debug("I18n created")

    return SimpleI18nMiddleware(i18n)


__all__ = ["_", "create_i18n"]
