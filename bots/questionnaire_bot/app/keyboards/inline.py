from aiogram.filters.callback_data import CallbackData
from aiogram.utils.keyboard import InlineKeyboardBuilder

from libs.common.aiogram.i18n import _


class QCb(CallbackData, prefix="q"):
    act: str
    hint_key: str | None = None


def kb_inline_step(
    show_back: bool = True,
    show_skip: bool = False,
    hint_key: str | None = None,
    hint_state: bool = True,
) -> InlineKeyboardBuilder:
    kb = InlineKeyboardBuilder()
    if hint_key:
        visibility = "show" if hint_state else "hide"
        kb.button(
            text=_(f"action.hint.{visibility}"),
            callback_data=QCb(act=f"hint_{visibility}", hint_key=hint_key).pack(),
        )
    if show_back:
        kb.button(text=_("action.back"), callback_data=QCb(act="back").pack())
    if show_skip:
        kb.button(text=_("action.skip"), callback_data=QCb(act="skip").pack())
    kb.button(text=_("action.cancel"), callback_data=QCb(act="cancel").pack())
    kb.adjust(2, 1)  # две слева, одна строкой снизу
    return kb
