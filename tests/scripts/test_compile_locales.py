import gettext
import shutil
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import polib
import pytest
from _pytest.capture import CaptureFixture
from _pytest.monkeypatch import MonkeyPatch

import scripts.compile_locales as cl


@pytest.fixture
def mock_compile_one() -> MagicMock:
    with patch("scripts.compile_locales._compile_locales", autospec=True) as mock:
        return mock


@pytest.fixture
def tmp_project(tmp_path: Path) -> Path:
    """
    Готовим временный "проект":
    - global: hello -> Global hello
    - bot test_bot: hello -> Bot hello (перекрывает), bye -> Goodbye
    - bot test_bot (ru): plural формы
    """
    # global/en
    g_en_dir = tmp_path / "locales" / "en" / "LC_MESSAGES"
    g_en_dir.mkdir(parents=True)
    g_en_po = polib.POFile()
    g_en_po.metadata = {
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": "en",
    }
    g_en_po.append(polib.POEntry(msgid="hello", msgstr="Global hello"))
    g_en_po.save(str(g_en_dir / "messages.po"))

    # bot/en
    b_en_dir = tmp_path / "bots" / "test_bot" / "locales" / "en" / "LC_MESSAGES"
    b_en_dir.mkdir(parents=True)
    b_en_po = polib.POFile()
    b_en_po.metadata = {
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": "en",
    }
    b_en_po.append(polib.POEntry(msgid="hello", msgstr="Bot hello"))
    b_en_po.append(polib.POEntry(msgid="bye", msgstr="Goodbye"))
    b_en_po.save(str(b_en_dir / "messages.po"))

    # bot/ru plural
    b_ru_dir = tmp_path / "bots" / "test_bot" / "locales" / "ru" / "LC_MESSAGES"
    b_ru_dir.mkdir(parents=True)
    b_ru_po = polib.POFile()
    b_ru_po.metadata = {
        "Content-Type": "text/plain; charset=UTF-8",
        "Language": "ru",
        "Plural-Forms": (
            "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : "
            "n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
        ),
    }
    b_ru_po.append(
        polib.POEntry(
            msgid="apple",
            msgid_plural="apples",
            msgstr_plural={0: "яблоко", 1: "яблока", 2: "яблок"},
        )
    )
    b_ru_po.save(str(b_ru_dir / "messages.po"))

    return tmp_path


def _load_mo(mo_path: Path) -> gettext.GNUTranslations:
    with mo_path.open("rb") as fp:
        return gettext.GNUTranslations(fp)


def test_compile_single_bot_merges_global_and_bot(
    monkeypatch: MonkeyPatch, tmp_project: Path
) -> None:
    monkeypatch.setattr(cl, "PROJECT_ROOT", tmp_project)

    cl._compile_locales("test_bot")

    en_mo = (
        tmp_project / ".i18n_cache" / "test_bot" / "locales" / "en" / "LC_MESSAGES" / "messages.mo"
    )
    ru_mo = (
        tmp_project / ".i18n_cache" / "test_bot" / "locales" / "ru" / "LC_MESSAGES" / "messages.mo"
    )

    assert en_mo.exists()
    assert ru_mo.exists()

    tr_en = _load_mo(en_mo)
    # bot перекрывает global
    assert tr_en.gettext("hello") == "Bot hello"
    # новая строка из бота
    assert tr_en.gettext("bye") == "Goodbye"

    tr_ru = _load_mo(ru_mo)
    assert tr_ru.ngettext("apple", "apples", 1) == "яблоко"
    assert tr_ru.ngettext("apple", "apples", 3) == "яблока"
    assert tr_ru.ngettext("apple", "apples", 7) == "яблок"


def test_compile_all_bots_includes_empty_bot_with_globals(
    monkeypatch: MonkeyPatch, tmp_project: Path
) -> None:
    # создаём пустого бота (без локалей)
    (tmp_project / "bots" / "empty_bot").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cl, "PROJECT_ROOT", tmp_project)
    monkeypatch.setattr(cl, "BOTS_DIR", tmp_project / "bots")

    cl._compile_all_bots()

    # test_bot: должны быть свои + глобальные
    en_mo = (
        tmp_project / ".i18n_cache" / "test_bot" / "locales" / "en" / "LC_MESSAGES" / "messages.mo"
    )
    assert en_mo.exists()
    tr_en = _load_mo(en_mo)
    assert tr_en.gettext("hello") == "Bot hello"

    empty_en_mo = (
        tmp_project / ".i18n_cache" / "empty_bot" / "locales" / "en" / "LC_MESSAGES" / "messages.mo"
    )
    assert empty_en_mo.exists()
    tr_empty = _load_mo(empty_en_mo)
    assert tr_empty.gettext("hello") == "Global hello"
    # "bye" там быть не должно
    assert tr_empty.gettext("bye") == "bye"


def test_merge_entries_empty_list_uses_defaults_and_no_entries() -> None:
    # po_list пустой → берутся дефолтные метаданные (в т.ч. Plural-Forms)
    merged = cl._merge_entries(lang="en", po_list=[])
    assert merged.metadata["Language"] == "en"
    assert "Plural-Forms" in merged.metadata
    assert len(merged) == 0  # нет записей


def test_compile_all_folder_search(
    mock_compile_one: MagicMock, tmp_project: Path, monkeypatch: MonkeyPatch
) -> None:
    for child in tmp_project.iterdir():
        if child.is_dir():
            shutil.rmtree(child)
        else:
            child.unlink()

    monkeypatch.setattr(cl, "PROJECT_ROOT", tmp_project)
    monkeypatch.setattr(cl, "BOTS_DIR", tmp_project / "bots")

    cl._compile_all_bots()
    mock_compile_one.assert_not_called()

    (tmp_project / "bots").mkdir(parents=True, exist_ok=True)

    cl._compile_all_bots()
    mock_compile_one.assert_not_called()

    (tmp_project / "bots" / "global").mkdir(parents=True, exist_ok=True)
    (tmp_project / "bots" / "test_bot").mkdir(parents=True, exist_ok=True)

    cl._compile_all_bots()
    mock_compile_one.call_count = 1

    cl._compile_all_bots(skip_global=False)
    mock_compile_one.call_count = 2


def test_compile_all_with_po_saved(monkeypatch: MonkeyPatch, tmp_project: Path) -> None:
    monkeypatch.setattr(cl, "PROJECT_ROOT", tmp_project)
    monkeypatch.setattr(cl, "BOTS_DIR", tmp_project / "bots")

    monkeypatch.setattr(sys, "argv", ["compile_locales.py", "--keep-po"])
    cl.main()

    en_po = (
        tmp_project / ".i18n_cache" / "test_bot" / "locales" / "en" / "LC_MESSAGES" / "messages.mo"
    )
    assert en_po.exists()


@patch("scripts.compile_locales._compile_all_bots")
def test_incorrect_arguments(
    mock_compile_all: MagicMock,
    mock_compile_one: MagicMock,
    capsys: CaptureFixture,
    monkeypatch: MonkeyPatch,
    tmp_project: Path,
) -> None:
    (tmp_project / "bots" / "__pycache__").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(cl, "PROJECT_ROOT", tmp_project)
    monkeypatch.setattr(cl, "BOTS_DIR", tmp_project / "bots")

    monkeypatch.setattr(sys, "argv", ["compile_locales.py", "--bot", "wrong_bot"])
    with pytest.raises(SystemExit):
        cl.main()

    result = capsys.readouterr()
    assert "❌ Unknown bot: wrong_bot. Available bots: test_bot" in result.out
    mock_compile_all.call_count = 0
    mock_compile_one.call_count = 0

    monkeypatch.setattr(sys, "argv", ["compile_locales.py"])
    cl.main()
    mock_compile_all.call_count = 1
    mock_compile_one.call_count = 0

    monkeypatch.setattr(sys, "argv", ["compile_locales.py", "--bot", "test_bot"])
    cl.main()
    mock_compile_all.call_count = 1
    mock_compile_one.call_count = 1


def test_lang_by_po(tmp_project: Path) -> None:
    assert cl._lang_from_po(tmp_project) == "en"
    assert cl._lang_from_po(tmp_project / "locales") == "en"
    assert cl._lang_from_po(tmp_project / "locales" / "ru") == "ru"
