/**
 * Sessions contract (frontend ↔ backend), docs: sessions.md (Hand2Note's rule, own words).
 *
 * A session is built over ALL of the player's hands (every stake/site/table of the workspace):
 * each hand covers [start, start + 180 s] (GG has no end time); sorted by start, a hand joins the
 * current session when it starts LESS than `max break` (app setting, default 10 min) after the
 * session's end, and the end becomes max(end, start + 180 s). Session end = last start + 180 s,
 * duration = end − start. Effective GG rule: a gap of ≥ 13 min between starts opens a new session.
 *
 * The date filter only picks which sessions are listed (any hand in range) and what the row's
 * Hands / Won count (in-range hands); Duration is always the whole session. Session pages use the
 * row's `filter` step and ignore the date filter.
 */
import type { Step } from '../reports/types';

export interface SessionRow {
  /** Stable key: the session's first hand id (Hand2Note renumbers; OHM needs stable URLs). */
  id: number;
  /** 1..n in chronological order over all of the player's sessions (display only). */
  number: number;
  start: string; // local naive ISO datetime of the first hand
  last_hand_at: string; // start of the last hand
  end: string; // last_hand_at + 180 s
  duration_s: number; // end − start
  is_live: boolean; // now − end ≤ max break
  hands: number; // in-range hands
  won: number; // hero net won in the hand currency ($), in-range hands
  won_ev: number; // all-in EV adjusted
  won_bb: number;
  won_ev_bb: number;
  /** Page 0 chain step: { k: 'session', start, end: last_hand_at }. */
  filter: Step;
}

export interface SessionsSummary {
  hands: number;
  duration_s: number; // sum of the rows' spans
  won: number;
  won_ev: number;
  won_bb: number;
  won_ev_bb: number;
}

export interface SessionsResponse {
  player: { id: number; username: string; site: string } | null; // null = no hero / no hands
  /** Newest first (start descending). */
  sessions: SessionRow[];
  summary: SessionsSummary | null; // only when sessions.length > 1
  max_break_minutes: number;
}

export interface SessionsQuery {
  workspace_id: number;
  player_id?: number; // default: the active hero
  date_from?: string; // ISO date, inclusive (local day)
  date_to?: string;
}

/** GET /api/sessions/live?workspace_id= → whether the hero's newest session is live (sidebar badge). */
export interface SessionsLive {
  live: boolean;
  session_id: number | null;
  /** Start of the live session (for "Live 14:05 - ..."). */
  start: string | null;
}
