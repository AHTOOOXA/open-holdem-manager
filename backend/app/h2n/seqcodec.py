"""Compact binary copy of a hand's H2N action sequence (`hand_players.h2n_seq`).

The stat popup needs every opportunity hand's annotated action sequence
(hit action, hero's next decision, bet-size buckets). Re-parsing the hand
history and rebuilding the sequence costs ~0.3 ms per hand, which made the
first popup over tens of thousands of hands take many seconds. The import
already builds the sequence, so it stores this copy once per hand (in one
player's row, see `app.h2n.compute_h2n`) and the popup decodes it instead.

`decode_sequence(encode_sequence(seq))` gives a `HandSeq` whose actions and
bookkeeping (names, positions, per-player sequences, action indexes) equal
the original, so the popup gets the same results either way. `reject` is not
kept (the popup never reads it). A blob with another format version decodes
to None and the caller falls back to re-parsing the hand history.

Layout (little-endian):
    header   B version, d big blind, d pot_total, B players, B actions,
             H length of the text block
    has_seq  one byte per player (bit s = street s)
    text     UTF-8 "name\0position\0name\0position..." (names never hold NUL)
    action   B street, B actor, B raw | eff << 4, B all-in, I flags,
             6 d: inc, to, pot, to_call, stack_left, amt_bb
"""

from __future__ import annotations

import struct

from app.h2n.sequence import FOLD, FR, OPEN, RAISE, Act, HandSeq, _NO_TYPES

__all__ = ["FORMAT_VERSION", "encode_sequence", "decode_sequence"]

FORMAT_VERSION = 2

_HEAD = struct.Struct("<BddBBH")
_ACT = struct.Struct("<BBBBI6d")
_MAX_ITEMS = 255


def encode_sequence(seq: HandSeq) -> bytes | None:
    """The sequence as bytes, or None if it does not fit the format."""
    acts = [a for street in seq.streets for a in street]
    n = len(seq.names)
    if n > _MAX_ITEMS or len(acts) > _MAX_ITEMS:
        return None
    fields = []
    for name, pos in zip(seq.names, seq.pos):
        fields.append(name)
        fields.append(pos or "")
    if any("\0" in f for f in fields):
        return None
    text = "\0".join(fields).encode("utf-8")
    if len(text) > 0xFFFF:
        return None
    has = bytes(h[0] | h[1] << 1 | h[2] << 2 | h[3] << 3 for h in seq.has_seq)
    pack = _ACT.pack
    return b"".join([
        _HEAD.pack(FORMAT_VERSION, seq.bb, seq.pot_total, n, len(acts), len(text)), has, text,
        *(pack(a.street, a.actor, a.raw | a.eff << 4, 1 if a.is_all_in else 0, a.flags,
               a.inc, a.to, a.pot, a.to_call, a.stack_left, a.amt_bb) for a in acts),
    ])


def decode_sequence(blob: bytes | memoryview | None) -> HandSeq | None:
    """Rebuild the HandSeq from `encode_sequence` output (None: not decodable)."""
    if not blob:
        return None
    buf = bytes(blob)
    if buf[0] != FORMAT_VERSION or len(buf) < _HEAD.size:
        return None
    _v, bb, pot_total, n, n_acts, text_len = _HEAD.unpack_from(buf, 0)
    off = _HEAD.size
    has_bits = buf[off:off + n]
    off += n
    fields = buf[off:off + text_len].decode("utf-8").split("\0") if n else []
    off += text_len
    if len(fields) != 2 * n or off + n_acts * _ACT.size != len(buf):
        return None
    names = fields[0::2]
    pos = fields[1::2]

    seq = HandSeq(names, pos, bb)
    seq.pot_total = pot_total
    rng = range(n)
    seq.has_seq = [[bool(h & 1), bool(h & 2), bool(h & 4), bool(h & 8)] for h in has_bits]
    own = [[[], [], [], []] for _ in rng]
    seq_end = [[0, 0, 0, 0] for _ in rng]
    fold_street = seq.fold_street
    streets = seq.streets
    first_raise_idx = seq.first_raise_idx
    open_idx = seq.open_idx
    for (s, actor, types, allin, flags, inc, to, pot, to_call, stack_left,
         amt_bb) in _ACT.iter_unpack(buf[off:]):
        acts = streets[s]
        i = len(acts)
        raw = types & 15
        eff = types >> 4
        act = Act(s, i, actor, names[actor], raw, eff, flags, pos[actor], inc, to, bb, pot,
                  to_call, stack_left, bool(allin))
        act.amt_bb = amt_bb
        acts.append(act)
        own[actor][s].append(i)
        if raw == FOLD:
            fold_street[actor] = s
        if flags & OPEN:
            open_idx[s] = i
        if eff == RAISE and first_raise_idx[s] < 0 and flags & FR:
            first_raise_idx[s] = i
    by_type = seq.by_type
    for s in range(4):
        acts = streets[s]
        if not acts:
            by_type.append(_NO_TYPES)
            continue
        idx_by_type: list[list[int]] = [[], [], [], [], []]
        for a in acts:
            idx_by_type[a.eff].append(a.idx)
        by_type.append(idx_by_type)
        nacts = len(acts)
        for p in rng:
            mine = own[p][s]
            seq_end[p][s] = mine[-1] + 1 if mine and acts[mine[-1]].raw == FOLD else nacts
    seq.own = own
    seq.seq_end = seq_end
    return seq
