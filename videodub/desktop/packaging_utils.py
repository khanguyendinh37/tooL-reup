"""Helpers shared by the PyInstaller specs."""
from __future__ import annotations

import os
from pathlib import Path

# Windows still limits most installers (Inno Setup included) to 260-character
# paths. torch ships third-party licenses nested 15 folders deep inside its
# dist-info (179 characters relative to the app folder), so a customer with a
# long user name or a custom install folder hits "Error 206: filename too long"
# and the installer rolls back. Deep license files are merged into one text
# file instead; their full text is kept for license compliance.
MAX_METADATA_RELATIVE_PATH = 60
MERGED_LICENSE_NAME = "THIRD_PARTY_LICENSES.txt"


def shorten_metadata_paths(datas: list[tuple[str, str]], work_dir: str | os.PathLike) -> list[tuple[str, str]]:
    """Expand ``*.dist-info`` folders and merge files with very long paths.

    ``datas`` uses PyInstaller's ``(source, destination_folder)`` format.
    Returns a new list; other entries are passed through unchanged.
    """
    work = Path(work_dir) / "merged-licenses"
    result: list[tuple[str, str]] = []
    seen: set[tuple[str, str]] = set()

    def add(entry: tuple[str, str]) -> None:
        if entry not in seen:
            seen.add(entry)
            result.append(entry)

    for source, destination in datas:
        source_path = Path(source)
        if not (source_path.is_dir() and source_path.name.endswith(".dist-info")):
            add((source, destination))
            continue

        long_files: list[Path] = []
        for file in sorted(p for p in source_path.rglob("*") if p.is_file()):
            relative = file.relative_to(source_path)
            if len(relative.as_posix()) > MAX_METADATA_RELATIVE_PATH:
                long_files.append(file)
                continue
            add((str(file), str(Path(destination) / relative.parent)))

        if long_files:
            merged_dir = work / destination
            merged_dir.mkdir(parents=True, exist_ok=True)
            merged = merged_dir / MERGED_LICENSE_NAME
            with merged.open("w", encoding="utf-8") as handle:
                for file in long_files:
                    relative = file.relative_to(source_path).as_posix()
                    handle.write(f"===== {relative} =====\n")
                    handle.write(file.read_text(encoding="utf-8", errors="replace"))
                    handle.write("\n\n")
            add((str(merged), destination))
    return result
