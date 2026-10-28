"""Minimal top-level MP4 atom reader. Reads headers only, never the media."""

from __future__ import annotations

import struct
from dataclasses import dataclass
from pathlib import Path
from typing import BinaryIO, List, Optional, Tuple


@dataclass
class Layout:
    """Top-level atoms of a file, in order, as (type, offset, size)."""

    atoms: List[Tuple[str, int, int]]

    def offset_of(self, kind: str) -> Optional[int]:
        return next((off for t, off, _ in self.atoms if t == kind), None)

    @property
    def has_moov(self) -> bool:
        return self.offset_of("moov") is not None

    @property
    def is_faststart(self) -> bool:
        """True when the index comes before the media data (or there is no media data)."""
        moov, mdat = self.offset_of("moov"), self.offset_of("mdat")
        if moov is None:
            return False
        return mdat is None or moov < mdat


def _iter_atoms(f: BinaryIO, file_size: int):
    pos = 0
    while pos + 8 <= file_size:
        f.seek(pos)
        header = f.read(8)
        if len(header) < 8:
            break
        size, kind = struct.unpack(">I4s", header)
        if size == 1:  # 64-bit size follows the type
            ext = f.read(8)
            if len(ext) < 8:
                break
            size = struct.unpack(">Q", ext)[0]
        elif size == 0:  # atom runs to the end of the file
            size = file_size - pos
        if size < 8:
            raise ValueError(f"corrupt atom at offset {pos}")
        yield kind.decode("latin-1"), pos, size
        pos += size


def read_layout(path: "str | Path") -> Layout:
    path = Path(path)
    size = path.stat().st_size
    with path.open("rb") as f:
        return Layout(list(_iter_atoms(f, size)))
