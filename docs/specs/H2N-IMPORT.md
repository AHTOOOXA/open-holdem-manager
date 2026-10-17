# Import from Hand2Note

Status: **shipped on `fix/fork-bugs`** (2026-10-17): reader, endpoint, UI, tests.

## Why

Most serious players OHM wants already keep years of hands in Hand2Note. The original
hand history files are often gone, so "re-import your HH folder" doesn't work for them.
A direct import from the H2N database removes the biggest reason not to switch, and it
pairs with a clear marketing moment: *"Switch from H2N in one click."*

## What it does

- Finds the user's Hand2Note 4 databases in H2N's default folder
  (`~/Library/Application Support/Hand2Note/Databases` on macOS, `%APPDATA%\Hand2Note\Databases`
  on Windows) or takes a folder path, and imports every hand into the active workspace.
- H2N 4 keeps the **original hand history text** of each hand in the user's own databases.
  OHM extracts that text and runs it through its own site parsers, the same pipeline as a
  `.txt` import. Nothing H2N computed (stats, results, HUD data) is used, so stats come out
  identical to importing the original files. Duplicates are skipped by hand id, as usual.
- Hand2Note doesn't need to be installed or running; only the database folder is read.

Out of scope: purchased/vendor databases (encrypted, no text), H2N 3.x / PostgreSQL setups,
notes, tags, HUD layouts and custom stats.

## Format (`<database>/hands/`, H2N 4.1)

| File | Contents |
|---|---|
| `version` | Text, e.g. `4.1.226`. Only major version 4 is accepted. |
| `hands.data.index` | One little-endian int64 per hand id: record offset in `hands.data` **plus one** (0 = no hand). |
| `hands.data` | Records: `int32 hand id`, `varint n` + n bytes of H2N's own hand structure (skipped), `varint m` + m bytes of the original text (UTF-8, lines separated by NUL). Databases created with original texts turned off have no text part; those are rejected with a clear error. |

GGPoker files sometimes contain a NUL byte in place of a decimal point. In H2N's copy that
NUL becomes a line break in the middle of an amount (`($15` / `96 in chips)`); the reader
joins those back (`$15.96`).

## Code

- `backend/app/parsers/h2n_db.py`: format reader (`list_databases`, `iter_hand_texts`).
- `backend/app/api/import_h2n.py`: `GET /api/import/h2n/databases`, `POST /api/import/h2n`
  (`{"path": ...}`, NDJSON progress like `/import/files/stream`).
- `frontend/src/components/H2NImportSection.tsx`: "Import from Hand2Note" in the import dialog.
- `backend/tests/test_h2n_import.py`: fixture databases are written in the same layout from
  OHM's own fixture hands; checks round trip, mixed sites, duplicates, bad versions/paths, and
  that a hand imported from H2N gives exactly the same rows as the same hand from a file.

## Results on a real database (author's machine)

75,865 hands (GGPoker Rush & Cash), all imported in ~37 s, 0 parse errors. For 13,402 hands
whose original files still existed, 13,395 texts are identical to the files; the other 7 differ
only by GG's random byte corruption (in the file or in H2N's copy).

## Rules

- Interoperability only: we read the user's own data. No Hand2Note code, assets or stat
  definition files are in this repo, and none are needed: the importer only extracts text.
