/** Formatting for the docked hand panel ("hand plot") and the hand export, kept pure for tests. */
import { bb, count, signedBb } from '@/lib/format';
import type { HandDetail } from '@/lib/api';

/** Largest export the server returns; a longer list comes back capped (header X-OHM-Truncated: 1). */
export const EXPORT_MAX_HANDS = 100_000;
export const EXPORT_FILENAME = 'OHM hands.txt';

/** Notice shown before an export that the server will cap; null when the whole list fits. */
export function exportCapNotice(total: number | null | undefined): string | null {
  if (total === null || total === undefined || total <= EXPORT_MAX_HANDS) return null;
  return `Only the first ${count(EXPORT_MAX_HANDS)} of ${count(total)} hands are exported`;
}

/** A bet or stack in big blinds, "6.5 bb". */
export function plotAmount(amountBb: number | null | undefined): string {
  return amountBb === null || amountBb === undefined ? '' : `${bb(amountBb, 1)} bb`;
}

export type PlotTone = 'pos' | 'neg' | 'zero';

export interface PlotResult {
  /** "Won 12.5 bb" / "Lost 3 bb" / "Broke even" */
  label: string;
  tone: PlotTone;
  /** All-in EV line ("All-in EV +10.5 bb"), only when it differs from the result. */
  ev: string | null;
}

/** The result line: what the hero (the row's player) won, plus the all-in EV when it differs. */
export function plotResult(wonBb: number, evBb?: number | null): PlotResult {
  const rounded = Math.round(wonBb * 10) / 10;
  const tone: PlotTone = rounded > 0 ? 'pos' : rounded < 0 ? 'neg' : 'zero';
  const label = tone === 'zero' ? 'Broke even' : tone === 'pos' ? `Won ${bb(rounded, 1)} bb` : `Lost ${bb(-rounded, 1)} bb`;
  const ev = evBb ?? null;
  const showEv = ev !== null && Math.abs(ev - wonBb) >= 0.05;
  return { label, tone, ev: showEv ? `All-in EV ${signedBb(ev, 1)} bb` : null };
}

/** The row's player: matched by `player_id`, else the hero (hand lists that do not mix players). */
export function rowPlayer<P extends { player_id?: number; is_hero: boolean }>(players: readonly P[], playerId?: number): P | undefined {
  return (playerId !== undefined ? players.find((p) => p.player_id === playerId) : undefined) ?? players.find((p) => p.is_hero);
}

/** Players in seat order with the row's player first (the panel leads with the hand's owner). */
export function plotPlayers(hand: Pick<HandDetail, 'players'>, playerId?: number): HandDetail['players'] {
  const owner = rowPlayer(hand.players, playerId);
  return [...hand.players].sort((a, b) => Number(b === owner) - Number(a === owner) || a.seat - b.seat);
}

/** Text for the clipboard / the history dialog; empty hands say so instead of copying nothing. */
export function handHistoryText(hand: Pick<HandDetail, 'raw_text'>): string | null {
  const t = hand.raw_text?.trim();
  return t ? hand.raw_text : null;
}
