# RIT & Cashout — Current State (2026-03-06)

Status: **backend done, frontend WIP / needs rework**

---

## Backend: DONE

All original architectural problems from the first attempt are fixed. The Parse → Compute → Insert pipeline is followed correctly.

### Parser (`backend/app/parsers/ggpoker.py`)
- Detects RIT via `SECOND FLOP/TURN/RIVER` and `THIRD FLOP/TURN/RIVER` markers
- Parses extra boards into `extra_boards: list[dict]` with same `{flop, turn, river}` format as Board 1
- Computes `rit_boards` (1/2/3) from number of boards with cards
- Detects cashout via `"Chooses to EV Cashout|Receives Cashout"` regex, sets `is_cashout: bool`

### DB Schema (`backend/app/db.py`)
- `hands.rit_boards INTEGER DEFAULT 1` — stored at parse time
- `hands.is_cashout BOOLEAN DEFAULT FALSE` — stored at parse time
- `board_cards.board_number INTEGER DEFAULT 1` — Board 2/3 cards stored with `board_number=2/3`
- Migrations are idempotent, rebuild-compatible

### Import (`backend/app/api/import_hands.py`)
- Inserts `rit_boards` and `is_cashout` into hands table
- Inserts extra board cards into `board_cards` with correct `board_number`
- Rebuild path re-parses raw_text and updates both

### API (`backend/app/api/hands.py`)
- `GET /api/hands` returns `rit_boards` and `is_cashout` from DB (no raw_text scanning)
- `GET /api/hands/{id}` fetches board_cards grouped by `board_number`, returns `extra_boards: BoardCards[]`

### Models (`backend/app/models.py`)
- `HandSummary`: `rit_boards: int`, `is_cashout: bool`
- `HandDetail`: `extra_boards: list[BoardCards]`, `rit_boards: int`, `is_cashout: bool`

---

## Frontend: Badges & Text View — DONE

### HandTypeBadge.tsx
- `RitBadge` — teal "RIT" / "RIT3" with tooltip
- `CashoutBadge` — amber "$CO" with tooltip
- Works fine, keep as-is

### HandExplorer.tsx
- Badges render below hole cards when `rit_boards > 1` or `is_cashout`
- Board 1 only in list view — correct

### HandDrawer.tsx
- Badges in meta header
- ExtraBoardSection shows extra boards in text/action view
- "(EV Cashout)" label on result line

### HandActions.tsx
- ExtraBoardSection renders "Board 2" / "Board 3" sections with street-grouped cards
- Teal label, reuses StreetSection pattern

---

## Frontend: Replayer — WIP, NEEDS REWORK

This is where the problems are. Multiple iterations have left the code messy and partially broken.

### What exists now

**useReplayerState.ts:**
- `Snapshot.board` = always Board 1
- `Snapshot.board2Cards?: Record<number, string>` = slot index → Board 2 card for diverging slots
- RIT transition snapshots generated after regular streets: "Turn (2)", "River (2)", etc.
  - `buildFullExtraBoard()` fills in shared cards from Board 1
  - Finds diverging slots, groups by street, creates one snapshot per street group
  - Uses `ritPlayers` (cards revealed, no action/bet labels) for RIT transitions
  - Uses `showdownPlayers` (cards + "Won X.X" with gross collected) for Result
- Result snapshot gets `board2Cards` with Board 2's diverging cards
- `collectedBb` computed as `max(0, wonBb + investedBb)` for gross collected display

**PokerTable.tsx:**
- Two rendering modes:
  - No `board2Cards` → single row of Board 1 cards
  - Has `board2Cards` → two rows: Board 1 full, Board 2 only diverging slots (spacers for shared)
- "EV Cashout" amber badge below pot display when `isCashout` prop is true

**HandReplayer.tsx:**
- "Run It Twice" / "EV Cashout Hand" banner above table
- "(EV Cashout)" in result summary line
- Passes `isCashout` to PokerTable

### Known problems

1. **Two-row board layout is ugly.** Board 2 row has empty gaps for shared slots — looks weird with just 1-2 cards floating under a full row. Multiple layout iterations (stacked behind, small cards above, two full rows) and none look good.

2. **"Won" amounts are gross collected, not net.** Changed from `wonBb` to `collectedBb` (gross) to show all collectors in split pots. This is arguably correct for RIT display but inconsistent with the rest of the app which shows net everywhere. The computation `max(0, wonBb + investedBb)` approximates gross but ignores rake allocation nuances.

3. **No RIT hands in current test dataset.** Can't visually verify. The hand from screenshots (RushAndCash6883408) is gone. Need to import a dataset with RIT hands to test.

4. **RIT3 completely untested.** Code handles it theoretically (loops over `extra_boards`) but zero real data to verify.

5. **Cashout hands have no special replayer behavior.** Just an "EV Cashout" badge on the felt. The cashout event (player choosing to cash out, paying risk premium) isn't shown as a replayer step. It's only visible in raw text.

6. **No animation/transition effect.** Board 2 cards just appear. No fade, no slide. The `isStreetTransition: true` flag gives a 1.5x auto-play pause but visually it's just a static swap.

---

## What to do next

### Priority 1: Get test data
Import hands that include RIT. Without them, can't verify anything.

### Priority 2: Settle on a board layout
The two-row layout with spacers is the current state. Options that haven't been tried:
- **Two complete rows with labels** — "Board 1" / "Board 2" labels on the left, both rows show all 5 cards. Wasteful of space but maximally clear.
- **Single row, toggle** — show one board at a time, small "1|2" toggle to switch. Compact but hides info.
- **Accept two rows with spacers** — it works, just looks weird. Maybe adding a subtle "Board 2" label and a thin divider line would make it feel intentional.

### Priority 3: Decide on Won display
- **Option A**: Show net `wonBb` (current DB value) for all non-zero players. Consistent with rest of app. Some collectors show negative.
- **Option B**: Show gross `collectedBb` (current replayer computation). All collectors show positive. But inconsistent and the computation is approximate.
- **Option C**: Store collected amount in DB (requires schema change + rebuild). Most correct but most work.

### Priority 4: Cashout replayer step (optional)
Parse "Chooses to EV Cashout" from raw_text in the replayer and show it as a step. Low priority — the badge is enough for now.

---

## File reference

| Layer | File | Status |
|-------|------|--------|
| Parser | `backend/app/parsers/ggpoker.py` | Done |
| DB | `backend/app/db.py` | Done |
| Import | `backend/app/api/import_hands.py` | Done |
| API | `backend/app/api/hands.py` | Done |
| Models | `backend/app/models.py` | Done |
| Types | `frontend/src/lib/api.ts` | Done |
| Badges | `frontend/src/components/hands/HandTypeBadge.tsx` | Done |
| List | `frontend/src/components/hands/HandExplorer.tsx` | Done |
| Drawer | `frontend/src/components/hands/HandDrawer.tsx` | Done |
| Actions | `frontend/src/components/hands/HandActions.tsx` | Done |
| Replayer state | `frontend/src/components/hands/replayer/useReplayerState.ts` | WIP |
| Replayer table | `frontend/src/components/hands/replayer/PokerTable.tsx` | WIP |
| Replayer shell | `frontend/src/components/hands/replayer/HandReplayer.tsx` | WIP |
