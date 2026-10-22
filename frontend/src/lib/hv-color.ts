/**
 * Hand-value category colours (stat popup strength bars, Range tab).
 *
 * The backend still sends H2N's colour per category (backend/app/hand_value.py);
 * the frontend ignores it and draws OHM's token for the category key instead.
 * Tokens: `--hv-<key>` in src/index.css, the key with "_" written as "-".
 */

/** Every category key hand_value.py can send, plus "other". */
export const HV_KEYS = [
  'trash',
  'missed_trash',
  'kq_kj_qj',
  'missed_overcards',
  'ace_high',
  'overcards_akj',
  'gutshot',
  'draw',
  'missed_draw',
  'draw_pair',
  'low_pockets',
  'low_pair',
  'middle_pair',
  'tpwk',
  'tpgk',
  'tptk',
  'overpair',
  'set',
  'two_pairs_plus',
  'other',
] as const;

export type HvKey = (typeof HV_KEYS)[number];

const KNOWN: ReadonlySet<string> = new Set(HV_KEYS);

/** CSS colour for a hand-value category: `var(--hv-<key>)`, neutral `--hv-other` for an unknown key. */
export function hvColor(key: string | null | undefined): string {
  const k = key && KNOWN.has(key) ? key : 'other';
  return `var(--hv-${k.replaceAll('_', '-')})`;
}
