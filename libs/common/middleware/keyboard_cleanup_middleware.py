from __future__ import annotations

from collections.abc import Awaitable, Callable
from contextvars import ContextVar
from typing import Any

from aiogram import BaseMiddleware
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, InlineKeyboardMarkup, Message, TelegramObject

from libs.common.logger import setup_logging


SKIP_INLINE_CLEANUP: ContextVar[bool] = ContextVar("skip_inline_cleanup", default=False)


class KeyboardCleanupMiddleware(BaseMiddleware):

    def __init__(self, *, bot_name: str) -> None:
        super().__init__()
        self.log = setup_logging(bot_name)

    async def __call__(
        self,
        handler: Callable[[TelegramObject, dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: dict[str, Any],
    ) -> Any:  # noqa: ANN401
        state: FSMContext | None = data.get("state")
        bot = data["bot"]

        # --- Message branch: перед вызовом хендлера убираем прошлую клавиатуру ---
        if isinstance(event, Message):
            if state:
                st = await state.get_data()
                last_id: int | None = st.get("last_inline_msg_id")
                if last_id:
                    try:
                        await bot.edit_message_reply_markup(
                            chat_id=event.chat.id,
                            message_id=last_id,
                            reply_markup=None,
                        )
                    except TelegramBadRequest:
                        pass
                    finally:
                        await state.update_data(last_inline_msg_id=None)

            result = await handler(event, data)

            # после хендлера переносим next → last
            if state:
                st = await state.get_data()
                next_id: int | None = st.get("next_inline_msg_id")
                if next_id:
                    await state.update_data(last_inline_msg_id=next_id, next_inline_msg_id=None)

            return result

        # --- Если это не CallbackQuery — просто пробрасываем дальше ---
        if not isinstance(event, CallbackQuery):
            return await handler(event, data)

        # --- CallbackQuery branch ---
        cq: CallbackQuery = event

        token = SKIP_INLINE_CLEANUP.set(False)
        try:
            result = await handler(cq, data)
        finally:
            skip = SKIP_INLINE_CLEANUP.get()
            SKIP_INLINE_CLEANUP.reset(token)

        if not skip:
            try:
                if cq.message is not None:
                    await bot.edit_message_reply_markup(
                        chat_id=cq.message.chat.id,
                        message_id=cq.message.message_id,
                        reply_markup=None,
                    )
                elif cq.inline_message_id is not None:
                    await bot.edit_message_reply_markup(
                        inline_message_id=cq.inline_message_id,
                        reply_markup=None,
                    )
                # если нет ни message, ни inline_message_id — чистить нечего
            except TelegramBadRequest:
                pass
            else:
                # если почистили именно то сообщение, что мы помнили — обнулим стейт
                if state and cq.message is not None:
                    st = await state.get_data()
                    if st.get("last_inline_msg_id") == cq.message.message_id:
                        await state.update_data(last_inline_msg_id=None)

        # переносим next → last (на случай если отправляли новую клаву из хендлера)
        if state:
            st = await state.get_data()
            next_inline_id: int | None = st.get("next_inline_msg_id")
            if next_inline_id:
                await state.update_data(last_inline_msg_id=next_inline_id, next_inline_msg_id=None)

        return result


async def answer_tracked(
    message: Message,
    text: str,
    state: FSMContext,
    reply_markup: InlineKeyboardMarkup | None = None,
    **kwargs: Any,  # noqa: ANN401
) -> Message:
    msg = await message.answer(text, reply_markup=reply_markup, **kwargs)
    if reply_markup is not None:
        await state.update_data(next_inline_msg_id=msg.message_id)
    return msg


async def edit_tracked(
    message: Message,
    text: str,
    **kwargs: Any,  # noqa: ANN401
) -> Message | bool:
    SKIP_INLINE_CLEANUP.set(True)
    return await message.edit_text(text, **kwargs)


keyboard_cleanup_middleware = KeyboardCleanupMiddleware

__all__ = ["answer_tracked", "edit_tracked", "keyboard_cleanup_middleware"]
