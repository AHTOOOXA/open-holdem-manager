"""Read hand histories out of a Hand2Note 4 database folder.

Lets H2N users bring their hands over when the original hand history files
are gone. H2N 4 keeps the original hand history text of every hand it imported,
so we pull that text out and feed it to our own site parsers, exactly as if it
came from a .txt file. Nothing H2N computed is used.

Layout of <database>/hands/ (H2N 4.1):
  version            text, e.g. "4.1.226"
  hands.data.index   one little-endian int64 per hand id; the value is the
                     record's byte offset in hands.data plus one (0 = no hand)
  hands.data         records of:
                       int32   hand id (matches the index position)
                       varint  n, then n bytes of H2N's own hand structure (skipped)
                       varint  m, then m bytes of the original hand history text,
                               UTF-8, lines separated by NUL instead of newlines
                               (absent when the database was created with original
                               texts turned off: the next record starts right away)

Only the user's own databases are supported. Purchased ("vendor") databases are
encrypted and don't store the text, so they're rejected.
"""

from __future__ import annotations

import mmap
import os
import re
import struct
import sys
from collections.abc import Iterator
from pathlib import Path

SUPPORTED_MAJOR_VERSION = 4

# GGPoker hand histories sometimes have a NUL byte where a decimal point should
# be ("$15\x0096"). In H2N's copy NUL is the line separator, so that splits a
# line in two: "...($15" / "96 in chips)". A piece that starts with bare digits
# right after a line ending in "$<digits>" is the rest of that amount.
_AMOUNT_CUT = re.compile(r"\$\d+$")
_AMOUNT_REST = re.compile(r"^\d+(?:[ )]|$)")


def _to_lines(raw: str) -> str:
    lines: list[str] = []
    for piece in raw.split("\x00"):
        if lines and _AMOUNT_CUT.search(lines[-1]) and _AMOUNT_REST.match(piece):
            lines[-1] += "." + piece
        else:
            lines.append(piece)
    return "\n".join(lines)


class H2NFormatError(ValueError):
    """The folder isn't a Hand2Note 4 database we can read."""


def default_databases_dir() -> Path:
    """Where Hand2Note keeps its databases by default on this OS."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"))
    return base / "Hand2Note" / "Databases"


def _hands_dir(db_dir: Path) -> Path:
    hands = Path(db_dir) / "hands"
    if not (hands / "hands.data").is_file() or not (hands / "hands.data.index").is_file():
        raise H2NFormatError(f"Not a Hand2Note database (no hands/hands.data): {db_dir}")
    return hands


def database_version(db_dir: Path) -> str:
    version_file = _hands_dir(db_dir) / "version"
    return version_file.read_text(encoding="utf-8").strip() if version_file.is_file() else ""


def count_hands(db_dir: Path) -> int:
    """Number of hands in the database (non-empty index entries)."""
    index = (_hands_dir(db_dir) / "hands.data.index").read_bytes()
    n = len(index) // 8
    return sum(1 for a in struct.unpack(f"<{n}q", index[: n * 8]) if a > 0)


def list_databases(root: Path | None = None) -> list[dict]:
    """Hand2Note databases found under root (default: H2N's own folder)."""
    root = Path(root) if root else default_databases_dir()
    if not root.is_dir():
        return []
    found = []
    for d in sorted(p for p in root.iterdir() if p.is_dir()):
        try:
            found.append({
                "name": d.name,
                "path": str(d),
                "version": database_version(d),
                "hands": count_hands(d),
            })
        except (H2NFormatError, OSError, struct.error):
            continue
    return found


def _read_varint(buf, i: int) -> tuple[int, int]:
    result = shift = 0
    while True:
        b = buf[i]
        i += 1
        result |= (b & 0x7F) << shift
        if not b & 0x80:
            return result, i
        shift += 7
        if shift > 63:
            raise H2NFormatError(f"Bad varint at offset {i}")


def iter_hand_texts(db_dir: Path) -> Iterator[str]:
    """Yield the original hand history text of every hand in the database."""
    hands = _hands_dir(db_dir)
    version = database_version(db_dir)
    try:
        major = int(version.split(".")[0])
    except ValueError:
        major = -1
    if major != SUPPORTED_MAJOR_VERSION:
        raise H2NFormatError(
            f"Unsupported Hand2Note database version {version or 'unknown'!r} "
            f"(only {SUPPORTED_MAJOR_VERSION}.x is supported)"
        )

    index = (hands / "hands.data.index").read_bytes()
    n = len(index) // 8
    addresses = struct.unpack(f"<{n}q", index[: n * 8])
    # Where each record ends = where the next one (in file order) starts
    starts = sorted(a - 1 for a in addresses if a > 0)

    with open(hands / "hands.data", "rb") as f:
        size = os.fstat(f.fileno()).st_size
        if size == 0:
            return
        ends = dict(zip(starts, starts[1:] + [size]))
        with mmap.mmap(f.fileno(), 0, access=mmap.ACCESS_READ) as data:
            for hand_id, address in enumerate(addresses):
                if address <= 0:
                    continue
                i = address - 1
                if i + 4 > size:
                    raise H2NFormatError(f"Hand {hand_id}: offset {i} is past the end of hands.data")
                stored_id = struct.unpack_from("<i", data, i)[0]
                if stored_id != hand_id:
                    raise H2NFormatError(
                        f"Hand {hand_id}: record says {stored_id} (encrypted or unsupported database?)"
                    )
                end = ends[address - 1]
                struct_len, i = _read_varint(data, i + 4)
                i += struct_len
                if i >= end:
                    # The option is per database, so no other hand has it either
                    raise H2NFormatError(
                        "This Hand2Note database doesn't store the original hand "
                        "histories, so it can't be imported"
                    )
                text_len, i = _read_varint(data, i)
                if i + text_len > end:
                    raise H2NFormatError(f"Hand {hand_id}: text runs past the end of its record")
                raw = data[i:i + text_len]
                yield _to_lines(raw.decode("utf-8", errors="replace"))
