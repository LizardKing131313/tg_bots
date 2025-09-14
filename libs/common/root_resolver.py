from __future__ import annotations

import contextlib
import sys
from pathlib import Path


def _iter_starts() -> list[Path]:
    starts: list[Path] = []

    # 1) Предпочитаем __file__ — именно то, что нужно тесту "from_file_start"
    with contextlib.suppress(NameError, Exception):
        starts.append(Path(__file__).resolve())

    # 2) Затем текущая директория — часто полезна при запуске скриптов
    with contextlib.suppress(Exception):
        starts.append(Path.cwd().resolve())

    # 3) Frozen: PyInstaller/аналогичные сборки
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            with contextlib.suppress(Exception):
                starts.append(Path(meipass).resolve())
        with contextlib.suppress(Exception):
            starts.append(Path(sys.executable).resolve().parent)
    else:
        # 4) НЕ frozen: sys.argv[0] — только в самом конце приоритета,
        # чтобы не перебить __file__/cwd под pytest.
        with contextlib.suppress(Exception):
            starts.append(Path(sys.argv[0]).resolve())

    # Дедуп по сохранению первого вхождения (важен порядок приоритета)
    uniq: list[Path] = []
    seen: set[Path] = set()
    for s in starts:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    return uniq


def _looks_like_root(p: Path) -> bool:
    # Признаки корня проекта
    return (p / "libs").is_dir() and (p / "bots").is_dir()


def resolve_root() -> Path:
    # Идём от каждой стартовой точки вверх по родителям
    for start in _iter_starts():
        for node in (start, *start.parents):
            if _looks_like_root(node):
                return node

    # Фоллбэк: подняться на 2 уровня от файла модуля (если доступен)
    with contextlib.suppress(Exception):
        candidate = Path(__file__).resolve().parents[2]
        if _looks_like_root(candidate):
            return candidate

    raise RuntimeError("ROOT not found. Exit")


__all__ = ["resolve_root"]
