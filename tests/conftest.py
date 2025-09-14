import sys
from collections.abc import Callable
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from _pytest.monkeypatch import MonkeyPatch


class MockLogger:
    def __init__(self) -> None:
        self.debug_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.warning_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
        self.exception_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []

    def debug(self, *a: Any, **k: Any) -> None:  # noqa: ANN401
        self.debug_calls.append((a, k))

    def warning(self, *a: Any, **k: Any) -> None:  # noqa: ANN401
        self.warning_calls.append((a, k))

    def exception(self, *a: Any, **k: Any) -> None:  # noqa: ANN401
        self.exception_calls.append((a, k))


@pytest.fixture(autouse=True)
def setup_logging() -> MockLogger:
    return MockLogger()


class MockI18n:
    def __init__(
        self,
        path: str | Path = ".",
        default_locale: str = "en",
        domain: str = "messages",
    ) -> None:
        self.path = path
        self.default_locale = default_locale
        self.domain = domain


class MockI18nMW:
    def __init__(self, i18n: MockI18n) -> None:
        self.i18n = i18n

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def get_locale(self, event: Any, data: dict[str, Any]) -> str:  # noqa: ANN401
        user = data.get("event_from_user")
        return getattr(user, "language_code", None) or "en"


@pytest.fixture
def mock_i18n(
    monkeypatch: MonkeyPatch, tmp_path: Path
) -> Callable[[str | Path | None, str | None], MockI18nMW]:

    def fake_create(
        _project_root: str | Path | None = None, _bot_name: str | None = None
    ) -> MockI18nMW:
        i18n = MockI18n(path=str(tmp_path / "locales"))
        return MockI18nMW(i18n)

    import libs.common.aiogram.i18n as i18n_mod

    i18n_mod.create_i18n.cache_clear()
    monkeypatch.setattr(i18n_mod, "create_i18n", fake_create)
    return fake_create


@pytest.fixture(autouse=True)
def noop_gettext(monkeypatch: MonkeyPatch) -> None:
    import libs.common.aiogram.i18n as i18n_mod

    monkeypatch.setattr(i18n_mod, "_", lambda s, *a, **kw: s)


class FakeMessage:
    def __init__(self, chat_id: int = 1, user_id: int = 2) -> None:
        self.chat = type("Chat", (), {"id": chat_id})()
        self.from_user = type("User", (), {"id": user_id})()
        self.answered: list[str] = []

    async def answer(self, text: str) -> None:
        self.answered.append(text)


class FakeCallbackQuery:
    def __init__(self, data: str = "cb", chat_id: int = 1, user_id: int = 2) -> None:
        self.data: str = data
        self.message: FakeMessage | None = FakeMessage(chat_id=chat_id, user_id=user_id)
        self.from_user = type("User", (), {"id": user_id})()


class FakeUpdate:
    def __init__(
        self,
        message: FakeMessage | None = None,
        callback_query: FakeCallbackQuery | None = None,
    ) -> None:
        self.message: FakeMessage | None = message
        self.callback_query: FakeCallbackQuery | None = callback_query


class FakeErrorEvent:
    def __init__(self, update: FakeUpdate | None) -> None:
        self.update: FakeUpdate | None = update


HandlerType = Callable[[FakeErrorEvent, Exception], "Any"]


class FakeDispatcher:
    def __init__(self) -> None:
        self._handler: HandlerType | None = None

    def errors(self) -> Callable[[HandlerType], HandlerType]:
        def decorator(func: HandlerType) -> HandlerType:
            self._handler = func
            return func

        return decorator


@pytest.fixture(autouse=True)
def stub_aiogram(monkeypatch: MonkeyPatch) -> None:
    exc_mod: ModuleType = ModuleType("aiogram.exceptions")

    class TelegramBadRequest(Exception):
        def __init__(self, message: str = "bad request") -> None:
            super().__init__(message)
            self.message: str = message

    class TelegramForbiddenError(Exception):
        def __init__(self, message: str = "forbidden") -> None:
            super().__init__(message)
            self.message: str = message

    class TelegramRetryAfter(Exception):
        def __init__(self, retry_after: float = 1.0) -> None:
            super().__init__(f"retry after {retry_after}")
            self.retry_after: float = retry_after

    exc_mod.TelegramBadRequest = TelegramBadRequest
    exc_mod.TelegramForbiddenError = TelegramForbiddenError
    exc_mod.TelegramRetryAfter = TelegramRetryAfter

    types_mod: ModuleType = ModuleType("aiogram.types")
    types_mod.ErrorEvent = FakeErrorEvent
    types_mod.Message = FakeMessage
    types_mod.CallbackQuery = FakeCallbackQuery

    aio_mod: ModuleType = ModuleType("aiogram")
    aio_mod.Dispatcher = FakeDispatcher

    monkeypatch.setitem(sys.modules, "aiogram", aio_mod)
    monkeypatch.setitem(sys.modules, "aiogram.exceptions", exc_mod)
    monkeypatch.setitem(sys.modules, "aiogram.types", types_mod)
