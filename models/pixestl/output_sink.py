from __future__ import annotations

import zipfile
from pathlib import Path
from typing import BinaryIO, Protocol, runtime_checkable


@runtime_checkable
class OutputSink(Protocol):
    """Writes PIXEstL outputs (PNGs, ASCII STL, text) to a ZIP or a directory."""

    def open_bin(self, name: str) -> BinaryIO:
        ...

    def write_bytes(self, name: str, data: bytes) -> None:
        ...


class ZipSink:
    def __init__(self, zf: zipfile.ZipFile) -> None:
        self._zf = zf

    def open_bin(self, name: str) -> BinaryIO:
        return self._zf.open(name, "w")

    def write_bytes(self, name: str, data: bytes) -> None:
        self._zf.writestr(name, data)


class DirSink:
    def __init__(self, root: Path) -> None:
        self._root = root
        root.mkdir(parents=True, exist_ok=True)

    def open_bin(self, name: str) -> BinaryIO:
        return open(self._root / name, "wb")

    def write_bytes(self, name: str, data: bytes) -> None:
        (self._root / name).write_bytes(data)
