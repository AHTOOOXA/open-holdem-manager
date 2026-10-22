/**
 * The H2N-style "General" screen as data: which cells exist, where they sit,
 * and which text tone each one uses. Layout: the reference
 * screenshot of Hand2Note's General screen (docs/specs/H2N-COMPATIBLE-STATS.md §3.6, §4).
 *
 * Cell ids are `section.stat.column` (e.g. `preflop.open_raise.EP`). They are
 * the contract with the backend: GET /api/general returns `cells[id]` for
 * every id in GENERAL_CELL_IDS. The backend mirrors this list in
 * backend/app/general_cells.py. Every grid position has its own id, even
 * when two positions show the same underlying stat; `sameAs` names the id
 * whose numbers it repeats so the backend can compute it once.
 *
 * Columns: `Total`, `EP`, `MP`, `CO`, `BTN`, `SB`, `BB` for positional stats;
 * `Flop`, `Turn`, `River` for the street a postflop stat measures;
 * `Fold`/`Call`/`Raise` for the vs-C-Bet response grid.
 */

import type { H2NUnits } from './h2n-format';

// ── Tones ──────────────────────────────────────────────────────────

/** Text role of a layout cell; the value never changes it (win rate aside, see GeneralGrid). */
export type GeneralTone =
  | 'title'
  | 'heading'
  | 'value'
  | 'ep'
  | 'mp'
  | 'co'
  | 'btn'
  | 'sb'
  | 'bb'
  | 'flop'
  | 'turn'
  | 'river'
  | 'winrate';

/**
 * Text colour class per tone (OHM tokens, src/index.css). Same places as
 * Hand2Note: labels / column titles muted, headings and Total columns in the
 * foreground, positional columns in their position colour, postflop columns
 * in their street colour. `winrate` is the zero tone here; the stat cell
 * picks money-pos / money-neg from the value.
 */
export const GENERAL_TONE_CLASS: Record<GeneralTone, string> = {
  title: 'text-muted-foreground', // row labels, column headers
  heading: 'text-foreground', // PRE-FLOP / POSTFLOP and block headings
  value: 'text-foreground', // Total columns, right list, showdown rows, top-line values
  ep: 'text-pos-ep',
  mp: 'text-pos-mp',
  co: 'text-pos-co',
  btn: 'text-pos-btn',
  sb: 'text-pos-sb',
  bb: 'text-pos-bb',
  flop: 'text-street-flop',
  turn: 'text-street-turn',
  river: 'text-street-river',
  winrate: 'text-money-zero',
};

// ── Cell metadata ──────────────────────────────────────────────────

export type GeneralColumn =
  | 'Total' | 'EP' | 'MP' | 'CO' | 'BTN' | 'SB' | 'BB'
  | 'Flop' | 'Turn' | 'River'
  | 'Fold' | 'Call' | 'Raise';

/**
 * - `action`: counted from action rows (cases / opportunities). Clicking opens the stat popup.
 * - `expression`: arithmetic over other stats. Clicking only highlights the cell.
 */
export type GeneralCellKind = 'action' | 'expression';

export interface GeneralCellMeta {
  id: string;
  section: 'summary' | 'preflop' | 'steal' | 'postflop';
  /** Stat key inside the section (the middle part of the id). */
  stat: string;
  column: GeneralColumn;
  /** Full name, used for the popup title and tooltips. */
  name: string;
  kind: GeneralCellKind;
  units: H2NUnits;
  /** Which popup variant the cell opens (preflop range vs postflop hand values). */
  street: 'preflop' | 'postflop';
  /** This position repeats the numbers of another cell id (same underlying stat). */
  sameAs?: string;
  /** Short formula description shown as a tooltip on expression cells. */
  formula?: string;
}

const cells: GeneralCellMeta[] = [];

function def(
  section: GeneralCellMeta['section'],
  stat: string,
  column: GeneralColumn,
  name: string,
  extra: Partial<Pick<GeneralCellMeta, 'kind' | 'units' | 'street' | 'sameAs' | 'formula'>> = {},
): string {
  const id = `${section}.${stat}.${column}`;
  cells.push({
    id,
    section,
    stat,
    column,
    name,
    kind: extra.kind ?? 'action',
    units: extra.units ?? 'percent',
    street: extra.street ?? (section === 'postflop' ? 'postflop' : 'preflop'),
    sameAs: extra.sameAs,
    formula: extra.formula,
  });
  return id;
}

type PosCol = 'Total' | 'EP' | 'MP' | 'CO' | 'BTN' | 'SB' | 'BB';
/** Columns of a positional row, in order: `true` = its own stat, or the cell id it repeats. */
type PosCols = Partial<Record<PosCol, true | { sameAs: string }>>;

/** Define a positional row; returns the ids by column. */
function positional(
  section: 'preflop' | 'steal',
  stat: string,
  label: string,
  cols: PosCols,
): Partial<Record<PosCol, string>> {
  const out: Partial<Record<PosCol, string>> = {};
  for (const col of Object.keys(cols) as PosCol[]) {
    const v = cols[col]!;
    const name = col === 'Total' ? label : `${label}: ${col}`;
    out[col] = v === true ? def(section, stat, col, name) : defSameAs(section, stat, col, name, v.sameAs);
  }
  return out;
}

/** A position that repeats another cell's stat. */
function defSameAs(section: GeneralCellMeta['section'], stat: string, column: GeneralColumn, name: string, target: string) {
  const ref = cells.find((c) => c.id === target);
  if (!ref) throw new Error(`h2n-layout: unknown sameAs target ${target}`);
  return def(section, stat, column, name, { sameAs: target });
}

// Summary (top line)
const SUMMARY = {
  hands: def('summary', 'hands', 'Total', 'Hands', { kind: 'expression', units: 'count', formula: 'Hands' }),
  bb100: def('summary', 'bb100', 'Total', 'Win Rate (bb/100)', {
    kind: 'expression',
    units: 'bb100',
    formula: 'Win Rate (bb/100)',
  }),
  vpip: def('summary', 'vpip', 'Total', 'VPIP'),
  pfr: def('summary', 'pfr', 'Total', 'PFR'),
};

// PRE-FLOP left block
const OR = positional('preflop', 'open_raise', 'Open Raise', {
  Total: true, EP: true, MP: true, CO: true, BTN: true, SB: true,
});
const F3B = positional('preflop', 'fold_to_3bet', 'Fold to 3Bet', {
  Total: true, EP: true, MP: true, CO: true, BTN: true, SB: true,
});
const COR = positional('preflop', 'call_open_raise', 'Call Open Raise', {
  Total: true, EP: true, MP: true, CO: true, BTN: true, SB: true, BB: true,
});
const TB = positional('preflop', 'three_bet', '3-Bet', {
  Total: true, EP: true, MP: true, CO: true, BTN: true, SB: true, BB: true,
});
// EP..BTN repeat the 3-Bet row (those stats have no position test despite the row label).
const TBIP = positional('preflop', 'three_bet_ip', '3-Bet In Position', {
  Total: true,
  EP: { sameAs: TB.EP! }, MP: { sameAs: TB.MP! }, CO: { sameAs: TB.CO! }, BTN: { sameAs: TB.BTN! },
  BB: true,
});
const TBOOP = positional('preflop', 'three_bet_oop', '3-Bet Out of Position', {
  Total: true, SB: { sameAs: TB.SB! }, BB: true,
});

// PRE-FLOP right list
const RIGHT = {
  four_bet: def('preflop', 'four_bet', 'Total', '4-Bet'),
  four_bet_range: def('preflop', 'four_bet_range', 'Total', '4-Bet Range', {
    kind: 'expression',
    formula: 'Open Raise % × 4-Bet % / 100',
  }),
  four_bet_fold: def('preflop', 'four_bet_fold', 'Total', '4-Bet-Fold'),
  fold_to_4bet: def('preflop', 'fold_to_4bet', 'Total', 'Fold to 4-Bet'),
  call_4bet: def('preflop', 'call_4bet', 'Total', 'Call 4-Bet'),
  five_bet: def('preflop', 'five_bet', 'Total', '5-Bet'),
  limp: def('preflop', 'limp', 'Total', 'Limp'),
  limp_fold: def('preflop', 'limp_fold', 'Total', 'Limp-Fold'),
  squeeze: def('preflop', 'squeeze', 'Total', 'Squeeze'),
};

// Steal / vs. Steal
const ST = positional('steal', 'steal', 'Steal', { Total: true, BTN: true, SB: true });
const STF3B = positional('steal', 'fold_to_3bet', 'Steal: Fold to 3Bet', {
  Total: true, BTN: { sameAs: F3B.BTN! }, SB: true,
});
const ST4B = positional('steal', 'four_bet', 'Steal: 4-Bet', { Total: true, BTN: true, SB: true });
const ST4BF = positional('steal', 'four_bet_fold', 'Steal: 4-Bet-Fold', { Total: true, BTN: true, SB: true });
const VSF = positional('steal', 'vs_steal_fold', 'vs. Steal: Fold', { SB: true, BB: true });
const VSC = positional('steal', 'vs_steal_call', 'vs. Steal: Call', { SB: true, BB: true });
const VS3 = positional('steal', 'vs_steal_3bet', 'vs. Steal: 3-Bet', { SB: true, BB: true });

// POSTFLOP
type Street = 'Flop' | 'Turn' | 'River';
function streets(stat: string, label: string, extra: Parameters<typeof def>[4] = {}): Record<Street, string> {
  return {
    Flop: def('postflop', stat, 'Flop', `${label}: Flop`, extra),
    Turn: def('postflop', stat, 'Turn', `${label}: Turn`, extra),
    River: def('postflop', stat, 'River', `${label}: River`, extra),
  };
}

const CB = streets('cbet', 'Continuation Bet');
const FCB = streets('fold_to_cbet', 'Fold to Continuation Bet');
const AF = streets(
  'af',
  'Aggression',
  { kind: 'expression', formula: '(hands with a bet + hands with a raise) / hands with a call' },
);
const AFQ = streets(
  'afq',
  'Aggression Frequency',
  { kind: 'expression', formula: 'hands with a bet or raise / hands with any action on the street' },
);
const DONK = streets('donk', 'Donk Bet');

const VSCB_RAISED = {
  Fold: defSameAs('postflop', 'vs_cbet_raised', 'Fold', 'vs. Continuation Bet Flop, Raised Pot: Fold', FCB.Flop),
  Call: def('postflop', 'vs_cbet_raised', 'Call', 'vs. Continuation Bet Flop, Raised Pot: Call'),
  Raise: def('postflop', 'vs_cbet_raised', 'Raise', 'vs. Continuation Bet Flop, Raised Pot: Raise'),
};
const VSCB_3BET = {
  Fold: def('postflop', 'vs_cbet_3bet', 'Fold', 'vs. Continuation Bet Flop, 3-Bet Pot: Fold'),
  Call: def('postflop', 'vs_cbet_3bet', 'Call', 'vs. Continuation Bet Flop, 3-Bet Pot: Call'),
  Raise: def('postflop', 'vs_cbet_3bet', 'Raise', 'vs. Continuation Bet Flop, 3-Bet Pot: Raise'),
};

const MISSED = {
  total: def('postflop', 'missed_cbet', 'Flop', 'Missed Continuation Bet'),
  ip: def('postflop', 'missed_cbet_ip', 'Flop', 'Missed Continuation Bet: In Position'),
  ipFold: def('postflop', 'missed_cbet_ip_fold', 'Turn', 'Missed Continuation Bet: In Position → Fold'),
  oop: def('postflop', 'missed_cbet_oop', 'Flop', 'Missed Continuation Bet: Out of Position'),
  oopFold: def('postflop', 'missed_cbet_oop_fold', 'Flop', 'Missed Continuation Bet: Out of Position → Fold'),
};
const VS_MISSED = {
  total: def('postflop', 'vs_missed_cbet', 'Flop', 'vs. Missed Continuation Bet', {
    kind: 'expression',
    formula: 'bet when the preflop raiser skips the c-bet (flop in position, or turn after a checked flop)',
  }),
  betIp: def('postflop', 'vs_missed_cbet_bet_ip', 'Flop', 'vs. Missed Continuation Bet: Bet In Position'),
  checkFoldIp: def(
    'postflop',
    'vs_missed_cbet_check_fold_ip',
    'Turn',
    'vs. Missed Continuation Bet: Check | Fold (In Position)',
  ),
  betOop: def('postflop', 'vs_missed_cbet_bet_oop', 'Turn', 'vs. Missed Continuation Bet: Bet Out of Position Turn'),
  checkFoldOop: def(
    'postflop',
    'vs_missed_cbet_check_fold_oop',
    'Turn',
    'vs. Missed Continuation Bet: Check-Fold (Out of Position)',
  ),
};
const SHOWDOWN = {
  wtsd: def('postflop', 'wtsd', 'Total', 'Went to Showdown', {
    kind: 'expression',
    formula: 'hands that went to showdown / hands with a flop action',
  }),
  wsd: def('postflop', 'wsd', 'Total', 'Won at Showdown', {
    kind: 'expression',
    formula: 'showdowns won / showdowns (preflop all-ins included)',
  }),
  wwsf: def('postflop', 'wwsf', 'Total', 'Won When Saw Flop', {
    kind: 'expression',
    formula: 'hands won / hands with a flop action',
  }),
};

/** Every cell the screen shows, keyed by id. */
export const GENERAL_CELLS: Readonly<Record<string, GeneralCellMeta>> = Object.freeze(
  Object.fromEntries(cells.map((c) => [c.id, c])),
);

/** The backend contract: ids GET /api/general must return. */
export const GENERAL_CELL_IDS: readonly string[] = Object.freeze(cells.map((c) => c.id));

export const SUMMARY_CELL_IDS = SUMMARY;

// ── Layout ─────────────────────────────────────────────────────────

export type CellAlign = 'left' | 'center';

export type LayoutCell =
  | { type: 'empty'; span?: number }
  | { type: 'text'; text: string; tone: GeneralTone; section?: boolean; align?: CellAlign; span?: number }
  | { type: 'stat'; id: string; tone: GeneralTone; align?: CellAlign; span?: number }
  | { type: 'nickname'; tone: GeneralTone };

export interface LayoutTable {
  id: string;
  columns: number;
  /** grid-template-columns override; default `repeat(columns, auto)`. */
  tracks?: string[];
  /** Extra space under the table, on top of the page gap. */
  marginBottom?: number;
  rows: LayoutCell[][];
}

const E: LayoutCell = { type: 'empty' };

function empties(n: number): LayoutCell[] {
  return Array.from({ length: n }, () => E);
}

/** Row label / column header in the title (muted) tone. */
function label(text: string, align: CellAlign = 'left', span?: number): LayoutCell {
  return { type: 'text', text, tone: 'title', align, span };
}

function heading(text: string, span?: number): LayoutCell {
  return { type: 'text', text, tone: 'heading', align: 'left', span };
}

function section(text: string): LayoutCell {
  return { type: 'text', text, tone: 'heading', section: true, align: 'left' };
}

function stat(id: string | undefined, tone: GeneralTone, align: CellAlign = 'center', span?: number): LayoutCell {
  if (!id) return E;
  return { type: 'stat', id, tone, align, span };
}

const POS_TONES: Record<PosCol, GeneralTone> = {
  Total: 'value', EP: 'ep', MP: 'mp', CO: 'co', BTN: 'btn', SB: 'sb', BB: 'bb',
};

function posCells(ids: Partial<Record<PosCol, string>>, cols: PosCol[], overrides: Partial<Record<PosCol, GeneralTone>> = {}) {
  return cols.map((c) => stat(ids[c], overrides[c] ?? POS_TONES[c]));
}

const PRE_COLS: PosCol[] = ['Total', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];

/**
 * Top line: nickname, hands, bb/100, VPIP, PFR. Tracks reproduce the measured
 * screenshot positions (the hands value centres on the PRE-FLOP Total column,
 * bb/100 on the CO column, the PFR value starts at the right-list value column).
 */
const SUMMARY_TABLE: LayoutTable = {
  id: 'summary',
  columns: 9,
  // minmax(px, auto): the measured widths are minimums, so a long nickname or a
  // wider fallback font grows its track instead of overflowing into the next.
  tracks: ['135px', '38px', '72px', '29px', '84px', '37px', '56px', '56px'].map((w) => `minmax(${w}, auto)`).concat('auto'),
  marginBottom: 8,
  rows: [
    [
      { type: 'nickname', tone: 'value' },
      stat(SUMMARY.hands, 'value'),
      label('hands'),
      stat(SUMMARY.bb100, 'winrate'),
      label('bb/100'),
      label('VPIP'),
      stat(SUMMARY.vpip, 'value', 'left'),
      label('PFR'),
      stat(SUMMARY.pfr, 'value', 'left'),
    ],
  ],
};

const RIGHT_LIST: [string, string][] = [
  ['4-Bet', RIGHT.four_bet],
  ['4-Bet Range', RIGHT.four_bet_range],
  ['4-Bet-Fold', RIGHT.four_bet_fold],
  ['Fold to 4-Bet', RIGHT.fold_to_4bet],
  ['Call 4-Bet', RIGHT.call_4bet],
  ['5-Bet', RIGHT.five_bet],
  ['Limp', RIGHT.limp],
  ['Limp-Fold', RIGHT.limp_fold],
  ['Squeeze', RIGHT.squeeze],
];

function rightList(i: number): LayoutCell[] {
  const [text, id] = RIGHT_LIST[i];
  return [E, label(text), stat(id, 'value', 'left')];
}

/** PRE-FLOP: label + 7 positional columns, a 59px gap, then the label/value list. */
const PREFLOP_TABLE: LayoutTable = {
  id: 'preflop',
  columns: 11,
  tracks: ['auto', 'auto', 'auto', 'auto', 'auto', 'auto', 'auto', 'auto', '59px', 'auto', 'auto'],
  rows: [
    [section('PRE-FLOP'), ...PRE_COLS.map((c) => label(c, 'center')), ...rightList(0)],
    [label('Open Raise'), ...posCells(OR, PRE_COLS), ...rightList(1)],
    [label('Fold to 3Bet'), ...posCells(F3B, PRE_COLS), ...rightList(2)],
    [label('Call Open Raise'), ...posCells(COR, PRE_COLS), ...rightList(3)],
    // The reference draws 3-Bet / BB in the value tone rather than the BB column colour.
    [label('3-Bet'), ...posCells(TB, PRE_COLS, { BB: 'value' }), ...rightList(4)],
    [label('3-Bet In Position'), ...posCells(TBIP, PRE_COLS), ...rightList(5)],
    [label('3-Bet Out of Position'), ...posCells(TBOOP, PRE_COLS), ...rightList(6)],
    [...empties(8), ...rightList(7)],
    [...empties(8), ...rightList(8)],
  ],
};

/** Steal table: Total/BTN/SB, an 8px spacer, then vs. Steal SB/BB. */
const STEAL_TABLE: LayoutTable = {
  id: 'steal',
  columns: 8,
  rows: [
    [E, label('Total', 'center'), label('BTN', 'center'), label('SB', 'center'), E, label('vs. Steal'), label('SB', 'center'), label('BB', 'center')],
    [label('Steal'), ...posCells(ST, ['Total', 'BTN', 'SB']), E, label('Fold'), ...posCells(VSF, ['SB', 'BB'])],
    [label('Fold to 3Bet'), ...posCells(STF3B, ['Total', 'BTN', 'SB']), E, label('Call'), ...posCells(VSC, ['SB', 'BB'])],
    [label('4-Bet'), ...posCells(ST4B, ['Total', 'BTN', 'SB']), E, label('3-Bet'), ...posCells(VS3, ['SB', 'BB'])],
    [label('4-Bet-Fold'), ...posCells(ST4BF, ['Total', 'BTN', 'SB']), ...empties(4)],
  ],
};

function streetCells(ids: Record<Street, string>): LayoutCell[] {
  return [stat(ids.Flop, 'flop'), stat(ids.Turn, 'turn'), stat(ids.River, 'river')];
}

/**
 * POSTFLOP: 0 label, 1-3 Flop/Turn/River, 4-5 spacers, 6-7 second label
 * (spanning both, or label + value in the Missed C-Bet block), 8-10 values,
 * 11-12 empty. Rows 6, 10 and 14 are 8px spacer rows.
 */
const POSTFLOP_TABLE: LayoutTable = {
  id: 'postflop',
  columns: 13,
  rows: [
    [section('POSTFLOP'), label('Flop', 'center'), label('Turn', 'center'), label('River', 'center'), ...empties(9)],
    [
      heading('Continuation Bet'), ...streetCells(CB), E, E,
      heading('vs. ContinuationBet Flop', 2), label('Fold', 'center'), label('Call', 'center'), label('Raise', 'center'), E, E,
    ],
    [
      label('Fold to Continuation Bet'), ...streetCells(FCB), E, E,
      label('Raised Pot', 'left', 2), stat(VSCB_RAISED.Fold, 'flop'), stat(VSCB_RAISED.Call, 'flop'), stat(VSCB_RAISED.Raise, 'flop'), E, E,
    ],
    [
      label('Aggression'), ...streetCells(AF), E, E,
      label('3-Bet Pot', 'left', 2), stat(VSCB_3BET.Fold, 'flop'), stat(VSCB_3BET.Call, 'flop'), stat(VSCB_3BET.Raise, 'flop'), E, E,
    ],
    [label('Aggression Frequency'), ...streetCells(AFQ), ...empties(9)],
    [label('Donk Bet'), ...streetCells(DONK), ...empties(9)],
    empties(13),
    [
      heading('Missed Continuation Bet'), stat(MISSED.total, 'flop'), E, E, E, E,
      heading('vs. Missed Continuation Bet'), stat(VS_MISSED.total, 'flop'), ...empties(5),
    ],
    [
      label('In Position'), stat(MISSED.ip, 'flop'), label('→ Fold', 'center'), stat(MISSED.ipFold, 'turn'), E, E,
      label('Bet In Position'), stat(VS_MISSED.betIp, 'flop'), label('Check | Fold', 'center', 2), stat(VS_MISSED.checkFoldIp, 'turn'), E, E,
    ],
    [
      label('Out of Position'), stat(MISSED.oop, 'flop'), label('→ Fold', 'center'), stat(MISSED.oopFold, 'flop'), E, E,
      label('Bet Out of Position Turn'), stat(VS_MISSED.betOop, 'turn'), label('Check-Fold', 'center', 2), stat(VS_MISSED.checkFoldOop, 'turn'), E, E,
    ],
    empties(13),
    [label('Went to Showdown'), stat(SHOWDOWN.wtsd, 'value'), ...empties(11)],
    [label('Won at Showdown'), stat(SHOWDOWN.wsd, 'value'), ...empties(11)],
    [label('Won When Saw Flop'), stat(SHOWDOWN.wwsf, 'value'), ...empties(11)],
    empties(13),
  ],
};

/** Tables in page order (the page is one column of tables, 8px apart). */
export const GENERAL_LAYOUT: readonly LayoutTable[] = [SUMMARY_TABLE, PREFLOP_TABLE, STEAL_TABLE, POSTFLOP_TABLE];

/** Number of grid columns a row occupies (spans included). Used by tests. */
export function rowWidth(row: LayoutCell[]): number {
  return row.reduce((n, c) => n + ('span' in c && c.span ? c.span : 1), 0);
}

/** Cell ids that the layout actually places (each exactly once). */
export function layoutStatIds(layout: readonly LayoutTable[] = GENERAL_LAYOUT): string[] {
  const ids: string[] = [];
  for (const t of layout) for (const r of t.rows) for (const c of r) if (c.type === 'stat') ids.push(c.id);
  return ids;
}
