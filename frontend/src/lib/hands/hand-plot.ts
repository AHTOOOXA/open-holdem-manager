/** Formatting for the docked hand panel ("hand plot") and the hand export, kept pure for tests. */
import { bb, signedBb } from '@/lib/format';
import type { HandDetail } from '@/lib/api';

/** Largest export the server returns; a longer list comes back capped (header X-OHM-Truncated: 1). */
export const EXPORT_MAX_HANDS = 100_000;
export const EXPORT_FILENAME = 'OHM hands.txt';

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

/** Players in seat order with the hero first when present (the panel leads with the hand's owner). */
export function plotPlayers(hand: Pick<HandDetail, 'players'>): HandDetail['players'] {
  return [...hand.players].sort((a, b) => Number(b.is_hero) - Number(a.is_hero) || a.seat - b.seat);
}

/** Text for the clipboard / the history dialog; empty hands say so instead of copying nothing. */
export function handHistoryText(hand: Pick<HandDetail, 'raw_text'>): string | null {
  const t = hand.raw_text?.trim();
  return t ? hand.raw_text : null;
}
