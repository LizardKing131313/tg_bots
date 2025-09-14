from __future__ import annotations

import time
from collections import defaultdict, deque
from collections.abc import Awaitable, Callable
from typing import Any

from aiogram import BaseMiddleware
from aiogram.types import CallbackQuery, Message, TelegramObject

from libs.common.aiogram.i18n import _
from libs.common.config import get_settings
from libs.common.logger import setup_logging


class RateLimitMiddleware(BaseMiddleware):

    def __init__(self, bot_name: str) -> None:
        super().__init__()
        setting = get_settings(bot_name=bot_name)
        self.limit = setting.rate_limit_per_user
        self.window = setting.rate_limit_window_sec
        self.log = setup_logging(bot_name)
        self.bucket: dict[int, deque[float]] = defaultdict(deque)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict,
    ) -> Any:  # noqa: ANN401
        if isinstance(event, Message | CallbackQuery):
            user_id = event.from_user.id if event.from_user else None
        else:
            user_id = data.get("event_from_user").id if data.get("event_from_user") else None

        if user_id is None:
            return await handler(event, data)

        now = time.monotonic()
        q = self.bucket[user_id]

        while q and now - q[0] > self.window:
            q.popleft()

        if len(q) >= self.limit:
            if isinstance(event, Message):
                await event.answer(_("user.limit"))
            elif isinstance(event, CallbackQuery) and event.message:
                await event.answer()
            return None

        q.append(now)
        return await handler(event, data)


rate_limit_middleware = RateLimitMiddleware

__all__ = ["rate_limit_middleware"]
