# Multi-Site Parsers -- PRD

## 1. Goals & Non-Goals

### Goals

- Support importing hand histories from all major online poker sites
- Auto-detect which site a hand history file came from
- Normalize all site formats into the existing `ParsedHand` dataclass
- Zero changes to downstream stat computation (`stat_flags.py`) or stats engine
- Users can import files from multiple sites into the same workspace

### Non-Goals

- Tournament support (MTT, SNG, Spin & Go) -- cash game NLH only
- PLO or other game types
- Real-time HUD overlays
- Site-specific stat adjustments (all sites produce identical `ParsedHand` output)
- Proprietary binary format parsing (H2N `.dat`, PT4 `.db`) -- text hand histories only

---

## 2. Architecture

### 2.1 Current State

Everything is hardcoded to GGPoker:

- Single parser: `backend/app/parsers/ggpoker.py`
- `ParsedHand` dataclass lives inside `ggpoker.py` (lines 25-55)
- Position assignment logic (`_assign_positions`, `POSITIONS_BY_COUNT`) lives inside `ggpoker.py` (lines 61-70, 175-219)
- `import_hands.py` imports directly from `ggpoker` (line 6)
- Hand splitting and ID extraction use GGPoker-specific regexes (lines 32-33)
- Player lookups hardcode `site_id = 1` (line 163)

### 2.2 Target: Parser Registry Pattern

```
backend/app/parsers/
  __init__.py      # Registry: PARSERS list, detect_parser(), PARSER_BY_SITE_ID
  common.py        # ParsedHand, _assign_positions(), POSITIONS_BY_COUNT, _ZERO
  ggpoker.py       # GGPoker parser (refactored to import from common)
  pokerstars.py    # PokerStars parser
  poker888.py      # 888poker parser
  wpn.py           # Winning Poker Network (ACR/BCP)
  winamax.py       # Winamax
  ipoker.py        # iPoker network
  partypoker.py    # partypoker
```

### 2.3 Parser Interface

Each site parser module must export:

```python
# Constants
SITE_ID: int          # Matches sites table PK (GG=1, PS=2, 888=3, etc.)
SITE_CODE: str        # Short code for sites table (GG, PS, 888, WPN, WIN, IP, PP)
SITE_NAME: str        # Human-readable name

# Functions
def detect(sample: str) -> bool:
    """Return True if this text looks like it came from this site.
    Called with first ~500 chars of a file. Must be fast and unambiguous."""

def split_hands(content: str) -> list[str]:
    """Split a multi-hand file into individual hand text blocks."""

def extract_hand_id(hand_text: str) -> str | None:
    """Extract the unique hand ID from a single hand block. Used for dedup."""

def parse_hand_history(hand_text: str) -> ParsedHand:
    """Parse a single hand text block into a ParsedHand. No DB, no stat flags."""
```

### 2.4 Registry (`parsers/__init__.py`)

```python
from app.parsers import ggpoker, pokerstars, poker888, wpn, winamax, ipoker, partypoker
from app.parsers.common import ParsedHand, _assign_positions, POSITIONS_BY_COUNT

# Ordered by popularity (checked in order during detection)
PARSERS = [ggpoker, pokerstars, poker888, wpn, winamax, ipoker, partypoker]

PARSER_BY_SITE_ID = {p.SITE_ID: p for p in PARSERS}

def detect_parser(sample: str):
    """Auto-detect parser from file content. Returns parser module or None."""
    for parser in PARSERS:
        if parser.detect(sample):
            return parser
    return None
```

### 2.5 Shared Code (`parsers/common.py`)

Extracted from `ggpoker.py`:

| What | Current location | New location |
|------|-----------------|--------------|
| `ParsedHand` dataclass | `ggpoker.py:25-55` | `common.py` |
| `_assign_positions()` | `ggpoker.py:175-219` | `common.py` |
| `POSITIONS_BY_COUNT` | `ggpoker.py:61-70` | `common.py` |
| `_ZERO = Decimal("0")` | `ggpoker.py:16` | `common.py` |

All site parsers import `ParsedHand` from `common.py` and call `_assign_positions()` during parsing. Position assignment is site-independent (it only depends on seat numbers and button position, which all sites provide).

---

## 3. Import Pipeline Refactoring

### 3.1 Hardcoded GGPoker References to Fix

There are 7 locations that assume GGPoker:

| # | File:Line | Current Code | Change To |
|---|-----------|-------------|-----------|
| 1 | `import_hands.py:6` | `from app.parsers.ggpoker import parse_hand_history, ParsedHand, _ZERO` | `from app.parsers.common import ParsedHand, _ZERO` + `from app.parsers import detect_parser` |
| 2 | `import_hands.py:32` | `RE_HAND_BOUNDARY = re.compile(r'\n(?=Poker Hand #)')` | Remove. Use `parser.split_hands()` instead. |
| 3 | `import_hands.py:33` | `RE_HAND_ID = re.compile(r'Poker Hand #(\w+):')` | Remove. Use `parser.extract_hand_id()` instead. |
| 4 | `import_hands.py:163` | `WHERE site_id = 1 AND username IN (...)` | `WHERE site_id = ? AND username IN (...)` with `parsed.site_id` |
| 5 | `stats_engine.py:476` | `WHERE username = ? AND site_id = 1` | Use `get_hero_player_id()` from `db.py` (already resolves site from workspace) |
| 6 | `reports.py:26` | `WHERE username = ? AND site_id = 1` | Same -- use `get_hero_player_id()` |
| 7 | `stats.py:74` | `WHERE username = ? AND site_id = 1` | Same -- use `get_hero_player_id()` |
| 8 | `cash_drop.py:44` | `WHERE username = ? AND site_id = 1` | Same -- use `get_hero_player_id()` |

Note: `stat_flags.py` already has no site-specific code. It takes a `ParsedHand` and returns flags -- fully site-independent. The `TYPE_CHECKING` import from `ggpoker` (line 12) just needs updating to import from `common`.

### 3.2 Updated Import Flow

```
User uploads .txt/.zip files
  -> _read_uploads() extracts text (unchanged)
  -> detect_parser(content[:500]) -> parser module
  -> parser.split_hands(content) -> individual hand texts
  -> parser.extract_hand_id(hand_text) -> dedup check
  -> parser.parse_hand_history(hand_text) -> ParsedHand
  -> compute_stat_flags(parsed) -> flags        (unchanged)
  -> _compute_financials(parsed) -> financials   (unchanged)
  -> _flush_batch(db, prepared) -> DB insert     (unchanged)
```

The only change is swapping hardcoded `parse_hand_history` / `RE_HAND_BOUNDARY` / `RE_HAND_ID` calls with the detected parser's methods.

### 3.3 Mixed-Site File Handling

Users may upload files from different sites in the same import batch. Strategy:

1. Detect parser per-file (not per-hand) -- all hands in one `.txt` file are from the same site
2. If detection fails, skip the file and report an error
3. Different files in the same upload can be from different sites

### 3.4 Rebuild Path

`_run_rebuild_sync()` re-parses from `raw_text`. It currently calls `parse_hand_history()` (GGPoker). After refactoring:

1. Look up `site_id` from the `hands` row
2. Get parser via `PARSER_BY_SITE_ID[site_id]`
3. Call `parser.parse_hand_history(raw_text)`

This already works because `hands.site_id` is stored at import time.

---

## 4. Database Changes

### 4.1 Seed Additional Sites

Add to `init_schema()` in `db.py`, after the existing GGPoker seed:

```sql
INSERT OR IGNORE INTO sites VALUES (1, 'GGPoker', 'GG');       -- existing
INSERT OR IGNORE INTO sites VALUES (2, 'PokerStars', 'PS');
INSERT OR IGNORE INTO sites VALUES (3, '888poker', '888');
INSERT OR IGNORE INTO sites VALUES (4, 'WPN', 'WPN');           -- ACR, Black Chip
INSERT OR IGNORE INTO sites VALUES (5, 'Winamax', 'WIN');
INSERT OR IGNORE INTO sites VALUES (6, 'iPoker', 'IP');
INSERT OR IGNORE INTO sites VALUES (7, 'partypoker', 'PP');
```

### 4.2 No Schema Changes Required

The `hands` table already has `site_id INTEGER REFERENCES sites(id)`. The `players` table already has `UNIQUE(site_id, username)`. No new columns, indexes, or migrations needed.

### 4.3 Player Namespace

Players are scoped by `(site_id, username)`. A player named "Hero" on GGPoker and "Hero" on PokerStars are different rows. This is correct -- the same screen name on different sites is a different person.

---

## 5. Per-Site Format Specifications

### 5.1 PokerStars (SITE_ID = 2)

**Header format:**
```
PokerStars Hand #242685837462: Hold'em No Limit ($0.25/$0.50 USD) - 2023/04/15 14:23:45 ET
Table 'Aludra' 6-max Seat #3 is the button
```

**Detection marker:** Line starts with `PokerStars Hand #` or `PokerStars Zoom Hand #`

**Hand boundary:** `\n(?=PokerStars (?:Zoom )?Hand #)`

**Hand ID extraction:** `PokerStars (?:Zoom )?Hand #(\d+):`

**Action format:** Same as GGPoker -- `player: folds|checks|calls $X|bets $X|raises $X to $Y`

**Raise convention:** "raises $X to $Y" -- stores the "to" amount. Same as GGPoker.

**Zoom (fast-fold):** Header says `PokerStars Zoom Hand #` instead of `PokerStars Hand #`. Map to `game_mode = "Fast Fold"`.

**Edge cases:**
- Currency symbol varies: `$`, `EUR`, `GBP`. Parse the symbol, store amounts in the file's native currency.
- Ante games: `player: posts the ante $0.05` -- different wording from GGPoker's `posts ante`.
- All-in: `player: raises $X to $Y and is all-in` or `player: bets $X and is all-in`.
- Uncalled bet: `Uncalled bet ($X) returned to player` -- same format as GGPoker.
- Summary: `Total pot $X | Rake $Y` -- GGPoker uses `Total pot $X Main pot $X. Rake $Y` or similar.
- Timezone: Always ET (Eastern Time). Convert to UTC.

### 5.2 888poker (SITE_ID = 3)

**Header format:**
```
***** 888poker Hand History for Game 1234567890 *****
$0.25/$0.50 Blinds No Limit Holdem - *** 15 04 2023 14:23:45
Table Houston 6 Max (Real Money)
Seat 3 is the button
```

**Detection marker:** `888poker Hand History` or `***** Hand History for Game` (older format)

**Hand boundary:** `\n(?=\*{5} 888poker Hand History|\*{5} Hand History for Game)`

**Hand ID extraction:** `(?:888poker Hand History for Game|Hand History for Game) (\d+)`

**Action format:** Different syntax:
```
player folds
player checks
player calls [$0.50]
player bets [$1.00]
player raises [$2.50]    <- NOTE: this is the raise-TO amount, in brackets
```

**Raise convention:** "raises [$Y]" -- the amount in brackets is the total "to" amount. Same convention as GGPoker.

**Edge cases:**
- No colon between player name and action (unlike GGPoker/PS)
- Dollar amounts wrapped in brackets: `[$0.50]`
- Seat line format: `Seat 3: player ($25.00)` -- different from GGPoker's `Seat 3: player ($25.00 in chips)`
- Dealt cards: `Dealt to player [Ah Kd]` -- brackets, space-separated
- Board: `** Dealing Flop ** [Ah, Kd, 3c]` -- comma-separated, brackets
- Summary section format is substantially different

### 5.3 WPN / Americas Cardroom (SITE_ID = 4)

**Header format:**
```
Game Hand #738291046 - Hold'em No Limit ($0.25/$0.50) - 2023/04/15 14:23:45
Table 'Fast-Fold Table 1' 6-max Seat #3 is the button
```

**Detection marker:** `Game Hand #` at start of line (WPN-specific, not used by other sites)

**Hand boundary:** `\n(?=Game Hand #)`

**Hand ID extraction:** `Game Hand #(\d+)`

**Action format:**
```
player folds
player checks
player calls $0.50
player bets $1.00
player raises $1.50 to $2.50
```

**Raise convention: DIFFERENT** -- "raises $X to $Y" where `$X` is the **increment**, `$Y` is the total. The parser must extract `$Y` (the "to" amount) to match our convention. Most WPN hands include both values.

**Blitz (fast-fold):** Table name contains `Fast-Fold`. Map to `game_mode = "Fast Fold"`.

**Edge cases:**
- Some older WPN formats omit "to $Y" and only show the increment. In that case, the parser must track the current bet and add the increment.
- All-in: `player raises $X to $Y [all-in]` -- square brackets for all-in marker.
- `Seat N: player ($XX.XX)` -- no "in chips" suffix.

### 5.4 Winamax (SITE_ID = 5)

**Header format:**
```
Winamax Poker - CashGame - HandId: #12345678-123-1234567890 - Holdem no limit (0.25/0.50) - 2023/04/15 14:23:45 UTC
Table: 'Lyon' 6-max (real money) Seat #3 is the button
```

**Detection marker:** `Winamax Poker -` at start of line

**Hand boundary:** `\n(?=Winamax Poker -)`

**Hand ID extraction:** `HandId: #([\w-]+)` -- hyphenated compound ID

**Action format:**
```
player folds
player checks
player calls 0.50
player bets 1.00
player raises 0.50 to 2.50
```

**Raise convention:** "raises $X to $Y" -- same as GGPoker. The first amount is the increment, `to Y` is the total.

**Edge cases:**
- Euro amounts with `EUR` suffix (not `$` prefix). Parse currency symbol position.
- Cards format: `[Ah Kd]` -- same as PS.
- Board dealt inline: `*** FLOP *** [Ah Kd 3c]` -- same as PS.
- Winamax Expresso (Spin & Go) -- skip, tournaments are non-goal.

### 5.5 iPoker Network (SITE_ID = 6)

**Header format (XML-based):**
```xml
<?xml version="1.0" encoding="utf-8"?>
<session sessioncode="12345678">
<game gamecode="87654321" ...>
```

Some iPoker skins export text format similar to PokerStars. The XML variant is more common.

**Detection marker:** `<session sessioncode=` or iPoker-specific text header

**Hand boundary:** `</game>` tags (XML) or `\n(?=<game gamecode=)` within a session

**Hand ID extraction:** `gamecode="(\d+)"`

**Action format (XML):**
```xml
<action no="1" player="player1" type="1" sum="0.50"/>
<!-- type: 0=fold, 1=small blind, 2=big blind, 3=call, 4=check, 5=bet, 6=raise, 23=all-in -->
```

**Raise convention:** The `sum` attribute is the total raise-to amount.

**Edge cases:**
- XML parsing required (use `xml.etree.ElementTree`, not regex)
- Card encoding: `C7` = 7 of clubs, `SA` = Ace of spades. Map suits: S=s, H=h, D=d, C=c.
- Multiple skins (Coral, Ladbrokes, Paddy Power, Betfair) -- all use same format
- Session wrapper contains multiple `<game>` elements

### 5.6 partypoker (SITE_ID = 7)

**Header format:**
```
***** Hand History for Game 1234567890 *****
$0.25/$0.50 USD NL Texas Hold'em - Saturday, April 15, 14:23:45 EDT 2023
Table Houston (Real Money)
Seat 3 is the button
Total number of players : 6/6
```

**Detection marker:** `Hand History for Game` (distinguish from 888 by absence of `888poker`)

**Hand boundary:** `\n(?=\*{5} Hand History for Game)`

**Hand ID extraction:** `Hand History for Game (\d+)`

**Action format:**
```
player folds
player checks
player calls [$0.50 USD]
player bets [$1.00 USD]
player raises [$2.50 USD]     <- raise-TO amount
```

**Raise convention:** "raises [$Y USD]" -- the amount is the raise-to total.

**Edge cases:**
- Date format is natural language: `Saturday, April 15, 14:23:45 EDT 2023` -- requires custom date parsing
- Currency suffix inside brackets: `[$0.50 USD]`
- fastforward (fast-fold): Look for `Table ... fastforward` in table line. Map to `game_mode = "Fast Fold"`.
- Very similar to 888poker format -- detection must check for `888poker` first

---

## 6. Critical Cross-Site Difference: Raise Amounts

This is the single most important normalization concern.

### Convention Used by OHM

OHM stores raise amounts as the **total "raise to" amount**, matching GGPoker's format. In `_compute_financials()` (import_hands.py:214-219):

```python
elif action == "raise":
    already_in = street_put_in.get(uname, _ZERO)
    increment = amt - already_in      # <- amt is the "to" amount
    if increment > 0:
        player_invested[uname] += increment
    street_put_in[uname] = amt
```

### Site-by-Site Raise Semantics

| Site | Format | What parser stores |
|------|--------|--------------------|
| GGPoker | `raises $3 to $10` | `amount = 10` (the "to" value) |
| PokerStars | `raises $7 to $10` | `amount = 10` (the "to" value) |
| 888poker | `raises [$10]` | `amount = 10` (already "to" value) |
| partypoker | `raises [$10 USD]` | `amount = 10` (already "to" value) |
| Winamax | `raises 3 to 10` | `amount = 10` (the "to" value) |
| **WPN/ACR** | `raises $7 to $10` | `amount = 10` (use "to" value) |
| iPoker | `sum="10"` (XML) | `amount = 10` (already "to" value) |

**All parsers MUST store the "to" amount.** The financial computation depends on this. If a site only provides the increment, the parser must track the current bet level and compute the "to" amount before building the action dict.

### Validation

Every parser's test suite must include a raise-heavy hand and verify that `player_invested` totals match expected values after running through `_compute_financials()`.

---

## 7. Test Strategy

### 7.1 Fixture Sources

Real hand history samples from open-source repositories:

| Repository | Language | Sites Covered |
|-----------|----------|---------------|
| [HHSmithy](https://github.com/HHSmithy) | C# | PS, 888, WPN, Party, iPoker |
| [thlorenz/hhp](https://github.com/thlorenz/hhp) | JavaScript | PS, 888, WPN |
| [Manggy94/PokerBrain](https://github.com/Manggy94/PokerBrain) | Python | PS, Winamax |
| [michaelcukier/Poker-Hand-Tracker](https://github.com/michaelcukier) | Python | PS |

Place fixtures in `backend/tests/fixtures/<site>/` -- one `.txt` file per test hand.

### 7.2 Test Structure

```python
# backend/tests/test_pokerstars_parser.py
class TestPokerStarsParser:
    def test_detect(self):
        """detect() returns True for PS hands, False for others."""

    def test_split_hands(self):
        """split_hands() correctly separates multi-hand files."""

    def test_extract_hand_id(self):
        """extract_hand_id() pulls correct ID."""

    def test_basic_hand(self):
        """Full parse of a standard 6-max hand."""

    def test_zoom_hand(self):
        """Zoom hand sets game_mode='Fast Fold'."""

    def test_raise_amounts(self):
        """Raise actions store 'to' amount, financials compute correctly."""

    def test_all_in(self):
        """All-in detection and uncalled bet return."""

    def test_showdown(self):
        """Multi-player showdown with correct collected amounts."""

    def test_no_showdown(self):
        """Fold-out hand with no showdown."""

    def test_stat_flags_integration(self):
        """Parse -> compute_stat_flags() produces valid flags."""

    def test_insert_roundtrip(self):
        """Parse -> insert_parsed_hand() -> query DB -> verify data."""
```

Repeat the same structure for each site parser.

### 7.3 Cross-Parser Validation

A shared test that runs every parser's sample hands through `_compute_financials()` and verifies:

1. Sum of all `player_invested` minus uncalled returns equals sum of `collected` amounts plus rake
2. `ParsedHand` has all required fields populated
3. Position assignments are valid for the table size

### 7.4 Running Tests

```bash
cd backend && python -m pytest tests/test_pokerstars_parser.py -v
cd backend && python -m pytest tests/ -k "parser" -v    # all parsers
```

---

## 8. Migration Story

### 8.1 Importing from Other Trackers

All major trackers (Hand2Note, PokerTracker 4, Holdem Manager 3) export hand histories as standard `.txt` files in the site's native format. No proprietary format parsing is needed.

**Export paths:**
- **Hand2Note**: `File > Export > Hand Histories` -> `.txt` files per site
- **PokerTracker 4**: `View > Hand Histories` -> right-click -> `Save to File` -> `.txt`
- **Holdem Manager 3**: `Hand Histories` tab -> `Export` -> `.txt`

### 8.2 User Workflow

1. Export hand histories from existing tracker as `.txt` files
2. Upload to OHM via the Import page (drag & drop, supports `.txt` and `.zip`)
3. OHM auto-detects the site and parses -- no manual site selection needed
4. Stats appear immediately

### 8.3 Raw Hand History Folders

Most poker sites write hand histories to a local folder. Users can also import directly from these folders:

| Site | Default HH Location (Windows) | Default HH Location (macOS) |
|------|-------------------------------|----------------------------|
| PokerStars | `%LOCALAPPDATA%\PokerStars\HandHistory\` | `~/Library/Application Support/PokerStars/HandHistory/` |
| 888poker | `%APPDATA%\888poker\HandHistory\` | N/A (Windows only) |
| GGPoker | `%LOCALAPPDATA%\GGPoker\HandHistory\` | N/A (Windows only) |
| WPN/ACR | `%LOCALAPPDATA%\WPN\HandHistory\` | N/A (Windows only) |
| partypoker | `%LOCALAPPDATA%\PartyGaming\PartyPoker\HandHistory\` | N/A |

---

## 9. Rollout Plan

### Phase 1: Infrastructure (no new parsers)

1. Extract `ParsedHand`, `_assign_positions()`, `POSITIONS_BY_COUNT`, `_ZERO` into `parsers/common.py`
2. Update `ggpoker.py` to import from `common.py` (keep all functions, just change imports)
3. Add `detect()`, `split_hands()`, `extract_hand_id()` to `ggpoker.py` module-level
4. Create `parsers/__init__.py` with registry
5. Refactor `import_hands.py` to use registry (all 4 changes from section 3.1 items 1-4)
6. Fix all `site_id = 1` hardcodes (items 5-8)
7. Seed new sites in `db.py`
8. Run existing test suite -- all must pass with zero behavior change

### Phase 2: PokerStars

Highest priority -- largest player pool, most commonly exported format, closest to GGPoker format.

1. Write `parsers/pokerstars.py`
2. Add test fixtures + `test_pokerstars_parser.py`
3. Test with real PokerStars hand histories from open-source repos

### Phase 3: 888poker

Second priority -- large player pool, format is well-documented.

1. Write `parsers/poker888.py`
2. Detection must distinguish from partypoker (similar `***** Hand History` header)
3. Add test fixtures + `test_888_parser.py`

### Phase 4: WPN / Americas Cardroom

Third priority -- popular in US market. **Critical**: handle the raise-increment format.

1. Write `parsers/wpn.py`
2. Extra attention on raise amount normalization
3. Add test fixtures + `test_wpn_parser.py`

### Phase 5: Remaining Sites

Lower priority, can be released incrementally:

1. `parsers/winamax.py` -- Euro-centric, straightforward text format
2. `parsers/ipoker.py` -- XML parsing, most different from other parsers
3. `parsers/partypoker.py` -- natural-language dates, bracket amounts

Each site is independent and can ship separately once the registry infrastructure is in place.

---

## Appendix A: ParsedHand Dataclass Reference

The canonical `ParsedHand` that all parsers must produce (extracted from `ggpoker.py:25-55`):

```python
@dataclass
class ParsedHand:
    hand_id: str                                 # Site-specific unique ID
    site_id: int                                 # FK to sites table
    played_at: datetime                          # UTC timestamp
    game_type: str                               # "Hold'em No Limit"
    game_mode: str                               # "Fast Fold" or ""
    stakes: str                                  # "$0.25/$0.50"
    sb_amount: Decimal                           # 0.25
    bb_amount: Decimal                           # 0.50
    table_name: str                              # Table identifier
    table_size: int                              # Max seats (6, 9, etc.)
    button_seat: int                             # Seat number of button
    seats: list[dict]                            # [{seat, username, stack, position}]
    actions_by_street: dict[str, list[dict]]     # {preflop: [{username, action, amount, is_all_in, order}], ...}
    board_cards: dict[str, list[str]]            # {flop: [Ah, Kd, 3c], turn: [7s], river: [2h]}
    hero_cards: dict[str, tuple[str, str]]       # {username: (card1, card2)} -- known hole cards
    uncalled_returns: dict[str, Decimal]          # {username: amount} -- uncalled bets returned
    collected: dict[str, Decimal]                 # {username: amount} -- pot winnings
    total_rake: Decimal                           # Total rake taken
    total_jackpot: Decimal                        # Jackpot/promo contribution
    went_to_showdown_players: set[str]            # Players who showed cards
    in_showdown: bool                             # Whether hand reached showdown
    sb_player: str | None                         # Username of SB poster
    bb_player: str | None                         # Username of BB poster
    raw_text: str                                 # Original hand history text
    cash_drop_received: Decimal = Decimal("0")    # GGPoker-specific (0 for other sites)
    extra_boards: list[dict] = field(default_factory=list)  # RIT extra boards
    rit_boards: int = 1                           # 1=normal, 2=RIT
    is_cashout: bool = False                      # GGPoker-specific
```

### Action Dict Format

Every action in `actions_by_street` lists must be:

```python
{
    "username": str,       # Player who acted
    "action": str,         # One of: fold, check, call, bet, raise, sb, bb, ante, straddle
    "amount": Decimal,     # Dollar amount (0 for fold/check). For raise: the "to" amount.
    "is_all_in": bool,     # Whether this action put the player all-in
    "order": int,          # Sequential action number within the hand (1-indexed)
}
```

## Appendix B: Detection Priority & Disambiguation

Detection order matters because some formats are similar:

1. **GGPoker** -- `Poker Hand #RC` or `Poker Hand #TM` or `Poker Hand #HD` (GGPoker-specific prefixes)
2. **PokerStars** -- `PokerStars Hand #` or `PokerStars Zoom Hand #`
3. **888poker** -- `888poker Hand History` (must check before partypoker)
4. **partypoker** -- `Hand History for Game` (without `888poker` prefix)
5. **WPN/ACR** -- `Game Hand #`
6. **Winamax** -- `Winamax Poker -`
7. **iPoker** -- `<session sessioncode=` or XML declaration followed by `<session`

GGPoker uses `Poker Hand #` which could theoretically conflict, but GGPoker hand IDs always start with `RC`, `TM`, or `HD` prefixes, making detection unambiguous.
