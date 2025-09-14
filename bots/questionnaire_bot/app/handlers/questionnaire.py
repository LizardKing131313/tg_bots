from aiogram import Dispatcher, F
from aiogram.filters import Command
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message

from libs.common.aiogram.i18n import _
from libs.common.aiogram.linked_states_group import LinkedStatesGroup, SkippableState
from libs.common.middleware.keyboard_cleanup_middleware import answer_tracked, edit_tracked

from ..filters.i18n_text import I18nTextEquals
from ..keyboards.inline import QCb, kb_inline_step
from ..keyboards.reply import kb_reply_controls


class Form(LinkedStatesGroup):
    name = SkippableState()
    age = SkippableState()
    city = SkippableState(can_skip=True)


# ---- Утилиты ----
def _parse_age(text: str) -> int | None:
    text = text.strip()
    if not text.isdigit():
        return None
    n = int(text)
    return n if 1 <= n <= 120 else None


def text_by_state(state: SkippableState) -> str:
    return f"{state.order_number}/{Form.states_count()} — {_('form.ask.' + state.state_name)}"


def _cb_message_or_none(cb: CallbackQuery) -> Message | None:
    """Вернёт Message только если оно доступно (не Inaccessible и не None)."""
    msg = cb.message
    return msg if isinstance(msg, Message) else None


async def to_next_state(message: Message, context: FSMContext, next_state: SkippableState) -> None:
    await context.set_state(next_state)
    await answer_tracked(
        message,
        text_by_state(next_state),
        context,
        reply_markup=kb_inline_step(
            show_back=next_state.previous is not None,
            show_skip=next_state.can_skip,
            hint_key=next_state.state_name,
        ).as_markup(),
    )


async def finish(message: Message, state: FSMContext) -> None:
    data = await state.get_data()
    await state.clear()
    await message.answer(
        _("form.summary").format(
            name=data["name"], age=data["age"], city=data.get("city") or _("form.city.unknown")
        )
    )


async def get_current(state: FSMContext) -> SkippableState:
    return Form.from_value(await state.get_state())


# ---- Команды ----
async def cmd_form(message: Message, state: FSMContext) -> None:
    # показываем постоянную reply-клаву (Cancel/Restart)
    await message.answer(_("form.start"), reply_markup=kb_reply_controls())
    await to_next_state(message, state, Form.name)


async def cmd_restart(message: Message, state: FSMContext) -> None:
    await state.clear()
    await cmd_form(message, state)


async def cmd_cancel(message: Message, state: FSMContext) -> None:
    await state.clear()
    await message.answer(_("cancel.done"))


# ---- Шаги ввода ----
async def ask_name(message: Message, state: FSMContext) -> None:
    await state.update_data(name=message.text.strip())
    await to_next_state(message, state, Form.age)


async def ask_age(message: Message, state: FSMContext) -> None:
    age = _parse_age(message.text)
    if age is None:
        await message.answer(_("form.validation.age"))
        return
    await state.update_data(age=age)
    await to_next_state(message, state, Form.city)


async def ask_city(message: Message, state: FSMContext) -> None:
    await state.update_data(city=message.text.strip())
    await finish(message, state)


# ---- Обработчики inline-кнопок ----
async def cb_cancel(cb: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    msg = _cb_message_or_none(cb)
    if msg:
        await msg.answer(_("cancel.done"))
    await cb.answer()


async def cb_back(cb: CallbackQuery, state: FSMContext) -> None:
    current = await get_current(state)
    if current.previous is None:
        await cb.answer()
        return
    msg = _cb_message_or_none(cb)
    if not msg:
        await cb.answer()
        return
    await to_next_state(msg, state, current.previous)
    await cb.answer()


async def cb_skip(cb: CallbackQuery, state: FSMContext) -> None:
    current = await get_current(state)
    msg = _cb_message_or_none(cb)
    if not msg:
        await cb.answer()
        return
    if current.next is None:
        await finish(msg, state)
    else:
        await to_next_state(msg, state, current.next)
    await cb.answer()


async def cb_hint_show(cb: CallbackQuery, state: FSMContext, callback_data: QCb) -> None:
    current = await get_current(state)
    base = text_by_state(current)
    title = _("hint.title")
    hint = _(f"hint.{callback_data.hint_key or ''}")
    new_text = f"<b>{base}</b>\n\n<b>{title}</b>\n{hint}"
    await cb.answer()
    msg = _cb_message_or_none(cb)
    if not msg:
        return
    await control_hint(msg, new_text, callback_data, current, False)


async def cb_hint_hide(cb: CallbackQuery, state: FSMContext, callback_data: QCb) -> None:
    current = await get_current(state)
    msg = _cb_message_or_none(cb)
    if not msg:
        await cb.answer()
        return
    await control_hint(msg, f"<b>{text_by_state(current)}</b>", callback_data, current)


async def control_hint(
    message: Message, text: str, callback_data: QCb, state: SkippableState, hint_state: bool = True
) -> None:
    await edit_tracked(
        message,
        text,
        parse_mode="HTML",
        reply_markup=kb_inline_step(
            show_back=state.previous is not None,
            show_skip=state.can_skip,
            hint_key=callback_data.hint_key,
            hint_state=hint_state,
        ).as_markup(),
    )


def register(dp: Dispatcher) -> None:
    # команды
    dp.message.register(cmd_cancel, I18nTextEquals("action.cancel"))
    dp.message.register(cmd_restart, I18nTextEquals("action.restart"))
    dp.message.register(cmd_cancel, Command("cancel"))
    dp.message.register(cmd_restart, Command("restart"))

    dp.message.register(cmd_form, Command("start"))
    dp.message.register(cmd_form, Command("form"))

    # шаги
    dp.message.register(ask_name, Form.name, F.text.len() > 0)
    dp.message.register(ask_age, Form.age, F.text.len() > 0)
    dp.message.register(ask_city, Form.city, F.text.len() > 0)

    # inline-кнопки
    dp.callback_query.register(cb_back, QCb.filter(F.act == "back"))
    dp.callback_query.register(cb_skip, QCb.filter(F.act == "skip"))
    dp.callback_query.register(cb_cancel, QCb.filter(F.act == "cancel"))
    dp.callback_query.register(cb_hint_show, QCb.filter(F.act == "hint_show"))
    dp.callback_query.register(cb_hint_hide, QCb.filter(F.act == "hint_hide"))
