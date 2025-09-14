from __future__ import annotations

import asyncio
import importlib
import sys
import types
from pathlib import Path
from typing import Any

import pytest
from mypy.moduleinspect import ModuleType


class DummyI18n:
    def __init__(self, *, path: str, default_locale: str, domain: str) -> None:
        self.path = path
        self.default_locale = default_locale
        self.domain = domain


def dummy_gettext(key: str) -> str:
    return key


class DummyI18nMiddleware:
    def __init__(self, i18n: DummyI18n) -> None:
        self.i18n = i18n

    # noinspection PyMethodMayBeStatic,PyUnusedLocal
    async def get_locale(self, event: Any, data: dict[str, Any]) -> str:  # noqa: ANN401
        user = data.get("event_from_user")
        code = getattr(user, "language_code", None) if user else None
        return code or "en"


class DummyTelegramObject:
    pass


def install_fake_aiogram() -> None:
    aiogram_pkg = types.ModuleType("aiogram")
    aiogram_types = types.ModuleType("aiogram.types")
    aiogram_types.TelegramObject = DummyTelegramObject

    aiogram_utils = types.ModuleType("aiogram.utils")
    aiogram_utils_i18n = types.ModuleType("aiogram.utils.i18n")
    aiogram_utils_i18n.I18n = DummyI18n
    aiogram_utils_i18n.gettext = dummy_gettext

    aiogram_utils_i18n_mw = types.ModuleType("aiogram.utils.i18n.middleware")
    aiogram_utils_i18n_mw.I18nMiddleware = DummyI18nMiddleware

    sys.modules["aiogram"] = aiogram_pkg
    sys.modules["aiogram.types"] = aiogram_types
    sys.modules["aiogram.utils"] = aiogram_utils
    sys.modules["aiogram.utils.i18n"] = aiogram_utils_i18n
    sys.modules["aiogram.utils.i18n.middleware"] = aiogram_utils_i18n_mw


def install_fake_libs_config(tmp_path: Path) -> None:
    libs_pkg = sys.modules.setdefault("libs", types.ModuleType("libs"))
    common_pkg = sys.modules.setdefault("libs.common", types.ModuleType("libs.common"))
    root_resolver = types.ModuleType("libs.common.root_resolver")

    def resolve_root() -> Path:
        return tmp_path

    root_resolver.resolve_root = resolve_root
    sys.modules["libs.common.root_resolver"] = root_resolver
    libs_pkg.common = common_pkg


def fresh_import_i18n() -> ModuleType:
    sys.modules.pop("libs.common.aiogram.i18n", None)
    i18n = importlib.import_module("libs.common.aiogram.i18n")
    i18n.create_i18n.cache_clear()
    return i18n


@pytest.fixture(autouse=True)
def _isolate_sys_modules() -> None:
    original = sys.modules.copy()
    try:
        return
    finally:
        sys.modules.clear()
        sys.modules.update(original)


def test_resolve_locales_dir_prefers_cache(tmp_path: Path) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    cache_dir = tmp_path / ".i18n_cache" / "alpha" / "locales"
    cache_dir.mkdir(parents=True)
    got = i18n._resolve_locales_dir(tmp_path, "alpha")
    assert got == cache_dir


def test_resolve_locales_dir_prefers_bot_when_no_cache(tmp_path: Path) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    bot_dir = tmp_path / "bots" / "beta" / "locales"
    bot_dir.mkdir(parents=True)
    got = i18n._resolve_locales_dir(tmp_path, "beta")
    assert got == bot_dir


def test_resolve_locales_dir_falls_back_to_global(tmp_path: Path) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    global_dir = tmp_path / "locales"
    global_dir.mkdir(parents=True)
    got = i18n._resolve_locales_dir(tmp_path, "gamma")
    assert got == global_dir


def test_resolve_locales_dir_missing_raises(tmp_path: Path) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    with pytest.raises(FileNotFoundError):
        i18n._resolve_locales_dir(tmp_path, "delta")


@pytest.mark.parametrize(
    ("lang_code", "expected"),
    [
        ("ru", "ru"),
        ("en", "en"),
        ("", "en"),
        (None, "en"),
    ],
)
def test_create_i18n_returns_middleware_and_locale_detection(
    tmp_path: Path, lang_code: str | None, expected: str
) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    # только global, чтобы выбран был именно он
    (tmp_path / "locales").mkdir(parents=True)

    mw = i18n.create_i18n(bot_name="zeta", project_root=tmp_path)
    assert isinstance(mw, DummyI18nMiddleware)

    user = types.SimpleNamespace(language_code=lang_code)
    loop = asyncio.new_event_loop()
    try:
        got = loop.run_until_complete(mw.get_locale(event=None, data={"event_from_user": user}))
    finally:
        loop.close()
    assert got == expected


def test_create_i18n_is_cached_singleton(tmp_path: Path) -> None:
    install_fake_aiogram()
    install_fake_libs_config(tmp_path)
    i18n = fresh_import_i18n()

    (tmp_path / "locales").mkdir(parents=True)
    a = i18n.create_i18n(bot_name="omega", project_root=tmp_path)
    b = i18n.create_i18n(bot_name="omega", project_root=tmp_path)
    assert a is b


def test___all___exports() -> None:
    install_fake_aiogram()
    i18n = fresh_import_i18n()
    expected = {"_", "create_i18n"}
    assert set(i18n.__all__) == expected
    for name in expected:
        assert hasattr(i18n, name)
