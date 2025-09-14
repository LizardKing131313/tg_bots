"""
Compile merged locales (.po → .mo) into .i18n_cache.

Usage:
    python scripts/compile_locales.py --all
    python scripts/compile_locales.py --bot echo_bot
    python scripts/compile_locales.py --all --keep-po
"""

from __future__ import annotations

import argparse
import shutil
from collections import defaultdict
from pathlib import Path

import polib


PROJECT_ROOT = Path(__file__).resolve().parent.parent
BOTS_DIR = PROJECT_ROOT / "bots"
DOMAIN = "messages"
CACHE_DIR = ".i18n_cache"
LOCALES_DIR = "locales"
DEFAULT_LANGUAGE = "en"
LC_MESSAGES = "LC_MESSAGES"

# Дефолты для plural-forms
PLURAL_DEFAULTS = {
    "en": "nplurals=2; plural=(n != 1);",
    "ru": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);",  # noqa: E501
}

# Глобальный переключатель: сохранять ли .po вместе с .mo
KEEP_PO = False


def _lang_from_po(po_path: Path) -> str:
    parts = po_path.parts
    if LOCALES_DIR in parts:
        i = parts.index(LOCALES_DIR)
        if i + 1 < len(parts):
            return parts[i + 1]
    return DEFAULT_LANGUAGE


def _scan_po(bot_name: str) -> dict[str, list[Path]]:
    """Группировка всех .po по языку (global → bot)."""
    by_lang: dict[str, list[Path]] = defaultdict(list)

    def add_dir(loc_dir: Path) -> None:
        if loc_dir.is_dir():
            for po in sorted(loc_dir.rglob("*.po")):
                lang = _lang_from_po(po)
                by_lang[lang].append(po)

    add_dir(PROJECT_ROOT / LOCALES_DIR)
    if bot_name != "global":
        add_dir(PROJECT_ROOT / "bots" / bot_name / LOCALES_DIR)
    return by_lang


def _merge_entries(lang: str, po_list: list[Path]) -> polib.POFile:
    """Мержим global+bot в один POFile (бот перекрывает)."""
    merged = polib.POFile()

    if po_list:
        first_hdr = polib.pofile(str(po_list[0])).metadata
        merged.metadata = {
            "Project-Id-Version": first_hdr.get("Project-Id-Version", "i18n"),
            "Report-Msgid-Bugs-To": first_hdr.get("Report-Msgid-Bugs-To", ""),
            "POT-Creation-Date": first_hdr.get("POT-Creation-Date", ""),
            "PO-Revision-Date": first_hdr.get("PO-Revision-Date", ""),
            "Last-Translator": first_hdr.get("Last-Translator", ""),
            "Language-Team": first_hdr.get("Language-Team", ""),
            "Language": lang,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
            "Plural-Forms": first_hdr.get("Plural-Forms")
            or PLURAL_DEFAULTS.get(lang, PLURAL_DEFAULTS[DEFAULT_LANGUAGE]),
        }
    else:
        merged.metadata = {
            "Project-Id-Version": "i18n",
            "Language": lang,
            "MIME-Version": "1.0",
            "Content-Type": "text/plain; charset=UTF-8",
            "Content-Transfer-Encoding": "8bit",
            "Plural-Forms": PLURAL_DEFAULTS.get(lang, PLURAL_DEFAULTS[DEFAULT_LANGUAGE]),
        }

    def key(entry: polib.POEntry) -> tuple[str | None, str, bool]:
        return entry.msgctxt, entry.msgid, bool(entry.msgid_plural)

    index: dict[tuple[str | None, str, bool], polib.POEntry] = {}
    for po_path in po_list:
        cat = polib.pofile(str(po_path))
        for e in cat:
            new_e = polib.POEntry(
                msgid=e.msgid,
                msgstr=e.msgstr,
                msgctxt=e.msgctxt,
                msgid_plural=e.msgid_plural,
                msgstr_plural=dict(e.msgstr_plural) if e.msgid_plural else {},
                occurrences=list(e.occurrences),
                comment=e.comment,
                tcomment=e.tcomment,
                flags=list(e.flags),
            )
            index[key(e)] = new_e

    for e in index.values():
        merged.append(e)

    return merged


def _emit_files(lang_dir: Path, merged: polib.POFile) -> Path:
    """Сохраняем .mo (+ опционально .po)."""
    lang_dir.mkdir(parents=True, exist_ok=True)
    po_path = lang_dir / f"{DOMAIN}.po"
    mo_path = lang_dir / f"{DOMAIN}.mo"

    if KEEP_PO:
        merged.save(str(po_path))
    merged.save_as_mofile(str(mo_path))
    return mo_path


def _compile_locales(bot_name: str) -> None:
    cache_base = PROJECT_ROOT / CACHE_DIR / bot_name / LOCALES_DIR
    bot_cache_root = PROJECT_ROOT / CACHE_DIR / bot_name
    if bot_cache_root.exists():
        shutil.rmtree(bot_cache_root)
    cache_base.mkdir(parents=True, exist_ok=True)

    by_lang = _scan_po(bot_name)
    compiled = 0
    for lang, po_files in by_lang.items():
        lang_dir = cache_base / lang / LC_MESSAGES
        merged = _merge_entries(lang, po_files)
        _emit_files(lang_dir, merged)
        compiled += 1

    print(
        f"[i18n] bot={bot_name} merged {len(by_lang)} "
        f"lang(s) into {bot_cache_root} (compiled {compiled} .mo)"
    )


def _available_bots() -> list[str]:
    return sorted([p.name for p in BOTS_DIR.iterdir() if p.is_dir() and p.name != "__pycache__"])


def _compile_all_bots(skip_global: bool = True) -> None:
    if not BOTS_DIR.exists():
        print("⚠️  No ./bots directory found — nothing to compile.")
        return
    bots = _available_bots()
    if not bots:
        print("⚠️  No bots found under ./bots — nothing to compile.")
        return
    for bot in bots:
        if skip_global and bot == "global":
            continue
        _compile_locales(bot)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compile merged locales into .i18n_cache.")
    g = parser.add_mutually_exclusive_group()
    g.add_argument("--all", action="store_true", help="Compile locales for all bots under ./bots")
    g.add_argument("--bot", type=str, help="Compile locales for a single bot (e.g. --bot echo_bot)")
    parser.add_argument("--include-global", action="store_true", help="Also compile for 'global'")
    parser.add_argument("--keep-po", action="store_true", help="Also write merged .po into cache")
    args = parser.parse_args()

    global KEEP_PO
    KEEP_PO = args.keep_po

    if args.bot:
        available_bots = _available_bots()
        if args.bot not in available_bots:
            print(f"❌ Unknown bot: {args.bot}. Available bots: {', '.join(available_bots)}")
            exit(1)
        _compile_locales(args.bot)
    else:
        _compile_all_bots(skip_global=not args.include_global)


if __name__ == "__main__":
    main()
