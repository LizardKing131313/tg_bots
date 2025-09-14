from aiogram.types import KeyboardButton, ReplyKeyboardMarkup

from libs.common.aiogram.i18n import _


def kb_reply_controls() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        keyboard=[
            [
                KeyboardButton(text=_("action.cancel")),
                KeyboardButton(text=_("action.restart")),
            ],
        ],
        resize_keyboard=True,
        one_time_keyboard=False,
        input_field_placeholder=_("input.placeholder"),
        selective=False,
    )
