/**
 * Import contract (frontend ↔ backend), milestone M7. Spec: databases-and-import.md §3–5, §9.
 *
 * ── 1. Jobs, cancel, date range (every streaming import) ───────────────────────────────────
 * POST /api/import/files/stream, POST /api/import/h2n, POST /api/import/tracker all accept the
 * query params `date_from` / `date_to` (ISO dates, inclusive, day-start hour applied like every
 * other day filter). Hands outside the range are skipped and counted in `out_of_range`.
 * The NDJSON stream's FIRST line is `ImportStart`; progress lines and the final line carry
 * `out_of_range`; the final line has `cancelled`.
 * POST /api/import/jobs/{job_id}/cancel → 204 (404 unknown/finished job). The import stops after
 * the batch in progress; hands already written stay (H2N does the same), finalisation runs, and
 * the stream ends with `{ type: 'done', cancelled: true, ... }`.
 */
export interface ImportStart {
  type: 'start';
  job_id: string;
  total: number; // hands found in the source (before dedup / date filtering)
}
export interface ImportProgress {
  type: 'progress';
  processed: number;
  total: number;
  imported: number;
  duplicates: number;
  errors: number;
  out_of_range: number;
  hands_per_sec: number;
}
export interface ImportDone {
  type: 'done';
  imported: number;
  duplicates: number;
  errors: number;
  out_of_range: number;
  cancelled: boolean;
  error_details: string[];
  elapsed_ms: number;
  hands_per_sec: number;
}
export type ImportEvent = ImportStart | ImportProgress | ImportDone;

/** The "Import Hand History" step shown before every manual import (date filter only). */
export interface ImportDateFilter {
  /** Relative preset id (re-derived at Apply) or undefined for a custom range / all time. */
  preset?: string;
  from?: string;
  to?: string;
}
// Remembered in localStorage `ohm.import.dateFilter` (H2N saves it on Apply). "Last Session" is not offered.

/**
 * ── 2. Auto-import (backend watcher; works in Electron and the browser dev setup) ───────────
 * Config: the generic config store, section 'auto_import' (GET/PUT/DELETE /api/config/auto_import).
 * The watcher (backend/app/auto_import.py) ticks every 1 s while enabled with ≥ 1 folder and no
 * other import/rebuild runs: it scans each folder recursively for hand-history files (.txt, .xml),
 * reads only what was appended since the last tick (per-file size / mtime / byte offset, persisted
 * so a restart does not re-read everything; a file that shrank is re-read from 0), imports new
 * hands into `workspace_id` (duplicates skipped), and bumps the data generation. A new file is
 * picked up within 2 s. Archiving (off by default in OHM — it moves the user's files): every
 * 150 s, files untouched for 5+ minutes whose hands are all in the DB move to
 * `<archive_dir>/<Site>/<YYYY>/<MM>/<DD>/<file name>` (appended if it exists).
 */
export interface AutoImportConfig {
  enabled: boolean; // default false
  workspace_id: number | null; // target workspace; null = the first workspace (UI sets the active one)
  folders: string[]; // absolute paths, de-duplicated (case-insensitive on macOS/Windows)
  archive_enabled: boolean; // default false
  archive_dir: string | null; // default null = `<home>/Documents/OHM Hand Archive`
}
/** GET /api/auto-import/status (polled by the status bar every 2 s while enabled). */
export interface AutoImportStatus {
  enabled: boolean;
  running: boolean; // a tick is importing right now
  workspace_id: number | null;
  session_hands: number; // hands auto-imported since the app started (or since it was re-enabled)
  hands_per_hour: number; // over the last 60 min
  last_import_at: string | null; // ISO datetime
  watched_files: number;
  last_error: string | null;
  /** Folders whose hand-history files exceed 50 MB (warning only; OHM keeps importing). */
  large_folders: { path: string; bytes: number }[];
}
// Electron: preload exposes `pickFolder(defaultPath?: string): Promise<string | null>` (native
// folder dialog). In the browser the section offers a path text field instead.

/**
 * ── 3. Import from another tracker's database ─────────────────────────────────────────────
 * Software: 'h2n4' (existing /api/import/h2n), 'pt4' (PokerTracker 4, PostgreSQL), 'hm3'
 * (Holdem Manager 3 — PostgreSQL like HM2/PT4 or a file; the backend decides from what it finds,
 * marked UNVERIFIED until tested on a real DB). Original hand texts are read and fed through
 * OHM's own parsers (cash games only).
 * POST /api/import/tracker/databases  body TrackerDatabasesRequest → TrackerDatabases
 *      (PostgreSQL: lists databases on the server that contain the tracker's hand-history table,
 *      with a hand count; the `postgres`/template DBs are hidden; a probe reads one hand.)
 *      A POST with a JSON body so the password never appears in a URL / access log.
 *      Defaults when a field is omitted, null or "" (the frontend omits blanks): host localhost,
 *      port 5432, user postgres, password = the tracker's stock password ('dbpass' for PT4;
 *      HM3: 'postgrespass'); the same rule applies to the import. Never logged/stored.
 *      At most 2 listings run at once: another one gets 429 with a readable `detail`. The UI
 *      searches when the dialog opens and on its "Search" button (not on every keystroke).
 * POST /api/import/tracker?workspace_id=&date_from=&date_to=  body TrackerImportRequest → NDJSON
 *      stream (ImportEvent). Errors before streaming (connection, not a tracker DB, bad date):
 *      400 with a readable `detail`. The hands are read in batches after the start line, so the
 *      job can be cancelled while reading.
 */
export type TrackerSoftware = 'pt4' | 'hm3';
export interface TrackerConnection {
  host?: string;
  port?: number;
  user?: string;
  password?: string;
}
export interface TrackerDatabase {
  name: string; // database name (PostgreSQL) or file path
  hands: number;
}
export interface TrackerDatabases {
  software: TrackerSoftware;
  databases: TrackerDatabase[];
  error: string | null; // e.g. "Could not connect to localhost:5432" (then databases = [])
}
export interface TrackerDatabasesRequest extends TrackerConnection {
  software: TrackerSoftware;
}
export interface TrackerImportRequest extends TrackerDatabasesRequest {
  database: string;
}
