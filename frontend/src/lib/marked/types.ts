/**
 * Marked hands contract (frontend ↔ backend). Spec: marked-hands.md (own words).
 *
 * Two layers: a hand is MARKED for one player (hand_id + player_id, normally the hero's seat),
 * and a marked hand carries zero or more TAGS. Tags are a global, ordered catalogue (app-wide,
 * shared by all workspaces); marks belong to a workspace. Tag colours are OHM tag tokens
 * ('tag-1' … 'tag-9' → `bg-tag-N` / `text-tag-N` utilities), never hex.
 *
 * Backend: backend/app/marked_hands.py + backend/app/api/marked_hands.py. Tables
 *   tag_defs(id, name, color, position)                         — global
 *   marked_hands(workspace_id, hand_id, player_id, marked_at)   — PK (workspace_id, hand_id, player_id)
 *   marked_hand_tags(workspace_id, hand_id, player_id, tag_id, position)
 * One-time migration from the old free-text `hand_tags`: every distinct tag name becomes a tag
 * def (known preset names keep a matching colour, others get the neutral 'tag-1'), every hand that had tags is
 * marked for the workspace hero's row in that hand (fallback: the only player with known hole
 * cards, else the first player) with those tags in created_at order. `hand_tags` rows are kept
 * untouched (no longer read or written). Fresh install (no hand_tags): OHM's default catalogue.
 */

export type TagColor = 'tag-1' | 'tag-2' | 'tag-3' | 'tag-4' | 'tag-5' | 'tag-6' | 'tag-7' | 'tag-8' | 'tag-9';
export const TAG_COLORS: readonly TagColor[] = ['tag-1', 'tag-2', 'tag-3', 'tag-4', 'tag-5', 'tag-6', 'tag-7', 'tag-8', 'tag-9'];

export interface TagDef {
  id: number;
  name: string;
  color: TagColor;
  position: number; // 0-based display order (also the Tags column sort key)
}

/** A tag on a hand row (resolved, in catalogue order). */
export type TagRef = Pick<TagDef, 'id' | 'name' | 'color'>;

// ── Tag catalogue: /api/tag-defs ──────────────────────────────────────────────────────────
// GET    /api/tag-defs                           → TagDef[] (position order)
// POST   /api/tag-defs        { name?, color? }  → TagDef  (defaults "my tag", 'tag-7' (red); appended)
// PATCH  /api/tag-defs/{id}   { name?, color? }  → TagDef  (name trimmed, 1-60 chars, else 422)
// DELETE /api/tag-defs/{id}                      → 204; removes it from every marked hand (hands stay marked)
// POST   /api/tag-defs/{id}/move { direction: 'up' | 'down' } → TagDef[]
// POST   /api/tag-defs/reset                     → TagDef[] (the defaults; tags not in the defaults are
//        deleted as above)

// ── Marking: /api/hands/{hand_id}/mark?workspace_id= ───────────────────────────────────────
// PUT    body MarkBody → MarkState. Marks the hand (no-op if marked). When `tag_ids` is given it
//        REPLACES the hand's tag list (unknown ids → 422). An empty list keeps the hand marked.
// DELETE ?player_id= → 204. Unmarks (tags go too).
// player_id defaults to the hero's row in that hand (404 when the hand has no such player).
export interface MarkBody {
  player_id?: number;
  tag_ids?: number[];
}
export interface MarkState {
  hand_id: string;
  player_id: number;
  marked: boolean;
  tags: TagRef[];
}

// ── Lists ─────────────────────────────────────────────────────────────────────────────────
// GET /api/hands gains `marked` (true | false) and `tag_ids` (comma list, OR: hands carrying any
// of them; implies marked). Rows (HandListItem) carry `marked: boolean` and `tags: TagRef[]` for
// the row's player. The old `tags` / `exclude_tags` string params and the /hands/{id}/tags and
// /api/tags endpoints are removed. The hand detail (`GET /api/hands/{id}`) carries the same two
// fields.

// POST /api/marked-hands/unmark?workspace_id=  { tag_ids?: number[] } → { unmarked: number }
//      (no tag_ids = every marked hand of the workspace)
// GET  /api/marked-hands/export?workspace_id=&format=json|txt&tag_ids=1,2  → file download
//      json: MarkedExportFile; txt: the original hand histories separated by blank lines.
// POST /api/marked-hands/import?workspace_id=  multipart `files` (.json in MarkedExportFile
//      format, .txt, .zip) → MarkedImportResult. Hands go through the normal import pipeline
//      (duplicates skipped but still marked). JSON entries are marked for the named player with
//      their tags matched by name (missing tag names are created with the file's colour); .txt/.zip
//      hands are marked for the hero, no tags.
export interface MarkedExportEntry {
  site: string;
  hand_id: string;
  player: string; // username of the marked player
  tags: { name: string; color: TagColor }[];
  hand_text: string;
}
export interface MarkedExportFile {
  format: 'ohm-marked-hands';
  version: 1;
  hands: MarkedExportEntry[];
}
export interface MarkedImportResult {
  imported: number; // new hands inserted
  duplicates: number;
  marked: number; // (hand, player) pairs newly marked
  errors: number;
}
