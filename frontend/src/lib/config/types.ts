/**
 * Configuration sections contract (frontend ↔ backend). Spec: configuration.md (own words).
 *
 * Every section saves on change (no Save button) and most have "Reset to default" (confirm
 * dialog). Generic store for JSON sections: backend/app/config_sections.py +
 * backend/app/api/config.py, rows in the `settings` table under `config.<section>` (global, not per
 * workspace). A missing key = the default.
 *
 *   GET    /api/config/{section}         → ConfigEnvelope<T>
 *   PUT    /api/config/{section}  T      → ConfigEnvelope<T> (full value; validated → 422)
 *   DELETE /api/config/{section}         → ConfigEnvelope<T> (reset to default)
 *
 * Sections served by this store: 'stat_appearance' | 'game_types' | 'color_markers'.
 * Other sections keep their own APIs:
 *   hero nicknames → /api/sites + /api/workspaces/{id}/heroes (M0)
 *   aliases        → /api/identities (+ new fields and CSV below), no reset
 *   marked tags    → /api/tag-defs (reset = POST /api/tag-defs/reset)
 *   other          → /api/app-settings (reset = DELETE /api/app-settings → defaults of
 *                    session_max_break_minutes + day_start_hour; numeric_date_format kept)
 */

export interface ConfigEnvelope<T> {
  value: T;
  default: T;
  is_default: boolean;
}

/** Stat Appearance (the H2N_APPEARANCE constants in lib/format/h2n.ts become these). */
export interface StatAppearance {
  one_decimal_below: number; // 0-100, default 10: one decimal strictly inside (-x, x)
  show_99_for_100: boolean; // default true
  leading_zero: boolean; // default false: "05" for single digits
  shorten_amounts: boolean; // default true: 1.2k
  show_sample_below: number; // int ≥ 1, default 15: show the small sample number when 0 < sample < x
  dim_below: number; // int ≥ 1, default 10: dim the value when sample < x
  vs_user_substitute_above: number; // int ≥ 0, default 50 (0 = off)
}

/** "Who is regular?" rule (one profile: OHM is NL Hold'em cash). Inclusive ranges in percent. */
export interface RegRule {
  min_hands: number; // default 10: below → fish
  vpip: [number, number]; // default [0, 35]
  pfr: [number, number]; // default [0, 30]
  vpip_minus_pfr: [number, number]; // default [0, 10]
  limp: [number, number]; // default [0, 20]
  auto_reg_hands: number; // default 20000: at or above → reg regardless of stats
}
export interface GameTypesConfig {
  reg_rule: RegRule;
}

/** Colour markers: reg/fish classes and manual player markers. Colours are tag tokens. */
export interface ColorMarker {
  id: number; // stable; defaults: 1 = "Fish" (tag-3, not regular), 2 = "Reg" (tag-7, regular)
  name: string;
  color: import('../marked/types').TagColor;
  is_regular: boolean;
}
export type ColorMarkersConfig = ColorMarker[];
// Auto marker of a player = first marker with is_regular === (player classified reg). A player's
// manual marker (players.color_tag holding a marker id as a string, set from the player dialog /
// Extras player page) overrides it. Player lists (GET /api/players, PlayerDialog, Sessions
// Players split rows are NOT required) return `reg: boolean | null` (null = no hands) and
// `marker: { id, name, color } | null`.

// ── Rebuild fingerprint ──────────────────────────────────────────────────────────────────
// The backend fingerprints every input that stored stats/classifications depend on
// (STAT_VERSION + game_types). The fingerprint of the last rebuild is stored; GET /api/health adds
// `rebuild_required: boolean` (true when they differ and the DB has hands). RebuildBanner shows
// "Rebuilding stats is required" + a "Rebuild stats" button (confirm, then the existing rebuild)
// on Reports / Statistics / Sessions / Configuration. A rebuild (and the startup auto-rebuild)
// stores the new fingerprint. Changing game_types does NOT rebuild on its own.

// ── Aliases (identities) additions ───────────────────────────────────────────────────────
// player_identities gains `is_single_person BOOLEAN DEFAULT FALSE`, `pinned BOOLEAN DEFAULT FALSE`
// (PATCH /api/identities/{id} accepts both; GET returns them + `player_count`).
// GET  /api/identities/export.csv               → text/csv, no header, one line per member:
//      `alias name, nickname, site, True|False`
// POST /api/identities/import-csv?workspace_id=  multipart `file` → { aliases: n, players: m,
//      skipped_lines: k }. Lines need ≥ 3 fields (name, nickname, site); unknown site/nickname in
//      this workspace → skipped; grouped by alias name; existing alias with that name → members
//      added (merge); single person if any line says True.

// ── System info (Databases › Data folder) ───────────────────────────────────────────────
// GET /api/system/info → { data_dir: string; db_path: string; db_size_bytes: number }
// Electron: preload exposes `openDataFolder()` (main process opens ITS OWN data dir with
// shell.openPath; the renderer never passes a path).
export interface SystemInfo {
  data_dir: string;
  db_path: string;
  db_size_bytes: number;
}
