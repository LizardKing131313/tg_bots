from __future__ import annotations

import asyncio
import importlib
from collections.abc import Awaitable, Callable
from types import ModuleType
from typing import Any

import pytest

from tests.conftest import (
    FakeCallbackQuery,
    FakeDispatcher,
    FakeErrorEvent,
    FakeMessage,
    FakeUpdate,
    MockLogger,
)


HandlerType = Callable[[FakeErrorEvent, Exception], Awaitable[bool]]


ErrorHandler = Callable[[], tuple[ModuleType, FakeDispatcher, HandlerType, Any]]


@pytest.fixture
def import_module(monkeypatch: pytest.MonkeyPatch, setup_logging: MockLogger) -> ErrorHandler:

    def _import() -> tuple[ModuleType, FakeDispatcher, HandlerType, Any]:
        module = importlib.import_module("libs.common.aiogram.error_handler")

        monkeypatch.setattr(module, "setup_logging", lambda _: setup_logging, raising=True)
        monkeypatch.setattr(module, "_", lambda s, *a, **kw: s, raising=True)

        from aiogram import Dispatcher

        dp: FakeDispatcher = Dispatcher()
        module.setup_error_handlers("bot", dp)
        handler: HandlerType | None = dp._handler
        assert handler is not None, "Handler не зарегистрировался через @dp.errors()"
        return module, dp, handler, setup_logging

    return _import


@pytest.fixture
def event_with_message() -> FakeErrorEvent:
    return FakeErrorEvent(FakeUpdate(message=FakeMessage()))


@pytest.fixture
def event_with_callback() -> FakeErrorEvent:
    return FakeErrorEvent(FakeUpdate(callback_query=FakeCallbackQuery(data="hello")))


@pytest.fixture
def event_without_target() -> FakeErrorEvent:
    return FakeErrorEvent(FakeUpdate(message=None, callback_query=None))


@pytest.fixture
def event_with_both() -> FakeErrorEvent:
    return FakeErrorEvent(
        FakeUpdate(message=FakeMessage(), callback_query=FakeCallbackQuery(data="hi"))
    )


@pytest.mark.asyncio
async def test_cancelled_error_branch(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    _, __, handler, logger = import_module()
    # noinspection PyTypeChecker
    ok: bool = await handler(event_with_message, asyncio.CancelledError())
    assert ok is True
    assert any("CancelledError" in str(args[0]) for args, _ in logger.debug_calls)


@pytest.mark.asyncio
async def test_retry_after_branch(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    module, __, handler, logger = import_module()

    slept: list[float] = []

    async def fake_sleep(x: float) -> None:
        slept.append(x)

    monkeypatch.setattr(module.asyncio, "sleep", fake_sleep)
    exc = module.TelegramRetryAfter(2.5)
    ok: bool = await handler(event_with_message, exc)
    assert ok is True
    assert slept == [2.5]
    assert any("Rate limit" in str(args[0]) for args, _ in logger.warning_calls)


@pytest.mark.asyncio
async def test_bad_request_branch(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    module, __, handler, logger = import_module()
    exc = module.TelegramBadRequest("some bad request")
    # noinspection DuplicatedCode
    ok: bool = await handler(event_with_message, exc)
    assert ok is True
    assert any("Telegram error" in str(args[0]) for args, _ in logger.warning_calls)
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None
    assert event_with_message.update.message.answered == []


@pytest.mark.asyncio
async def test_forbidden_blocked_no_fallback(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    module, __, handler, logger = import_module()
    exc = module.TelegramForbiddenError("bot was blocked by the user")
    # noinspection DuplicatedCode
    ok: bool = await handler(event_with_message, exc)
    assert ok is True
    assert any("Telegram error" in str(args[0]) for args, _ in logger.warning_calls)
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None
    assert event_with_message.update.message.answered == []


@pytest.mark.asyncio
async def test_unhandled_with_message_fallback_sent(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    _, __, handler, logger = import_module()
    ok: bool = await handler(event_with_message, RuntimeError("boom"))
    assert ok is True
    assert any("Unhandled error" in str(args[0]) for args, _ in logger.exception_calls)
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None
    assert event_with_message.update.message.answered == ["user.fallback"]


@pytest.mark.asyncio
async def test_unhandled_with_callback_fallback_sent(
    import_module: ErrorHandler, event_with_callback: FakeErrorEvent
) -> None:
    _, __, handler, ___ = import_module()
    ok: bool = await handler(event_with_callback, RuntimeError("another boom"))
    assert ok is True
    assert event_with_callback.update is not None
    assert event_with_callback.update.callback_query is not None
    assert event_with_callback.update.callback_query.message is not None
    assert event_with_callback.update.callback_query.message.answered == ["user.fallback"]


@pytest.mark.asyncio
async def test_unhandled_no_target(
    import_module: ErrorHandler, event_without_target: FakeErrorEvent
) -> None:
    _, __, handler, logger = import_module()
    ok: bool = await handler(event_without_target, RuntimeError("boom without target"))
    assert ok is True
    assert any("Unhandled error" in str(args[0]) for args, _ in logger.exception_calls)  # type: ignore[attr-defined]


@pytest.mark.asyncio
async def test_unhandled_should_not_send_fallback_when_chat_missing(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    _, __, handler, ___ = import_module()
    ok: bool = await handler(event_with_message, RuntimeError("chat not found"))
    assert ok is True
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None
    assert event_with_message.update.message.answered == []


@pytest.mark.asyncio
async def test_minimal_update_info_update_is_none_branch(
    import_module: ErrorHandler,
) -> None:
    _, __, handler, ___ = import_module()
    event: FakeErrorEvent = FakeErrorEvent(update=None)
    ok: bool = await handler(event, RuntimeError("anything"))
    assert ok is True


@pytest.mark.asyncio
async def test_resolve_answer_target_update_is_none_branch(
    import_module: ErrorHandler,
) -> None:
    _, __, handler, ___ = import_module()
    event: FakeErrorEvent = FakeErrorEvent(update=None)
    ok: bool = await handler(event, RuntimeError("regular error"))
    assert ok is True


@pytest.mark.asyncio
async def test_cb_msg_is_none_branch_false_path(
    import_module: ErrorHandler, event_with_callback: FakeErrorEvent
) -> None:
    module, __, handler, logger = import_module()
    assert event_with_callback.update is not None
    assert event_with_callback.update.callback_query is not None
    event_with_callback.update.callback_query.message = None
    exc = module.TelegramBadRequest("just to run through")
    ok: bool = await handler(event_with_callback, exc)
    assert ok is True
    assert any("Telegram error" in str(args[0]) for args, _ in logger.warning_calls)


@pytest.mark.asyncio
async def test_user_id_already_set_branch_false_path(
    import_module: ErrorHandler, event_with_both: FakeErrorEvent
) -> None:
    module, __, handler, logger = import_module()
    exc = module.TelegramBadRequest("walk through")
    ok: bool = await handler(event_with_both, exc)
    assert ok is True
    assert any("Telegram error" in str(args[0]) for args, _ in logger.warning_calls)


@pytest.mark.asyncio
async def test_should_send_fallback_blocked_markers_branch_true_path(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent
) -> None:
    _, __, handler, ___ = import_module()
    ok: bool = await handler(event_with_message, RuntimeError("bot was blocked by the user"))
    assert ok is True
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None
    assert event_with_message.update.message.answered == []


@pytest.mark.asyncio
async def test_unhandled_fallback_answer_raises_is_suppressed(
    import_module: ErrorHandler, event_with_message: FakeErrorEvent, monkeypatch: pytest.MonkeyPatch
) -> None:
    _, __, handler, logger = import_module()
    assert event_with_message.update is not None
    assert event_with_message.update.message is not None

    async def boom_answer() -> None:
        raise RuntimeError("send fail")

    monkeypatch.setattr(event_with_message.update.message, "answer", boom_answer, raising=True)

    ok: bool = await handler(event_with_message, RuntimeError("normal error"))
    assert ok is True
    assert any("Unhandled error" in str(args[0]) for args, _ in logger.exception_calls)
