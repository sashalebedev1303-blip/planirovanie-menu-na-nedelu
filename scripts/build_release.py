"""Сборка релизного артефакта приложения (ЛР-9).

Скрипт используется локально и в CI (job ``build``): складывает исходники,
зависимости и инструкции в ``dist/tastyweek-app.zip``. Архив
воспроизводим: файлы сортируются, служебные каталоги и локальная БД
исключаются, дата внутри архива фиксирована.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DIST_DIR = ROOT / "dist"
ARCHIVE_PATH = DIST_DIR / "tastyweek-app.zip"
ARCHIVE_ROOT = "tastyweek"

INCLUDE_FILES = [
    "README.md",
    "Dockerfile",
    "docs/release-notes/v1.0.0.md",
]
INCLUDE_DIRS = [
    "src",
]

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    ".mypy_cache",
    "htmlcov",
}
EXCLUDED_SUFFIXES = {".pyc", ".pyo", ".db", ".coverage", ".spec"}

FIXED_TIMESTAMP = (2026, 1, 1, 0, 0, 0)


def iter_project_files() -> list[Path]:
    """Возвращает отсортированный список файлов, попадающих в артефакт."""
    files: list[Path] = []
    for name in INCLUDE_FILES:
        path = ROOT / name
        if path.is_file():
            files.append(path)
    for dir_name in INCLUDE_DIRS:
        base = ROOT / dir_name
        if not base.is_dir():
            continue
        for path in sorted(base.rglob("*")):
            if not path.is_file():
                continue
            if EXCLUDED_DIR_NAMES.intersection(path.parts):
                continue
            if path.suffix in EXCLUDED_SUFFIXES:
                continue
            files.append(path)
    return sorted(set(files), key=lambda item: item.relative_to(ROOT).as_posix())


def build_archive() -> Path:
    """Создаёт zip-архив приложения и возвращает путь к нему."""
    DIST_DIR.mkdir(exist_ok=True)
    files = iter_project_files()
    with zipfile.ZipFile(ARCHIVE_PATH, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for path in files:
            relative = path.relative_to(ROOT).as_posix()
            info = zipfile.ZipInfo(f"{ARCHIVE_ROOT}/{relative}", date_time=FIXED_TIMESTAMP)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            archive.writestr(info, path.read_bytes())
    return ARCHIVE_PATH


def main() -> None:
    archive = build_archive()
    size_kb = archive.stat().st_size / 1024
    print(f"Артефакт собран: {archive.relative_to(ROOT)} ({size_kb:.1f} КиБ)")
    print(f"Файлов в архиве: {len(iter_project_files())}")


if __name__ == "__main__":
    main()
