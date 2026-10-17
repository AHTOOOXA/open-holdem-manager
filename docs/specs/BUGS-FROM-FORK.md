# Bugs found by the uhayate fork

Source: [uhayate/open-holdem-manager](https://github.com/uhayate/open-holdem-manager), forked 2026-09-10,
31 commits ahead of `main` as of 2026-10-16. It's a GGPoker-only personal build. The author
found these bugs while running OHM on a real database (13k+ hands, Windows) and wrote up
each one in detail. The commit hashes below point to their write-ups.

The fork's code has no license (it was forked before the AGPL commit `d7a91c4`). **Don't
cherry-pick it.** Either fix these ourselves from the descriptions or ask the author to open PRs.

Each bug was checked against `main` at `6df363c` on 2026-10-16:
**✅ confirmed** (read the code or reproduced it) · **❓ reported, not checked yet** · **➖ not reproduced**.

**2026-10-17: all 25 handled on branch `fix/fork-bugs`** (🔧 = fixed there, with regression tests;
#5 deliberately kept as is to match Hand2Note, see below).
`STAT_VERSION` 4 → 5, so every install rebuilds once on upgrade. Rebuilds are now
transactional, so a failed or interrupted one rolls back instead of emptying the tables.
Deviations from the fork's approach and new bugs found while fixing are listed at the end.

## P0 — data loss, bricked installs, wrong money

| # | Bug | Status | Where | Fork commit |
|---|---|---|---|---|
| 1 | **Closing the app can corrupt the DB permanently.** `killBackend()` calls `child.kill()` (TerminateProcess on Windows). `atexit`/`close_db()` never run, so DuckDB's WAL is left half-written. Every later launch fails while replaying it and shows only "Backend did not start in time". | ✅ 🔧 | `electron/main.js:152-163, 355-362` | `db583e7` |
| 2 | **No recovery from a bad WAL.** `get_db()` only catches `duckdb.IOException`; the WAL-replay error is an `InternalException`. One crash or power cut locks the user out with no way back in. Fix: move the WAL aside (`.wal.corrupt-<ts>`, don't delete it) and retry once. | ✅ 🔧 | `backend/app/db.py:42` | `1f02e4b` |
| 3 | **Self-deadlock on DB import.** `import_database` holds `db_lock()` and calls `close_db()`, which takes the same non-reentrant `threading.Lock`. The event loop freezes. | ✅ 🔧 | `api/import_hands.py:1059-1060`, `db.py:22,117` | `6107a90` |
| 4 | **Rebuild can wipe the stats tables.** The four `DELETE FROM` calls (`player_classifications`, `actions`, `board_cards`, `hand_players`) run *before* `BEGIN TRANSACTION`. A failure mid-rebuild leaves them empty, and every `STAT_VERSION` bump runs this path on every install. | ✅ 🔧 | `api/import_hands.py:884-892` | `6107a90` |
| 5 | **Cash Drop counted as profit.** `net_won = collected + uncalled - invested`, and GG's `collected` includes a share of the Cash Drop that nobody paid in. `cash_drop_received` is stored but never subtracted. The fork measured bb/100 at 5.31 instead of 4.68 (17 hands). It also inflates the all-in EV pot. | ➖ kept (matches H2N) | `api/import_hands.py:350-352` | `ac3f292` |
| 6 | **Fees mixed up.** `total_rake` sums Rake + Jackpot + Bingo + Fortune + Tax (`ggpoker.py:274, 552`) while jackpot is also tracked on its own. So `rake` is really "all fees" and `rake + jackpot` counts the jackpot twice. Fork: `total_rake` = pure rake, a new `total_fees` = everything. Invariant: `sum(won) == -total_fees` per hand. | ✅ 🔧 | `parsers/ggpoker.py:274, 552-557`, `api/import_hands.py:312-319` | `ac3f292` |
| 7 | **All-in EV never worked in the packaged app.** PyInstaller doesn't collect `eval7`'s Python deps (`.handrange` → `rangestring`, `pyparsing`). `import eval7` fails, `except ImportError` swallows it, and EV quietly falls back to actual winnings. Fix: `--collect-all eval7`, and log a warning instead of passing silently. | ✅ 🔧 | `.github/workflows/release.yml:66-77`, `package.json:10`, `Makefile:28`, `api/import_hands.py:24-27` | `ac3f292` |

## P1 — wrong numbers or broken parsing

| # | Bug | Status | Where | Fork commit |
|---|---|---|---|---|
| 8 | **Ante tables don't parse.** GG writes the header as `($0.02/$0.05($0.01))` and the line as `posts the ante`. `RE_HEADER` and `RE_ANTE` (`posts ante`) match neither. | ✅ 🔧 | `parsers/ggpoker.py:219-231` | `ac3f292` |
| 9 | **`sb_amount = bb_amount / 2`.** Wrong when stakes aren't 2:1. Read the SB from the header or the post line instead. | ✅ 🔧 | `parsers/ggpoker.py:404` | `ac3f292` |
| 10 | **EP/MP mean different seats per table size.** At 6-max EP is first to act; at 8-max it's second (after UTG). The fork uses `BTN SB BB UTG HJ CO` with UTG1/LJ/UTG2 at 8-9 max. Needs a migration that re-derives positions from seat order; a plain rename collides on 7-9 handed tables. | ✅ 🔧 | `parsers/common.py:47-57`, `StatsCard.tsx:14` | `ac3f292` |
| 11 | **Steal table hides CO.** `steal` counts CO+BTN+SB, but the table shows only Tot/BTN/SB, so the total can be lower than both visible columns. The three rows below it (fold to 3bet / 4bet / 4bet-fold vs steal) use BTN+SB, so their Tot doesn't match. | ✅ 🔧 | `stats_engine.py:288-291`, `components/stats/StatsCard.tsx:80-83` | `d52ee9e` |
| 12 | **`date_to` drops the last day.** `played_at <= '2026-10-15'` compares a TIMESTAMP against midnight. Make it `< date_to + 1 day` in one helper and use it everywhere. | ✅ 🔧 | `api/stats.py:103,129,251,435`, `stats_engine.py:441` (+ others) | `ac3f292` |
| 13 | **Calendar is off by a day east of UTC.** `toISOString().slice(0,10)` converts to UTC first, so in UTC+3 "Today" before 03:00 is yesterday. Matters to us: Moscow is UTC+3. | ✅ 🔧 | `components/FilterBar.tsx:102,160,333`, `hands/HandExplorer.tsx:33,37` | `ac3f292` |
| 14 | **`tags=,` → SQL syntax error.** Empty `tag_list` produces `IN ()`. Skip the clause when the list is empty; `add_tag` should reject blank tags. | ✅ 🔧 | `api/hands.py:70-81` | `ac3f292` |
| 15 | **Bet sizes rounded.** At precision 0, `Math.round` shows a 2.5 BB open as R3 and 3.5 BB as R4. Default to one decimal. | ✅ 🔧 | `components/hands/Actions.tsx:12`, `HandExplorer.tsx:328-356` | `d52ee9e` |
| 16 | **H2H rows sorted alphabetically** (`ORDER BY hero.position` → BB, BTN, CO…). Use one action-order constant. | ✅ 🔧 | `api/players.py:318` | `d52ee9e` |
| 17 | **Drilldown denominators don't match the headline stats** for `call_open_raise`, `four_bet_fold`, `call_4bet`, `wwsf`. For `wwsf`, the registry uses `action_flag: "won"`, a money column, as a boolean; the engine uses `won_bb > 0`. | ✅ (wwsf) / ❓ (others) 🔧 | `stat_registry.py:333-336` vs `stats_engine.py:165` | `b353fbc` |
| 18 | **Drift page fold-to-3bet** uses `three_bet_opp` as the denominator. That also counts players who just acted between the open and the 3-bet. Fork saw 3.7% here vs 52.8% on other pages. | ✅ (code) 🔧 | `api/reports.py:375, 485` | `ac3f292` |
| 19 | `/population/full-stats` with `player_type`: Binder error (WHERE references a table the query doesn't join; params bound twice). | ✅ 🔧 | `api/population.py` | `ac3f292` |

## P2 — robustness and small things

| # | Bug | Status | Where | Fork commit |
|---|---|---|---|---|
| 20 | DB export uses `shutil.copy2` while DuckDB holds the file open → `WinError 32` on Windows. Use `ATTACH` + `COPY FROM DATABASE`. | ✅ (code) 🔧 | `api/import_hands.py:1020` | `6107a90` |
| 21 | `hand_tags` / `hand_notes` primary keys don't include `workspace_id`. The same hand in two workspaces collides. | ✅ 🔧 | `db.py:326-335` | `b353fbc` |
| 22 | Import stream that ends without a final result reports "0 hands imported" as success. | ✅ 🔧 | `frontend/src/lib/api.ts` | `6107a90` |
| 23 | `/sessions/:index` with a non-numeric index renders an empty page instead of an error. | ✅ 🔧 | `pages/` sessions | `6107a90` |
| 24 | `tests/test_benchmark.py` fails to collect (`split_hands` import). The rest of the suite: 359 passed. | ✅ 🔧 | `backend/tests/test_benchmark.py` | `b353fbc` |
| 25 | Fresh DB init crashes because a failed `ALTER` aborts the transaction. | ➖ Not reproduced on DuckDB 1.4.4: fresh init and reopen both work. Maybe older DuckDB or a half-migrated DB. Switching to `_table_columns()` checks is still cleaner than catching exceptions. | `db.py:396-419` | `b353fbc` |

## Comment

The fork author spent a month using OHM daily on real data and found the bugs that only
show up that way: nothing crashes, the numbers are just quietly wrong (5, 6, 7, 11, 12, 13),
or the app dies once and never comes back (1, 2). Our 359 tests didn't catch any of them,
because they test parsing and flags, not money invariants or process lifecycle.

Suggested order:

1. **1 + 2 + 3 + 4 together**: graceful shutdown (`POST /api/shutdown`, Electron waits up
   to ~15s before killing), WAL quarantine on start, RLock, deletes inside the transaction.
   These are the ones that lose a user forever. Ship as a patch release.
2. **5 + 6 + 7**: money. Add the invariant test `sum(won) == -total_fees` for every
   fixture hand first, then fix. Needs a `STAT_VERSION` bump (full rebuild), so it
   goes after step 1 makes rebuilds safe.
3. **8 + 9 + 10**: parsing and positions. Get real GG ante-table exports as fixtures. The
   position rename is a data migration, so it gets its own release note.
4. **11-18**: display and filter fixes, one PR per area.
5. Check the ❓ rows before fixing them.

Also worth borrowing as ideas (not code) from the fork:
`scripts/check-electron.mjs` (`tsc --checkJs` over `electron/*.js` to catch undeclared names),
and a quit-path test that loads `main.js` with stubbed electron and asserts there's no `child.kill()`.
The Electron main process has no checks at all right now.

Contact: open an issue on our repo mentioning @uhayate, thank them, and ask whether
they'd send PRs (or allow us to use their changes under AGPL-3.0).

## How it was fixed (2026-10-17)

Fixed from the descriptions above; none of the fork's code was used.

- **1** Electron sends `POST /api/shutdown` with a per-launch token
  (`OHM_SHUTDOWN_TOKEN`, custom header, so web pages can't trigger it cross-origin) and waits up to
  15 s for the backend to exit before killing it. The backend stops any running import or rebuild
  (it rolls back), checkpoints and closes. Checked end to end: no WAL is left after quit, and a
  shutdown in the middle of a 20k-hand import rolls back cleanly.
- **2** A WAL that fails to replay is renamed to `poker.duckdb.wal.corrupt-<ts>` and the open is
  retried. The failure can be an `IOException` too, not only `InternalException`. `/api/health`
  reports it, and a banner tells the user to re-import their latest files.
- **3** `threading.RLock`.
- **4** The deletes run inside the transaction. Import and rebuild share a `_bulk_write()` context
  manager: BEGIN, COMMIT, ROLLBACK on any error, and index recreation after a failure.
- **5** **Kept as before, on purpose.** Hand2Note counts a Cash Drop as winnings for whoever
  wins the pot, and OHM matches it: the drop is real money in the player's balance, and numbers
  should agree with H2N for people switching. Invariant per hand: `sum(won) == cash_drop - fees`.
  All-in EV uses the pot including the drop. (A version that kept the drop out of winnings was
  tried and reverted.) `hands.cash_drop_received` still records the drop for the Cash Drop page.
- **6** `total_rake` is rake only; `ParsedHand.fees` covers everything. Same DB: rake drops from
  $114.30 to $91.65 (it had the $22.65 of jackpot in it twice).
- **7** `--collect-all eval7 --collect-submodules pyparsing` in all three PyInstaller commands, plus
  `ohm-backend --self-check` as a CI step after the build. Verified: the old build fails with
  `No module named 'eval7.xorshift_rand'` and the new one passes.
- **8, 9** Header and `posts the ante` regexes. The SB is read from the header or the post line,
  with 2:5 fallbacks. `$0.10/$0.25` was labelled `$0.12/$0.25`, so the stakes filter value
  changes after the rebuild.
- **10** The fork's UTG/HJ rename was not adopted. Every stat, filter and UI table is built on the
  six buckets EP/MP/CO/BTN/SB/BB, and at 7-9 handed the old labels UTG/UTG1/HJ fell outside them.
  New rule: UTG is EP, up to two seats before CO are MP, the rest is EP. 6-max labels are
  unchanged. Seats also get an `action_order`, because `stat_flags` decided IP/OOP from the label
  and gave UTG/UTG1/HJ the same order as SB.
- **11** CO, BTN and SB on all four steal rows (backend and table).
- **12, 14, 16, 18, 19** `app/date_filters.py` (`played_at < date + 1 day`, 16 call sites), empty
  tag lists, action-order sorting, matching denominators, and the population binder error.
- **17** Fixed all four, plus 9 more that `tests/test_stat_parity.py` found by comparing every
  registry stat with the engine. Missed c-bet and vs missed c-bet used `position IN ('CO','BTN')`
  as a stand-in for IP. AF/AFq are deliberately left out of the parity test (actions vs hands).
- **20** Close (checkpoint), copy, reopen under the lock. `COPY FROM DATABASE` breaks foreign keys.
- **21** These tables had no keys at all: the composite-key migration rebuilt them with
  `CREATE TABLE AS`. New unique indexes `(workspace_id, hand_id, tag)` and
  `(workspace_id, hand_id)`, with a dedupe step.
- **24** Import fix. **25** `_add_column_if_missing()` instead of catching `CatalogException`.

## Found while fixing (not in the fork's list)

- **DuckDB turns `COMMIT` into a silent `ROLLBACK` after any failed statement.** `_flush_batch`
  swallowed insert errors inside the import transaction, so one bad batch discarded the whole import
  while the UI reported it as imported. It now re-raises, and the stream sends an `error` event.
- **Auto-checkpoint was off for the whole session after any import** (`SET checkpoint_threshold =
  '10GB'` was never reset). A 20k-hand import left an 89 MB WAL, so a crash after an import put
  everything since launch at risk. It's now reset after every bulk write, followed by a checkpoint.
- **Fresh installs rebuilt everything on their second launch**, because an empty DB never recorded
  `stat_version`.
- **Donk bets were overcounted.** Any first bet by a non-aggressor counted, including a bet after the
  aggressor checked (that's a stab vs a missed c-bet). On the bench sample, Hero showed 10.7% donk
  bets when the real number is 0.
- **Money bugs in every non-GG parser**, found with the same invariant
  (`tests/test_money_invariant_sites.py`): Winamax, iPoker and partypoker credited the uncalled bet
  twice; partypoker read `raises $X` as the "to" amount; dead blinds were dropped on 888/WPN/party;
  iPoker dropped antes; PokerStars mis-keyed heads-up winners and crashed on garbled seat names.
  Before → after: winamax 19/27 → 0, ipoker 19/29 → 0, partypoker 20/254 → 0, 888 3/16 → 0,
  pokerstars 5/50 → 0, wpn 1/33 → 0.
- `add_tag` crashed with a `BinderException` (`INSERT OR IGNORE` on a table without a key).
- Open: WPN's derived rake includes an unlisted jackpot drop; 888's raise convention isn't verified
  by any fixture.

