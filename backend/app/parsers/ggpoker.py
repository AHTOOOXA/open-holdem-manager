"""
GGPoker hand history parser.

Parses a single hand history text block into structured data.
Returns a ParsedHand dataclass — does NOT write to DB or compute stat flags.
"""

import re
from dataclasses import dataclass, field
from decimal import Decimal
from datetime import datetime

SITE_ID = 1  # GGPoker

# Module-level constants to avoid per-call allocation
_ZERO = Decimal("0")
_STANDARD_BB = [
    Decimal("0.02"), Decimal("0.05"), Decimal("0.10"), Decimal("0.20"),
    Decimal("0.25"), Decimal("0.50"), Decimal("1"), Decimal("2"),
    Decimal("5"), Decimal("10"), Decimal("25"), Decimal("50"),
    Decimal("100"), Decimal("200"), Decimal("500"),
]


_STANDARD_BB_SET = set(_STANDARD_BB)


def _snap_to_nearest_standard(bb: Decimal) -> Decimal:
    """Snap a non-standard BB value to the nearest standard stake.

    GGPoker byte corruption can produce values like $0.52 instead of $0.50.
    Only snaps if within 10% of a standard stake to avoid wild guesses.
    """
    best = bb
    best_ratio = Decimal("Infinity")
    for std in _STANDARD_BB:
        if std == 0:
            continue
        ratio = abs(bb - std) / std
        if ratio < best_ratio:
            best_ratio = ratio
            best = std
    if best_ratio <= Decimal("0.10"):
        return best
    return bb


def _detect_bb(
    header_bb: Decimal,
    header_sb: Decimal,
    posted_bb: Decimal | None,
    posted_sb: Decimal | None,
    preflop_amounts: list[Decimal],
    stacks: list[Decimal],
) -> Decimal:
    """Detect the correct BB amount from multiple signals.

    GGPoker hand histories suffer from random byte corruption that can hit
    any dollar amount. Strategy:

    1. If header and posted BB agree, use that (snap if non-standard).
    2. If they disagree, use SB as tiebreaker (correct BB = 2× SB).
    3. If SB can't break the tie, use preflop action amounts to score
       which candidate produces more typical bet sizing (2-3x BB opens).
    4. If no actions, prefer the candidate supported by stack sizes.

    Candidates are restricted to header_bb, posted_bb, and their snapped
    variants — NOT all standard stakes, to avoid pulling hands to adjacent
    stakes (e.g. NL25 → NL20).
    """
    header_std = header_bb in _STANDARD_BB_SET
    posted_std = posted_bb is not None and posted_bb in _STANDARD_BB_SET

    # ── Fast path: agreement ──
    if posted_bb is not None and posted_bb == header_bb:
        bb = header_bb
        if bb not in _STANDARD_BB_SET:
            bb = _snap_to_nearest_standard(bb)
        # Both can agree on a wrong value (e.g. both corrupted to $0.52).
        # Sanity-check: if actions exist and look wildly wrong for this BB,
        # fall through to action scoring instead of returning early.
        if preflop_amounts and bb > 0:
            bad = 0
            for amt in preflop_amounts:
                ratio = amt / bb
                if ratio < Decimal("0.5") or ratio > Decimal("500"):
                    bad += 1
            if bad == 0:
                return bb
            # else: actions don't make sense at this BB — fall through
        elif stacks and bb > 0:
            # No actions, check stacks
            sorted_s = sorted(stacks)
            median = sorted_s[len(sorted_s) // 2]
            ratio = median / bb
            if Decimal("5") <= ratio <= Decimal("500"):
                return bb
            # else: stacks don't make sense — fall through
        else:
            return bb

    # ── One is standard, the other isn't ──
    if header_std and not posted_std:
        if posted_bb is None:
            return header_bb
        # posted_bb exists but is non-standard — header is probably right,
        # but verify with SB if available
        if posted_sb and posted_sb == posted_bb / 2 and posted_bb != header_bb:
            # SB supports posted — but posted is non-standard and header is.
            # Only override if actions strongly support posted.
            pass  # fall through to action scoring
        else:
            return header_bb

    if posted_std and not header_std:
        return posted_bb

    # ── Both standard but disagree ──
    if header_std and posted_std:
        # SB tiebreaker: correct BB = 2× SB
        if posted_sb and posted_sb == posted_bb / 2:
            return posted_bb
        if posted_sb and posted_sb == header_bb / 2:
            return header_bb
        if header_sb == posted_bb / 2:
            return posted_bb
        if header_sb == header_bb / 2:
            return header_bb
        # SB didn't help — fall through to action scoring

    # ── Build candidates for scoring ──
    # Start with direct BB evidence + snapped variants.
    candidates: set[Decimal] = set()
    candidates.add(header_bb)
    candidates.add(_snap_to_nearest_standard(header_bb))
    if posted_bb is not None:
        candidates.add(posted_bb)
        candidates.add(_snap_to_nearest_standard(posted_bb))
    # If header and posted agreed but failed the sanity check above,
    # the real BB is far from both. Expand to all standard stakes so
    # action/stack scoring can find the correct one.
    if posted_bb is not None and posted_bb == header_bb:
        candidates.update(_STANDARD_BB_SET)
    candidates.discard(_ZERO)

    # ── Score by preflop actions (strongest signal) ──
    if preflop_amounts and len(candidates) > 1:
        best_candidate = header_bb
        best_score = -1

        for candidate in candidates:
            score = 0
            if candidate in _STANDARD_BB_SET:
                score += 2
            for amt in preflop_amounts:
                ratio = amt / candidate
                if Decimal("1.5") <= ratio <= Decimal("5"):
                    score += 5  # Typical open/3bet sizing
                elif Decimal("0.5") <= ratio <= Decimal("30"):
                    score += 3  # Plausible (limps, 4bets)
                elif Decimal("0.5") <= ratio <= Decimal("500"):
                    score += 1
            for stack in stacks:
                ratio = stack / candidate
                if Decimal("30") <= ratio <= Decimal("200"):
                    score += 2
                elif Decimal("5") <= ratio <= Decimal("500"):
                    score += 1

            if score > best_score or (
                score == best_score
                and candidate in _STANDARD_BB_SET
                and best_candidate not in _STANDARD_BB_SET
            ):
                best_score = score
                best_candidate = candidate

        bb = best_candidate
    elif len(candidates) == 1:
        bb = next(iter(candidates))
    else:
        # No actions — use stacks as tiebreaker
        best_candidate = header_bb
        best_score = -1
        for candidate in candidates:
            score = 0
            if candidate in _STANDARD_BB_SET:
                score += 2
            for stack in stacks:
                ratio = stack / candidate
                if Decimal("30") <= ratio <= Decimal("200"):
                    score += 2
                elif Decimal("5") <= ratio <= Decimal("500"):
                    score += 1
            if score > best_score or (
                score == best_score
                and candidate in _STANDARD_BB_SET
                and best_candidate not in _STANDARD_BB_SET
            ):
                best_score = score
                best_candidate = candidate
        bb = best_candidate

    return _snap_to_nearest_standard(bb) if bb not in _STANDARD_BB_SET else bb


@dataclass
class ParsedHand:
    """Output of parsing a single hand history. Contains all extracted data."""
    hand_id: str
    site_id: int
    played_at: datetime
    game_type: str
    game_mode: str  # "Rush & Cash" or "Regular"
    stakes: str
    sb_amount: Decimal
    bb_amount: Decimal
    table_name: str
    table_size: int
    button_seat: int
    seats: list[dict]  # [{seat, username, stack, position}]
    actions_by_street: dict[str, list[dict]]
    board_cards: dict[str, list[str]]
    hero_cards: dict[str, tuple[str, str]]
    uncalled_returns: dict[str, Decimal]
    collected: dict[str, Decimal]
    total_rake: Decimal
    total_jackpot: Decimal
    went_to_showdown_players: set[str]
    in_showdown: bool
    sb_player: str | None
    bb_player: str | None
    raw_text: str
    cash_drop_received: Decimal = _ZERO
    extra_boards: list[dict[str, list[str]]] = field(default_factory=list)
    rit_boards: int = 1       # 1=normal, 2=RIT, 3=RIT3
    is_cashout: bool = False


# Position labels for 6-max (clockwise from BTN)
POSITIONS_6MAX = ["BTN", "SB", "BB", "EP", "MP", "CO"]
# For fewer players, trim from the middle positions
POSITIONS_BY_COUNT = {
    2: ["BTN", "BB"],
    3: ["BTN", "SB", "BB"],
    4: ["BTN", "SB", "BB", "CO"],
    5: ["BTN", "SB", "BB", "MP", "CO"],
    6: ["BTN", "SB", "BB", "EP", "MP", "CO"],
    7: ["BTN", "SB", "BB", "EP", "MP", "HJ", "CO"],
    8: ["BTN", "SB", "BB", "UTG", "EP", "MP", "HJ", "CO"],
    9: ["BTN", "SB", "BB", "UTG", "UTG1", "EP", "MP", "HJ", "CO"],
}

# Single combined skip regex (patterns → 1 search per line)
RE_SKIP = re.compile(
    r"is disconnected|has timed out|is sitting out|is connected|"
    r"has returned|Cashout:|was removed from the table|said,|"
    r"leaves the table|joins the table|"
    r"\*\*\* (?:FIRST|SECOND) BOARD \*\*\*|"
    r"\*\*\* (?:SECOND|THIRD) SHOWDOWN \*\*\*|"
    r"^Hand was run"
)

# Regex patterns for parsing
RE_HEADER = re.compile(
    r"Poker Hand #(\w+): (?:Tournament #\S+, )?"
    r"Hold'em No Limit \(\$([0-9.]+)/\$([0-9.]+)\)"
    r" - (\d{4}/\d{2}/\d{2} \d{2}:\d{2}:\d{2})"
)
RE_TABLE = re.compile(
    r"Table '([^']+)' (\d+)-max Seat #(\d+) is the button"
)
RE_SEAT = re.compile(
    r"Seat (\d+): (.+?) \(\$([0-9.]+) in chips\)"
)
RE_ANTE = re.compile(
    r"^(.+?): posts ante \$([0-9.]+)"
)
RE_SMALL_BLIND = re.compile(
    r"^(.+?): posts small blind \$([0-9.]+)"
)
RE_BIG_BLIND = re.compile(
    r"^(.+?): posts big blind \$([0-9.]+)"
)
RE_STRADDLE = re.compile(
    r"^(.+?): posts straddle \$([0-9.]+)"
)
RE_DEALT = re.compile(
    r"Dealt to (.+?) \[(\w{2}) (\w{2})\]"
)
RE_FOLD = re.compile(r"^(.+?): folds")
RE_CHECK = re.compile(r"^(.+?): checks")
RE_CALL = re.compile(
    r"^(.+?): calls \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_BET = re.compile(
    r"^(.+?): bets \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_RAISE = re.compile(
    r"^(.+?): raises \$([0-9.]+) to \$([0-9.]+)(?:\s+and is all-in)?"
)
RE_ALLIN_MARKER = re.compile(r"and is all-in")
RE_UNCALLED = re.compile(
    r"Uncalled bet \(\$([0-9.]+)\) returned to (.+)"
)
RE_COLLECTED = re.compile(
    r"(.+?) collected \(\$([0-9.]+)\)"
)
RE_COLLECTED_FROM_POT = re.compile(
    r"^(.+?) collected \$([0-9.]+) from (?:main |side )?pot"
)
RE_WON = re.compile(
    r"(.+?) won \(\$([0-9.]+)\)"
)
RE_BOARD = re.compile(r"Board \[(.+?)\]")
RE_SUMMARY_POT = re.compile(
    r"Total pot \$([0-9.]+)"
)
RE_SUMMARY_FEE = re.compile(
    r"(?:Rake|Jackpot|Bingo|Fortune|Tax) \$([0-9.]+)"
)
RE_SUMMARY_JACKPOT = re.compile(
    r"Jackpot \$([0-9.]+)"
)
RE_CASH_DROP = re.compile(r"Cash Drop to Pot : total \$([0-9.]+)")
RE_SUMMARY_SEAT = re.compile(
    r"Seat (\d+): (.+?)(?:\s+\(.*?\))* (?:collected|folded|showed|mucked|lost|won)"
)
# Extract username from summary seat lines — stops before position labels and action words
RE_SEAT_USERNAME = re.compile(
    r"Seat \d+: (.+?)(?:\s+\((?:button|small blind|big blind)\))?\s+(?:showed|mucked|folded|collected|won|received|bought)"
)
RE_SHOWED = re.compile(
    r"Seat (\d+): (.+?) (?:.*?)(?:showed|mucked) \[(\w{2}) (\w{2})\]"
)
RE_FLOP = re.compile(r"\*\*\* (?:FIRST )?FLOP \*\*\* \[(.+?)\]")
RE_TURN = re.compile(r"\*\*\* (?:FIRST )?TURN \*\*\* \[.+?\] \[(\w{2})\]")
RE_RIVER = re.compile(r"\*\*\* (?:FIRST )?RIVER \*\*\* \[.+?\] \[(\w{2})\]")
RE_SECOND_FLOP  = re.compile(r"\*\*\* SECOND FLOP \*\*\* \[(.+?)\]")
RE_SECOND_TURN  = re.compile(r"\*\*\* SECOND TURN \*\*\* \[.+?\] \[(\w{2})\]")
RE_SECOND_RIVER = re.compile(r"\*\*\* SECOND RIVER \*\*\* \[.+?\] \[(\w{2})\]")
RE_THIRD_FLOP   = re.compile(r"\*\*\* THIRD FLOP \*\*\* \[(.+?)\]")
RE_THIRD_TURN   = re.compile(r"\*\*\* THIRD TURN \*\*\* \[.+?\] \[(\w{2})\]")
RE_THIRD_RIVER  = re.compile(r"\*\*\* THIRD RIVER \*\*\* \[.+?\] \[(\w{2})\]")
RE_CASHOUT      = re.compile(r"Chooses to EV Cashout|Receives Cashout")
RE_SHOWDOWN = re.compile(r"\*\*\* (?:FIRST )?SHOW\s?DOWN \*\*\*")
RE_SUMMARY = re.compile(r"\*\*\* SUMMARY \*\*\*")
RE_DOES_NOT_SHOW = re.compile(r"^(.+?): does not show hand")
RE_SHOWS = re.compile(r"^(.+?): shows \[(\w{2}) (\w{2})\]")
RE_COLLECTED_WON_AMOUNT = re.compile(r"(?:collected|won) \(\$([0-9.]+)\)")


def _should_skip(line: str) -> bool:
    return RE_SKIP.search(line) is not None


def _assign_positions(seats: list[dict], button_seat: int, table_size: int) -> None:
    """Assign position labels to seated players based on button seat.

    Sorts players clockwise from button and assigns positions.
    seats is a list of dicts with 'seat' key, mutated to add 'position'.
    """
    if not seats:
        return

    num_players = len(seats)
    pos_labels = POSITIONS_BY_COUNT.get(num_players)
    if pos_labels is None:
        # Fallback for unusual counts
        pos_labels = POSITIONS_BY_COUNT.get(min(num_players, 9), POSITIONS_6MAX)

    # Sort seats clockwise starting from button
    seat_numbers = sorted(s["seat"] for s in seats)
    # Find button index
    btn_idx = None
    for i, sn in enumerate(seat_numbers):
        if sn == button_seat:
            btn_idx = i
            break
    if btn_idx is None:
        # Button seat not occupied — find the closest seat before button going backwards
        # (the seat that would act as button)
        for i in range(len(seat_numbers) - 1, -1, -1):
            if seat_numbers[i] < button_seat:
                btn_idx = i
                break
        if btn_idx is None:
            btn_idx = len(seat_numbers) - 1

    # Reorder clockwise from button
    ordered = seat_numbers[btn_idx:] + seat_numbers[:btn_idx]

    seat_to_pos = {}
    for i, sn in enumerate(ordered):
        if i < len(pos_labels):
            seat_to_pos[sn] = pos_labels[i]
        else:
            seat_to_pos[sn] = f"S{sn}"

    for s in seats:
        s["position"] = seat_to_pos[s["seat"]]


def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single GGPoker hand history into structured data.

    Returns a ParsedHand dataclass. Does NOT write to DB or compute stats.
    """
    # Strip BOM, null bytes, zero-width chars, and other invisible Unicode before parsing
    hand_text = hand_text.replace("\x00", "").replace("\ufeff", "").replace("\u200b", "").replace("\u200c", "").replace("\u200d", "")
    lines = hand_text.strip().split("\n")
    lines = [l.strip() for l in lines if l.strip()]

    # ── Parse header ──
    m = RE_HEADER.search(lines[0])
    if not m:
        raise ValueError(f"Cannot parse header line: {lines[0]}")

    hand_id = m.group(1)
    header_sb = Decimal(m.group(2))
    header_bb = Decimal(m.group(3))
    played_at = datetime.strptime(m.group(4), "%Y/%m/%d %H:%M:%S")

    # GGPoker has random byte corruption in hand history files that can hit
    # any dollar amount — header stakes, blind postings, bet sizes.
    # We use a vote-based approach: collect candidate BB values, then score
    # them by how well preflop action amounts, stack sizes, and standard-
    # stake membership agree.

    # Pre-scan: collect stacks, posted blinds, and preflop action amounts
    _scanned_stacks: list[Decimal] = []
    posted_bb: Decimal | None = None
    posted_sb: Decimal | None = None
    preflop_amounts: list[Decimal] = []
    _in_preflop = False

    for _sl in lines:
        # Stacks
        _sm = RE_SEAT.match(_sl)
        if _sm:
            _scanned_stacks.append(Decimal(_sm.group(3)))
            continue
        # Posted blinds
        if posted_bb is None:
            _bm = RE_BIG_BLIND.match(_sl)
            if _bm:
                posted_bb = Decimal(_bm.group(2))
                continue
        if posted_sb is None:
            _sbm = RE_SMALL_BLIND.match(_sl)
            if _sbm:
                posted_sb = Decimal(_sbm.group(2))
                continue
        # Preflop action amounts
        if "*** HOLE CARDS ***" in _sl:
            _in_preflop = True
            continue
        if _in_preflop:
            if _sl.startswith("***"):
                _in_preflop = False
                continue
            if _sl.startswith("Dealt "):
                continue
            _rm = RE_RAISE.match(_sl)
            if _rm:
                preflop_amounts.append(Decimal(_rm.group(3)))  # "to" amount
                continue
            _cm = RE_CALL.match(_sl)
            if _cm:
                preflop_amounts.append(Decimal(_cm.group(2)))
                continue
            _bm2 = RE_BET.match(_sl)
            if _bm2:
                preflop_amounts.append(Decimal(_bm2.group(2)))
                continue

    bb_amount = _detect_bb(
        header_bb, header_sb, posted_bb, posted_sb,
        preflop_amounts, _scanned_stacks,
    )
    sb_amount = bb_amount / 2

    def _fmt_stake(d: Decimal) -> str:
        if d == d.to_integral_value():
            return f"${int(d)}"
        return f"${d:.2f}"
    stakes = f"{_fmt_stake(sb_amount)}/{_fmt_stake(bb_amount)}"
    game_type = "NLH"

    # ── Parse table info ──
    m = RE_TABLE.search(lines[1])
    if not m:
        raise ValueError(f"Cannot parse table line: {lines[1]}")

    table_name = m.group(1)
    table_size = int(m.group(2))
    button_seat = int(m.group(3))

    # Detect game mode from hand ID prefix and table name
    if hand_id.startswith("RC") or table_name.startswith("RushAndCash"):
        game_mode = "Fast Fold"
    else:
        game_mode = ""

    # ── Parse seats ──
    seats = []  # list of {seat, username, stack}
    username_to_seat = {}
    line_idx = 2

    while line_idx < len(lines):
        m = RE_SEAT.match(lines[line_idx])
        if not m:
            break
        seat_num = int(m.group(1))
        username = m.group(2)
        stack = Decimal(m.group(3))
        seats.append({"seat": seat_num, "username": username, "stack": stack})
        username_to_seat[username] = seat_num
        line_idx += 1

    if not seats:
        raise ValueError("No seats found")

    _assign_positions(seats, button_seat, table_size)

    # Build lookup structures
    username_to_info = {s["username"]: s for s in seats}

    # ── Parse action lines ──
    # We need to track: hole cards, actions per street, board cards, collected amounts
    hero_cards = {}  # username -> (card1, card2)
    actions_by_street = {"preflop": [], "flop": [], "turn": [], "river": []}
    current_street = "preflop"
    board_cards = {"flop": [], "turn": [], "river": []}
    _board2: dict[str, list[str]] = {"flop": [], "turn": [], "river": []}
    _board3: dict[str, list[str]] = {"flop": [], "turn": [], "river": []}
    is_cashout = False
    uncalled_returns = {}  # username -> amount
    collected = {}  # username -> total amount collected
    total_rake = _ZERO
    total_jackpot = _ZERO
    cash_drop_received = _ZERO
    went_to_showdown_players = set()
    in_showdown = False
    in_summary = False

    # Track blinds/antes posted
    blinds_posted = {}  # username -> "sb" | "bb" | "straddle" | "ante"
    sb_player = None
    bb_player = None

    action_order = 0

    for line in lines[line_idx:]:
        if _should_skip(line):
            continue

        # Cash Drop line (appears before blinds)
        m = RE_CASH_DROP.search(line)
        if m:
            cash_drop_received = Decimal(m.group(1))
            continue

        # Street markers
        if line.startswith("*** HOLE CARDS ***"):
            current_street = "preflop"
            continue
        m = RE_FLOP.match(line)
        if m:
            current_street = "flop"
            cards = m.group(1).split()
            board_cards["flop"] = cards
            continue
        m = RE_TURN.match(line)
        if m:
            current_street = "turn"
            board_cards["turn"] = [m.group(1)]
            continue
        m = RE_RIVER.match(line)
        if m:
            current_street = "river"
            board_cards["river"] = [m.group(1)]
            continue

        # Second board (Run It Twice)
        m = RE_SECOND_FLOP.match(line)
        if m:
            _board2["flop"] = m.group(1).split()
            continue
        m = RE_SECOND_TURN.match(line)
        if m:
            _board2["turn"] = [m.group(1)]
            continue
        m = RE_SECOND_RIVER.match(line)
        if m:
            _board2["river"] = [m.group(1)]
            continue

        # Third board (Run It Three Times)
        m = RE_THIRD_FLOP.match(line)
        if m:
            _board3["flop"] = m.group(1).split()
            continue
        m = RE_THIRD_TURN.match(line)
        if m:
            _board3["turn"] = [m.group(1)]
            continue
        m = RE_THIRD_RIVER.match(line)
        if m:
            _board3["river"] = [m.group(1)]
            continue

        # EV Cashout detection
        if RE_CASHOUT.search(line):
            is_cashout = True
            continue

        if RE_SHOWDOWN.match(line):
            in_showdown = True
            continue
        if RE_SUMMARY.match(line):
            in_summary = True
            continue

        # Summary section parsing
        if in_summary:
            m = RE_SUMMARY_POT.search(line)
            if m:
                # Sum all fees: Rake + Jackpot + Bingo + Fortune + Tax
                for fee_m in RE_SUMMARY_FEE.finditer(line):
                    total_rake += Decimal(fee_m.group(1))
                jm = RE_SUMMARY_JACKPOT.search(line)
                if jm:
                    total_jackpot = Decimal(jm.group(1))
                continue

            # Board line fallback — populate board_cards from summary if empty
            m = RE_BOARD.search(line)
            if m:
                cards = m.group(1).split()
                if not board_cards["flop"] and len(cards) >= 3:
                    board_cards["flop"] = cards[:3]
                if not board_cards["turn"] and len(cards) >= 4:
                    board_cards["turn"] = [cards[3]]
                if not board_cards["river"] and len(cards) >= 5:
                    board_cards["river"] = [cards[4]]
                continue

            m = RE_SHOWED.match(line)
            if m:
                uname = m.group(2).strip()
                if uname in username_to_info:
                    hero_cards[uname] = (m.group(3), m.group(4))
                # Don't continue — also check for won/collected on same line (e.g. "showed [As 8h] and won ($11.00)")

            # Collected/won in summary — handle multiple "won ($X)" on same line (Run It Twice)
            seat_m = RE_SEAT_USERNAME.match(line)
            uname_from_seat = seat_m.group(1).strip() if seat_m else None

            # Find ALL won/collected amounts on this line
            found_any = False
            for m_coll in RE_COLLECTED_WON_AMOUNT.finditer(line):
                amt = Decimal(m_coll.group(1))
                uname = uname_from_seat or "unknown"
                collected[uname] = collected.get(uname, _ZERO) + amt
                found_any = True

            if found_any:
                continue
            continue

        # Dealt hole cards (skip lines like "Dealt to Player " with no cards)
        if line.startswith("Dealt to"):
            m = RE_DEALT.match(line)
            if m:
                hero_cards[m.group(1)] = (m.group(2), m.group(3))
            continue

        # Blinds / antes (before action tracking)
        m = RE_ANTE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            blinds_posted[uname] = "ante"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "ante",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_SMALL_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            sb_player = uname
            blinds_posted[uname] = "sb"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "sb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_BIG_BLIND.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            bb_player = uname
            blinds_posted[uname] = "bb"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "bb",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        m = RE_STRADDLE.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            blinds_posted[uname] = "straddle"
            action_order += 1
            actions_by_street["preflop"].append({
                "username": uname,
                "action": "straddle",
                "amount": amt,
                "is_all_in": False,
                "order": action_order,
            })
            continue

        # Uncalled bet
        m = RE_UNCALLED.match(line)
        if m:
            amt = Decimal(m.group(1))
            uname = m.group(2).strip()
            uncalled_returns[uname] = uncalled_returns.get(uname, _ZERO) + amt
            continue

        # Collected during hand body (before summary) — skip these,
        # we use the summary section as the authoritative source to avoid double-counting
        if not in_summary:
            m = RE_COLLECTED_FROM_POT.match(line) or RE_COLLECTED.search(line)
            if m:
                continue

        # Shows hand (during showdown)
        m = RE_SHOWS.match(line)
        if m:
            uname = m.group(1)
            hero_cards[uname] = (m.group(2), m.group(3))
            went_to_showdown_players.add(uname)
            continue

        # "does not show hand" — still went to showdown if in showdown section
        m = RE_DOES_NOT_SHOW.match(line)
        if m and in_showdown:
            went_to_showdown_players.add(m.group(1))
            continue

        # ── Voluntary actions ──
        is_all_in = bool(RE_ALLIN_MARKER.search(line))

        m = RE_FOLD.match(line)
        if m:
            uname = m.group(1)
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "fold",
                    "amount": _ZERO,
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_CHECK.match(line)
        if m:
            uname = m.group(1)
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "check",
                    "amount": _ZERO,
                    "is_all_in": False,
                    "order": action_order,
                })
            continue

        m = RE_CALL.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "call",
                    "amount": amt,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

        m = RE_BET.match(line)
        if m:
            uname = m.group(1)
            amt = Decimal(m.group(2))
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "bet",
                    "amount": amt,
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

        m = RE_RAISE.match(line)
        if m:
            uname = m.group(1)
            raise_to = Decimal(m.group(3))  # GGPoker shows raise TO amount
            if uname in username_to_info:
                action_order += 1
                actions_by_street[current_street].append({
                    "username": uname,
                    "action": "raise",
                    "amount": raise_to,  # Store the "to" amount
                    "is_all_in": is_all_in,
                    "order": action_order,
                })
            continue

    # Assemble extra boards from RIT data
    # A board is non-empty if ANY street has cards (RIT can start at flop, turn, or river)
    extra_boards: list[dict[str, list[str]]] = []
    if _board2["flop"] or _board2["turn"] or _board2["river"]:
        extra_boards.append(_board2)
    if _board3["flop"] or _board3["turn"] or _board3["river"]:
        extra_boards.append(_board3)
    rit_boards = 1 + len(extra_boards)

    return ParsedHand(
        hand_id=hand_id,
        site_id=SITE_ID,
        played_at=played_at,
        game_type=game_type,
        game_mode=game_mode,
        stakes=stakes,
        sb_amount=sb_amount,
        bb_amount=bb_amount,
        table_name=table_name,
        table_size=table_size,
        button_seat=button_seat,
        seats=seats,
        actions_by_street=actions_by_street,
        board_cards=board_cards,
        hero_cards=hero_cards,
        uncalled_returns=uncalled_returns,
        collected=collected,
        total_rake=total_rake,
        total_jackpot=total_jackpot,
        went_to_showdown_players=went_to_showdown_players,
        in_showdown=in_showdown,
        sb_player=sb_player,
        bb_player=bb_player,
        cash_drop_received=cash_drop_received,
        raw_text=hand_text,
        extra_boards=extra_boards,
        rit_boards=rit_boards,
        is_cashout=is_cashout,
    )
