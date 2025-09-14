import importlib
import types
from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch
from mypy.moduleinspect import ModuleType


def _reload_config() -> ModuleType:
    import sys

    if "config" in sys.modules:
        return importlib.reload(sys.modules["config"])
    from libs.common import config

    return importlib.reload(config)


@pytest.fixture(autouse=True)
def clear_env(monkeypatch: MonkeyPatch) -> None:
    # Чистим важные переменные окружения между тестами
    for k in ("ENV_FILE", "BOT_TOKEN", "I18N_BOT", "RATE_LIMIT_PER_USER", "RATE_LIMIT_WINDOW_SEC"):
        monkeypatch.delenv(k, raising=False)
    # Чистим кэш get_settings между тестами
    from libs.common import config

    config.get_settings.cache_clear()


def _ns(filename: str | Path | None = None) -> types.SimpleNamespace:
    # Удобный конструктор кадров стека
    if filename is None:
        return types.SimpleNamespace()
    return types.SimpleNamespace(filename=str(filename))


def test_detect_returns_bot_posix(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns("/some/irrelevant/path.py"),
        _ns("/project/bots/echo_bot/handler.py"),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() == "echo_bot"


def test_detect_returns_bot_windows_separators(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    win_path = r"C:\work\repo\bots\questionnaire\app\main.py"
    monkeypatch.setattr(config.inspect, "stack", lambda: [_ns(win_path)])

    assert config._detect_bot_name_from_stack() == "questionnaire"


def test_detect_none_when_file_after_bots(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns("/no/bots/here.py"),
        _ns("/another/place/main.py"),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() is None


def test_detect_none_when_no_trailing_after_bot_dir(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns("/project/bots/echo_bot"),
        _ns("/other.py"),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() is None


def test_detect_skips_empty_and_missing_filename_frames(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns(None),  # объект без filename вовсе
        _ns(""),  # filename пустая строка
        _ns(Path("/proj/bots/mega_bot/core.py")),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() == "mega_bot"


def test_detect_first_valid_among_many_frames(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns("/x/y.py"),
        _ns("/a/bots/here.py"),  # файл после bots -> игнор
        _ns("/root/bots/botA/file.txt"),  # валидный кандидат
        _ns("/another/bots/botB/elsewhere.py"),  # до сюда не дойдём
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() == "botA"


def test_detect_bot_name_from_stack_happy(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    # Подсунем кастомный стек: сначала "плохой" кадр (IndexError),
    # затем корректный кадр с bots/<bot>/file.py,
    # затем вообще без "bots".
    fake_stack = [
        types.SimpleNamespace(
            filename=str(Path("/project/bots"))
        ),  # вызовет IndexError внутри функции
        types.SimpleNamespace(
            filename=str(Path("/project/bots/echo_bot/handler.py"))
        ),  # должен найти echo_bot
        types.SimpleNamespace(filename=str(Path("/some/other/path.py"))),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() == "echo_bot"


def test_detect_bot_name_from_stack_none(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        types.SimpleNamespace(filename=str(Path("/no/bots/here.py"))),
        types.SimpleNamespace(filename=str(Path("/another/place/main.py"))),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() is None


def test_detect_skips_segment_with_dot_in_name(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    fake_stack = [
        _ns("/repo/bots/bad.name/handler.py"),
        _ns("/repo/bots/good/ok.py"),
    ]
    monkeypatch.setattr(config.inspect, "stack", lambda: fake_stack)

    assert config._detect_bot_name_from_stack() == "good"


def test_select_env_file_prefers_env_var(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    custom = tmp_path / "my.env"
    custom.write_text("BOT_TOKEN=abc\n", encoding="utf-8")

    monkeypatch.setenv("ENV_FILE", str(custom))
    # PROJECT_ROOT не важен в этом кейсе, но изменим на всякий случай
    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path, raising=False)

    assert config.select_env_file() == custom


def test_select_env_file_bot_specific_over_root(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    # Структура: <tmp>/bots/echo_bot/.env и <tmp>/.env
    bots_dir = tmp_path / "bots" / "echo_bot"
    bots_dir.mkdir(parents=True)
    bot_env = bots_dir / ".env"
    bot_env.write_text("BOT_TOKEN=bot\n", encoding="utf-8")
    root_env = tmp_path / ".env"
    root_env.write_text("BOT_TOKEN=root\n", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "echo_bot")

    got = config.select_env_file()
    assert got == bot_env, "Должен выбрать .env конкретного бота, если он существует"


def test_select_env_file_root_when_bot_env_absent(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    # Структура: только <tmp>/.env
    root_env = tmp_path / ".env"
    root_env.write_text("BOT_TOKEN=root\n", encoding="utf-8")

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "echo_bot")

    got = config.select_env_file()
    assert got == root_env, "Если .env бота нет — берём корневой .env"


def test_select_env_file_empty_when_no_envs(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "PROJECT_ROOT", tmp_path, raising=False)
    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: None)
    monkeypatch.delenv("ENV_FILE", raising=False)

    got = config.select_env_file()
    assert got == Path(), "Если .env файлов нет — возвращается пустой Path()"


def test_appsettings_defaults_and_i18n_autofill(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    # Детектируемый бот
    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "questionnaire")
    # Валидный токен
    monkeypatch.setenv("BOT_TOKEN", "real:123")
    # I18N_BOT не задаём -> должен подставиться из детекта

    app = config.AppSettings()
    assert app.i18n_bot == "questionnaire"
    # Дефолты rate limit
    assert app.rate_limit_per_user == 3
    assert app.rate_limit_window_sec == 1


def test_appsettings_i18n_mismatch_raises(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "questionnaire")
    monkeypatch.setenv("BOT_TOKEN", "real:123")
    monkeypatch.setenv("I18N_BOT", "echo")

    with pytest.raises(ValueError) as ei:  # noqa: PT011
        config.AppSettings()
    assert "I18N_BOT='echo'" in str(ei.value)


@pytest.mark.parametrize("bad_token", ["", "   ", "Put-Your-Telegram-Bot-Token-Here-xxx"])
def test_validate_token_bad_values_raise(monkeypatch: MonkeyPatch, bad_token: str) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "global")
    if bad_token is None:
        monkeypatch.delenv("BOT_TOKEN", raising=False)
    else:
        monkeypatch.setenv("BOT_TOKEN", bad_token)

    app = config.AppSettings()
    with pytest.raises(RuntimeError) as ei:
        app.validate_token()
    assert "BOT_TOKEN is not set" in str(ei.value)


def test_validate_token_ok(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "global")
    monkeypatch.setenv("BOT_TOKEN", "real:ok-987")

    app = config.AppSettings()
    # не должно кидать
    app.validate_token()


def test_get_settings_strict_true_caches(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "global")
    monkeypatch.setenv("BOT_TOKEN", "real:cache-1")
    config.get_settings.cache_clear()

    s1 = config.get_settings(bot_name="test", strict=True)
    s2 = config.get_settings(bot_name="test", strict=True)
    assert s1 is s2, "Ожидаем кэширование по strict=True"


def test_get_settings_strict_false_allows_placeholder_and_caches(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: "global")
    monkeypatch.setenv("BOT_TOKEN", "Put-Your-Telegram-Bot-Token-Here-zzz")
    config.get_settings.cache_clear()

    # strict=False — не валидируем токен
    s1 = config.get_settings(bot_name="test", strict=False)
    s2 = config.get_settings(bot_name="test", strict=False)
    assert s1 is s2
    # И при этом токен остался как есть
    assert s1.bot_token == "Put-Your-Telegram-Bot-Token-Here-zzz"


def test_appsettings_i18n_mismatch_but_detected_global(monkeypatch: MonkeyPatch) -> None:
    from libs.common import config

    # Детектируем "global"
    monkeypatch.setattr(config, "_detect_bot_name_from_stack", lambda: None)
    monkeypatch.setenv("BOT_TOKEN", "real:456")
    # Но явно задаём I18N_BOT
    monkeypatch.setenv("I18N_BOT", "echo")

    app = config.AppSettings()
    # В этом случае ошибки быть не должно
    assert app.i18n_bot == "echo"


def test_protocol_validate_token_signature() -> None:
    from libs.common import config

    class Dummy:
        # noinspection PyMethodMayBeStatic
        def validate_token(self) -> None:
            return None

    # Проверим, что сигнатура совпадает и метод доступен
    assert callable(config.Settings.validate_token)
    d = Dummy()
    # вызов не должен падать
    assert d.validate_token() is None


def test_protocol_validate_token_executes_ellipsis() -> None:
    from libs.common import config

    # Берём исходную функцию из Protocol (а не у реализации)
    func = config.Settings.__dict__["validate_token"]
    assert callable(func)

    # Вызываем – должно выполниться и вернуться None
    result = func(object())
    assert result is None
