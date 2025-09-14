from __future__ import annotations

import asyncio
from contextlib import suppress
from typing import Any

from aiogram import Dispatcher
from aiogram.exceptions import (
    TelegramBadRequest,
    TelegramForbiddenError,
    TelegramRetryAfter,
)
from aiogram.types import CallbackQuery, ErrorEvent, Message

from libs.common.aiogram.i18n import _
from libs.common.logger import setup_logging


def setup_error_handlers(bot_name: str, dp: Dispatcher) -> None:

    log = setup_logging(bot_name)

    def _minimal_update_info(event: ErrorEvent) -> dict[str, Any]:
        upd = getattr(event, "update", None)

        chat_id: int | None = None
        user_id: int | None = None
        cb_data: str | None = None

        if upd is None:
            return {"chat_id": chat_id, "user_id": user_id, "callback_data": cb_data}

        msg: Message | None = getattr(upd, "message", None)
        if msg:
            chat_id = getattr(getattr(msg, "chat", None), "id", None)
            user_id = getattr(getattr(msg, "from_user", None), "id", None)

        cb: CallbackQuery | None = getattr(upd, "callback_query", None)
        if cb:
            cb_msg: Message | None = getattr(cb, "message", None)
            if cb_msg and chat_id is None:
                chat_id = getattr(getattr(cb_msg, "chat", None), "id", None)
            if user_id is None:
                user_id = getattr(getattr(cb, "from_user", None), "id", None)
            cb_data = getattr(cb, "data", None)

        return {"chat_id": chat_id, "user_id": user_id, "callback_data": cb_data}

    async def _resolve_answer_target(event: ErrorEvent) -> Message | None:
        upd = getattr(event, "update", None)
        if upd is None:
            return None

        msg: Message | None = getattr(upd, "message", None)
        if msg:
            return msg

        cb: CallbackQuery | None = getattr(upd, "callback_query", None)
        if cb and isinstance(cb.message, Message):
            return cb.message

        return None

    def _exc_text(exc: Exception) -> str:
        msg = getattr(exc, "message", None)
        return str(msg if msg else exc)

    def _should_send_fallback(exc: Exception) -> bool:
        text = _exc_text(exc).lower()
        blocked_markers = ("bot was blocked by the user", "user is deactivated")
        chat_missing_markers = ("chat not found", "chat_id is empty")

        if any(m in text for m in blocked_markers):
            return False

        return all(m not in text for m in chat_missing_markers)

    @dp.errors()
    async def on_error(event: ErrorEvent, exception: Exception) -> bool:
        info = _minimal_update_info(event)

        match exception:
            case asyncio.CancelledError():
                log.debug("CancelledError %s", info)
                return True

            case TelegramRetryAfter() as e:
                secs: float = getattr(e, "retry_after", 1.0)
                log.warning("Rate limit: sleep=%s %s", secs, info)
                await asyncio.sleep(secs)
                return True

            case TelegramBadRequest() | TelegramForbiddenError():
                log.warning("Telegram error: %r %s", exception, info)
                return True

            case _:
                log.exception("Unhandled error while processing update %s", info)

                if _should_send_fallback(exception):
                    target = await _resolve_answer_target(event)
                    if target:
                        with suppress(Exception):
                            log.debug("Replying fallback %s", info)
                            await target.answer(_("user.fallback"))
                return True
