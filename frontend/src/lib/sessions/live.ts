/** Live-session helpers: when the live state flips, the session list has to be refetched. */
import type { SessionsLive } from './types';

/** Signature of the live state; a change means the list's `is_live` flags are stale. */
export function liveSignature(l: SessionsLive | undefined): string | null {
  return l ? `${l.live ? 1 : 0}:${l.session_id ?? ''}` : null;
}

/** True when `next` differs from a known `prev` (the first answer is not a flip). */
export function liveFlipped(prev: string | null, next: string | null): boolean {
  return prev !== null && next !== null && prev !== next;
}

export const LIVE_POLL_MS = 60_000;
