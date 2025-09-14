from __future__ import annotations

from pathlib import Path

import pytest
from _pytest.monkeypatch import MonkeyPatch

import libs.common.root_resolver as root_resolver


def _make_project_tree(tmp_path: Path) -> tuple[Path, Path]:
    root: Path = tmp_path / "project_root"
    (root / "libs" / "common").mkdir(parents=True, exist_ok=True)
    (root / "bots").mkdir(parents=True, exist_ok=True)
    fake_module: Path = root / "libs" / "common" / "root_resolver.py"
    fake_module.touch()
    return root, fake_module


def test_resolve_root_from_file_start(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Обычный кейс: старт от __file__ ведёт вверх к {root} с libs/ и bots/."""
    root, fake_file = _make_project_tree(tmp_path)

    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)
    monkeypatch.setattr(root_resolver.sys, "frozen", False, raising=False)

    other: Path = tmp_path / "elsewhere"
    other.mkdir()
    monkeypatch.chdir(other)

    resolved = root_resolver.resolve_root()
    assert resolved == root


def test_resolve_root_frozen_meipass(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    """Frozen-кейс: есть sys._MEIPASS, оттуда поднимаемся к {root}."""
    root, fake_file = _make_project_tree(tmp_path)
    meipass: Path = root / "build" / "_MEIPASS_dir"
    meipass.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(root_resolver.sys, "frozen", True, raising=False)
    monkeypatch.setattr(root_resolver.sys, "_MEIPASS", str(meipass), raising=False)

    app_dir: Path = root / "bin"
    app_dir.mkdir(exist_ok=True)
    app_path: Path = app_dir / "app"
    app_path.touch()
    monkeypatch.setattr(root_resolver.sys, "executable", str(app_path), raising=False)

    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)

    resolved = root_resolver.resolve_root()
    assert resolved == root


def test_resolve_root_frozen_no_meipass_uses_executable_parent(
    tmp_path: Path, monkeypatch: MonkeyPatch
) -> None:
    root, fake_file = _make_project_tree(tmp_path)

    monkeypatch.setattr(root_resolver.sys, "frozen", True, raising=False)
    if hasattr(root_resolver.sys, "_MEIPASS"):
        monkeypatch.delattr(root_resolver.sys, "_MEIPASS", raising=False)

    app_dir: Path = root / "run"
    app_dir.mkdir(exist_ok=True)
    app_path: Path = app_dir / "bot_app"
    app_path.touch()
    monkeypatch.setattr(root_resolver.sys, "executable", str(app_path), raising=False)

    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)

    resolved = root_resolver.resolve_root()
    assert resolved == root


def test_resolve_root_fallback_parents3(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    root, fake_file = _make_project_tree(tmp_path)

    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)

    nowhere: Path = tmp_path / "nowhere"
    nowhere.mkdir()

    def fake_iter() -> list[Path]:
        return [nowhere]

    monkeypatch.setattr(root_resolver, "_iter_starts", fake_iter, raising=True)

    resolved = root_resolver.resolve_root()
    assert resolved == root


def test_resolve_root_failure_raises(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    stray: Path = tmp_path / "stray"
    stray.mkdir()

    def fake_iter() -> list[Path]:
        return [stray]

    monkeypatch.setattr(root_resolver, "_iter_starts", fake_iter, raising=True)

    fake_file: Path = stray / "some.py"
    fake_file.touch()
    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)

    with pytest.raises(RuntimeError):
        root_resolver.resolve_root()


def test_iter_starts_dedup(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    from libs.common import root_resolver as resolver

    path = tmp_path
    monkeypatch.setattr(resolver, "Path", Path)
    monkeypatch.setattr(resolver.sys, "frozen", False, raising=False)
    monkeypatch.setattr(resolver, "__file__", str(path / "file.py"), raising=False)
    starts = resolver._iter_starts()
    # noinspection PyTypeChecker
    starts_with_dup = [*starts, starts[0]]
    seen: set[Path] = set()
    uniq = []
    for s in starts_with_dup:
        if s not in seen:
            uniq.append(s)
            seen.add(s)
    # noinspection PyTypeChecker
    assert starts[0] in uniq
    assert len(uniq) < len(starts_with_dup)


def test_fallback_candidate_not_root(monkeypatch: MonkeyPatch, tmp_path: Path) -> None:
    import libs.common.root_resolver as resolver

    fake_root = tmp_path / "fake"
    fake_root.mkdir()
    fake_file = fake_root / "libs" / "common" / "root_resolver.py"
    fake_file.parent.mkdir(parents=True, exist_ok=True)
    fake_file.touch()

    monkeypatch.setattr(resolver, "__file__", str(fake_file), raising=False)
    monkeypatch.setattr(resolver, "_iter_starts", lambda: [tmp_path], raising=True)

    with pytest.raises(RuntimeError):
        resolver.resolve_root()


def test_iter_starts_dedup_found(tmp_path: Path, monkeypatch: MonkeyPatch) -> None:
    base: Path = tmp_path / "sandbox"
    base.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(root_resolver.sys, "frozen", True, raising=False)
    monkeypatch.setattr(root_resolver.sys, "_MEIPASS", str(base), raising=False)
    exe_path = base / "app.exe"
    exe_path.touch()
    monkeypatch.setattr(root_resolver.sys, "executable", str(exe_path), raising=False)

    fake_file = base / "some_module.py"
    fake_file.touch()
    monkeypatch.setattr(root_resolver, "__file__", str(fake_file), raising=False)
    monkeypatch.chdir(base)

    with pytest.raises(RuntimeError):
        root_resolver.resolve_root()
