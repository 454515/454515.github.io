"""Import queue: filtered, de-duplicated image paths. See spec-05 §3.

Pure logic, no UI: files/folders go in, an ordered list of accepted images
comes out, non-image paths are collected as `rejected` for friendly feedback.
"""
import os
from dataclasses import dataclass
from pathlib import Path

EXT_WHITELIST = {".jpg", ".jpeg", ".png", ".bmp"}


@dataclass
class ImportedImage:
    path: str
    filename: str  # display name


class ImportQueue:
    def __init__(self) -> None:
        self._items: list[ImportedImage] = []
        self._seen: set[str] = set()
        self._rejected: list[str] = []

    # ---- public API ----

    def add_images(self, paths: list[str]) -> list[str]:
        """Add image paths; return the accepted (newly added) paths."""
        accepted = []
        for p in paths:
            p = str(p)
            if Path(p).suffix.lower() not in EXT_WHITELIST:
                self._rejected.append(p)
                continue
            key = os.path.normcase(os.path.abspath(p))
            if key in self._seen:
                continue
            self._seen.add(key)
            self._items.append(ImportedImage(path=p, filename=Path(p).name))
            accepted.append(p)
        return accepted

    def add_folder(self, folder: str) -> list[str]:
        """Recursively scan a folder (whitelisted extensions, name-sorted)."""
        paths = []
        for root, dirs, files in os.walk(folder):
            dirs.sort()
            for f in sorted(files):
                if Path(f).suffix.lower() in EXT_WHITELIST:
                    paths.append(str(Path(root) / f))
        return self.add_images(paths)

    def items(self) -> list[ImportedImage]:
        return list(self._items)

    def take_rejected(self) -> list[str]:
        """Return and reset the rejected paths since the last read."""
        rejected, self._rejected = self._rejected, []
        return rejected

    def clear(self) -> None:
        self._items.clear()
        self._seen.clear()
        self._rejected.clear()
