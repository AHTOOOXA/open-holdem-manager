/**
 * Line builder model -> H2N matcher row notation (backend/app/h2n/matcher.py docstring), plus the
 * readable labels and the checks the builder shows. Pure; no React.
 *
 *   toDsl(line)       "pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R"
 *   rowsToDsl(rows)   filter-dialog Actions tab rows, e.g. flop Bet Call = "flop: H:B > V:R > H:C"
 *   describeLine      "3-Bet BTN → Villain calls → Flop: Bet → Villain raises"
 *   validateLine      normalised line + the reasons it can never match
 *   fromDsl           the inverse of toDsl for one-row-per-street notation (chips without a model)
 */
import type { Pos, Street } from '../reports/types';
import type { ActionRows, FacedPreflop, Line, LineAction, LineActionType, LineActor, RaiseKind, StreetRow } from './types';

export const LINE_STREETS: readonly Street[] = ['preflop', 'flop', 'turn', 'river'];
export const LINE_POSITIONS: readonly Pos[] = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
/** Longest notation the backend takes (`LINE_MAX_LEN` in backend/app/reports/chain.py). */
export const LINE_MAX_LENGTH = 2000;
export const STREET_TITLE: Record<Street, string> = { preflop: 'Preflop', flop: 'Flop', turn: 'Turn', river: 'River' };

const STREET_KEY: Record<Street, string> = { preflop: 'pre', flop: 'flop', turn: 'turn', river: 'river' };
const KEY_STREET: Record<string, Street> = { pre: 'preflop', preflop: 'preflop', flop: 'flop', turn: 'turn', river: 'river' };
type Letter = 'F' | 'X' | 'C' | 'B' | 'R';
const LETTER: Record<LineActionType, Letter> = { fold: 'F', check: 'X', call: 'C', bet: 'B', raise: 'R' };
const TYPE_OF: Record<Letter, LineActionType> = { F: 'fold', X: 'check', C: 'call', B: 'bet', R: 'raise' };

const streetIndex = (s: Street) => LINE_STREETS.indexOf(s);

/** Positions in table order without duplicates; all six (= any) or none give []. */
export function normalisePositions(pos: readonly Pos[] | undefined): Pos[] {
  if (!pos) return [];
  const out = LINE_POSITIONS.filter((p) => pos.includes(p));
  return out.length === LINE_POSITIONS.length ? [] : out;
}

// ── Line -> notation ─────────────────────────────────────────────────────────────────────────

export function actionToDsl(a: LineAction): string {
  const side = a.who === 'hero' ? 'H' : a.same !== false ? 'V1' : 'V';
  const flags: string[] = [];
  if (a.a === 'raise') {
    if (a.raise === 'open') flags.push('fr');
    else if (a.raise === '3bet' && a.street === 'preflop') flags.push('3b');
  }
  if (a.last) flags.push('last');
  const pos = normalisePositions(a.pos);
  if (pos.length) flags.push(`pos=${pos.join('+')}`);
  return `${side}:${LETTER[a.a]}${flags.length ? `[${flags.join(',')}]` : ''}`;
}

/** Streets in order pre / flop / turn / river; a street without actions is left out. */
export function toDsl(line: Line): string {
  const parts: string[] = [];
  for (const street of LINE_STREETS) {
    const acts = line.actions.filter((a) => a.street === street);
    if (acts.length) parts.push(`${STREET_KEY[street]}: ${acts.map(actionToDsl).join(' > ')}`);
  }
  return parts.join('; ');
}

// ── Actions tab rows ────────────────────────────────────────────────────────────────────────

interface Tok { hero: boolean; t: Letter; flags: string[] }

/** Hero's whole action on a street: first action, then (villain raise / bet, hero's answer). */
const ROW_DEF: Record<StreetRow, { first: Letter; then?: Letter }> = {
  raise: { first: 'R' }, raise_fold: { first: 'R', then: 'F' }, raise_call: { first: 'R', then: 'C' }, raise_raise: { first: 'R', then: 'R' },
  fold: { first: 'F' },
  call: { first: 'C' }, call_fold: { first: 'C', then: 'F' }, call_call: { first: 'C', then: 'C' }, call_raise: { first: 'C', then: 'R' },
  bet: { first: 'B' }, bet_fold: { first: 'B', then: 'F' }, bet_call: { first: 'B', then: 'C' }, bet_raise: { first: 'B', then: 'R' },
  check: { first: 'X' }, check_fold: { first: 'X', then: 'F' }, check_call: { first: 'X', then: 'C' }, check_raise: { first: 'X', then: 'R' },
};

/** Canonical row order (the Actions tab's columns, top to bottom, left to right). */
export const ROW_ORDER: readonly StreetRow[] = [
  'raise', 'raise_fold', 'raise_call', 'raise_raise', 'fold',
  'call', 'call_fold', 'call_call', 'call_raise',
  'bet', 'bet_fold', 'bet_call', 'bet_raise',
  'check', 'check_fold', 'check_call', 'check_raise',
];

export const ROW_LABEL: Record<StreetRow, string> = {
  raise: 'Raise', raise_fold: 'Raise Fold', raise_call: 'Raise Call', raise_raise: 'Raise Raise', fold: 'Fold',
  call: 'Call', call_fold: 'Call Fold', call_call: 'Call Call', call_raise: 'Call Raise',
  bet: 'Bet', bet_fold: 'Bet Fold', bet_call: 'Bet Call', bet_raise: 'Bet Raise',
  check: 'Check', check_fold: 'Check Fold', check_call: 'Check Call', check_raise: 'Check Raise',
};

/** Rows a street can have: preflop has no bets, and its only check is the big blind's (no check_*). */
export function rowAllowed(street: Street, row: StreetRow): boolean {
  if (street !== 'preflop') return true;
  return !row.startsWith('bet') && (row === 'check' || !row.startsWith('check'));
}

function rowToks(row: StreetRow): Tok[] {
  const d = ROW_DEF[row];
  // Hero's whole action on the street: his first action is `first`, his final one `last`
  const out: Tok[] = [{ hero: true, t: d.first, flags: ['first'] }];
  if (d.then) out.push({ hero: false, t: d.first === 'X' ? 'B' : 'R', flags: [] }, { hero: true, t: d.then, flags: [] });
  return withLast(out, true);
}

function tokToDsl(t: Tok): string {
  return `${t.hero ? 'H' : 'V'}:${t.t}${t.flags.length ? `[${t.flags.join(',')}]` : ''}`;
}

function withLast(toks: Tok[], last: boolean): Tok[] {
  if (!last) return toks;
  let i = toks.length - 1;
  while (i >= 0 && !toks[i].hero) i--;
  return toks.map((t, j) => (j === i && !t.flags.includes('last') ? { ...t, flags: [...t.flags, 'last'] } : t));
}

const v = (t: Letter, ...flags: string[]): Tok => ({ hero: false, t, flags });

/**
 * Faced preflop situations the matcher can express: villain actions in front of hero's first
 * preflop action (between two filter actions only folds may be skipped, so a prefix fixes the
 * whole action in front of hero). `unopened` instead puts `open` (first VPIP action of the
 * street) on hero's first action, which only a raise or a call can carry: folds and checks in an
 * unopened pot cannot be selected. Not expressible, so not offered: Posted Blind, 3-Bet, 4-Bet,
 * 5-Bet, Open Raise All-in.
 */
export const FACED_PREFLOP: readonly { id: FacedPreflop; label: string; prefixes: Tok[][]; check: boolean }[] = [
  { id: 'unopened', label: 'Unopened', prefixes: [[]], check: false },
  { id: 'one_limp', label: 'One Limp', prefixes: [[v('C', 'open')]], check: true },
  { id: 'two_plus_limps', label: '2+ Limps', prefixes: [[v('C', 'limp'), v('C')]], check: true },
  { id: 'limp_raise', label: '1 Limp and Raise', prefixes: [[v('C', 'open'), v('R')]], check: false },
  { id: 'open_raise', label: 'Open Raise', prefixes: [[v('R', 'open')]], check: false },
  { id: 'open_3bet', label: 'Open Raise and 3-Bet', prefixes: [[v('R', 'open'), v('R')]], check: false },
  { id: 'raise_call', label: '1 Raise and 1 Call', prefixes: [[v('R', 'open'), v('C')]], check: false },
  {
    id: 'raise_calls', label: '1 Raise and 2 or 3 Calls',
    prefixes: [[v('R', 'open'), v('C'), v('C')], [v('R', 'open'), v('C'), v('C'), v('C')]], check: false,
  },
];

export const FACED_LABEL = Object.fromEntries(FACED_PREFLOP.map((f) => [f.id, f.label])) as Record<FacedPreflop, string>;

function streetRows(rows: ActionRows, street: Street): StreetRow[] {
  const set = rows.streets[street] ?? [];
  return ROW_ORDER.filter((r) => set.includes(r) && rowAllowed(street, r));
}

function facedList(rows: ActionRows): FacedPreflop[] {
  const set = rows.faced ?? [];
  return FACED_PREFLOP.filter((f) => set.includes(f.id)).map((f) => f.id);
}

/** Generic "hero's first preflop action" when only Faced Preflop is set. */
const ANY_FIRST: Letter[] = ['F', 'X', 'C', 'R'];

/** Notation rows of one Faced Preflop situation with the chosen preflop rows ([] = none expressible). */
function facedRows(id: FacedPreflop, base: Tok[][]): string[] {
  const def = FACED_PREFLOP.find((f) => f.id === id)!;
  const out: string[] = [];
  for (const toks of base) {
    let row = toks;
    if (id === 'unopened') {
      if (row[0].t !== 'R' && row[0].t !== 'C') continue;
      row = [{ ...row[0], flags: [...row[0].flags, 'open'] }, ...row.slice(1)];
    } else if (row[0].t === 'X' && !def.check) {
      continue; // nobody can check after a raise
    }
    for (const prefix of def.prefixes) out.push([...prefix, ...row].map(tokToDsl).join(' > '));
  }
  return out;
}

function preflopBase(rows: ActionRows): Tok[][] {
  const chosen = streetRows(rows, 'preflop');
  return chosen.length ? chosen.map(rowToks) : ANY_FIRST.map((t): Tok[] => [{ hero: true, t, flags: ['first'] }]);
}

function preflopPart(rows: ActionRows): string[] {
  const faced = facedList(rows);
  if (!faced.length) return streetRows(rows, 'preflop').map((r) => withLast(rowToks(r), rows.last.preflop === true).map(tokToDsl).join(' > '));
  const base = preflopBase(rows);
  return [...new Set(faced.flatMap((id) => facedRows(id, base)))];
}

/** Selected Faced Preflop situations that no selected preflop row can be expressed in. */
function emptyFaced(rows: ActionRows): FacedPreflop[] {
  const base = preflopBase(rows);
  return facedList(rows).filter((id) => facedRows(id, base).length === 0);
}

/** Why the Actions tab selection cannot be turned into a filter (empty = fine). */
export function rowsIssues(rows: ActionRows): string[] {
  return emptyFaced(rows).map((id) => `Faced ${FACED_LABEL[id]} cannot be combined with the selected preflop actions: nothing is left to match.`);
}

/** The rows of one street (preflop: with Faced Preflop) as notation rows; [] = no filter there. */
export function streetRowsDsl(rows: ActionRows, street: Street): string[] {
  if (street === 'preflop') return preflopPart(rows);
  const last = rows.last[street] === true;
  return streetRows(rows, street).map((r) => withLast(rowToks(r), last).map(tokToDsl).join(' > '));
}

/** Rows of a street OR'd (" | "), streets AND'd ("; "); '' when nothing is selected. */
export function rowsToDsl(rows: ActionRows): string {
  const parts: string[] = [];
  for (const street of LINE_STREETS) {
    const r = streetRowsDsl(rows, street);
    if (r.length) parts.push(`${STREET_KEY[street]}: ${r.join(' | ')}`);
  }
  return parts.join('; ');
}

export const EMPTY_ROWS: ActionRows = { streets: {}, last: {} };

/** Canonical copy: known rows in order, empty streets and unchecked flags dropped. */
export function cleanRows(rows: ActionRows): ActionRows {
  const out: ActionRows = { streets: {}, last: {} };
  for (const street of LINE_STREETS) {
    const r = streetRows(rows, street);
    if (r.length) out.streets[street] = r;
    if (rows.last[street] === true) out.last[street] = true;
  }
  const faced = facedList(rows);
  if (faced.length) out.faced = faced;
  return out;
}

/** Street has a selection (its inner-tab dot). */
export function streetHasRows(rows: ActionRows, street: Street): boolean {
  return streetRows(rows, street).length > 0 || (street === 'preflop' && facedList(rows).length > 0);
}

/** Chip text: "Faced Open Raise · Preflop: Raise, Call Fold · Flop: Bet Call (last)". */
export function describeRows(rows: ActionRows): string {
  const parts: string[] = [];
  const empty = emptyFaced(rows);
  const faced = facedList(rows).filter((f) => !empty.includes(f));
  if (faced.length) parts.push(`Faced ${faced.map((f) => FACED_LABEL[f]).join(', ')}`);
  for (const street of LINE_STREETS) {
    const r = streetRows(rows, street);
    if (r.length) parts.push(`${STREET_TITLE[street]}: ${r.map((x) => ROW_LABEL[x]).join(', ')}${rows.last[street] ? ' (last)' : ''}`);
  }
  return parts.join(' · ');
}

// ── Labels ──────────────────────────────────────────────────────────────────────────────────

const VILLAIN_VERB: Record<LineActionType, string> = { fold: 'folds', check: 'checks', call: 'calls', bet: 'bets', raise: 'raises' };
const HERO_NOUN: Record<LineActionType, string> = { fold: 'Fold', check: 'Check', call: 'Call', bet: 'Bet', raise: 'Raise' };

export function raiseKindLabel(kind: RaiseKind | undefined, street: Street): string {
  if (kind === 'open') return 'First Raise';
  if (kind === '3bet' && street === 'preflop') return '3-Bet';
  return 'Raise';
}

/** "Hero" / "Villain" / "Any villain" (a villain action not bound to the line's villain). */
export function actorLabel(who: LineActor, same: boolean | undefined): string {
  return who === 'hero' ? 'Hero' : same === false ? 'Any villain' : 'Villain';
}

function describeAction(line: Line, i: number): string {
  const a = line.actions[i];
  const pos = normalisePositions(a.pos).join('/');
  const tail = a.last ? ' (last)' : '';
  if (a.who === 'hero') {
    const noun = a.a === 'raise' ? raiseKindLabel(a.raise, a.street) : HERO_NOUN[a.a];
    return `${noun}${pos ? ` ${pos}` : ''}${tail}`;
  }
  return `${actorLabel('villain', a.same)}${pos ? ` ${pos}` : ''} ${actionVerb(a)}${tail}`;
}

/** "raises", "raises first", "3-bets", "calls", ... */
export function actionVerb(a: Pick<LineAction, 'a' | 'raise' | 'street'>): string {
  if (a.a === 'raise' && a.raise === 'open') return 'raises first';
  if (a.a === 'raise' && a.raise === '3bet' && a.street === 'preflop') return '3-bets';
  return VILLAIN_VERB[a.a];
}

/** Builder chip text: "Hero BTN 3-bets", "Villain calls", "Any villain checks (last)". */
export function actionChipLabel(a: LineAction): string {
  const pos = normalisePositions(a.pos).join('/');
  return `${actorLabel(a.who, a.same)}${pos ? ` ${pos}` : ''} ${actionVerb(a)}${a.last ? ' (last)' : ''}`;
}

/** "3-Bet BTN → Villain calls → Flop: Bet → Villain raises"; '' for an empty line. */
export function describeLine(line: Line): string {
  const ordered = sortByStreet(line);
  const out: string[] = [];
  let street: Street | null = null;
  ordered.actions.forEach((a, i) => {
    const text = describeAction(ordered, i);
    out.push(a.street !== street && a.street !== 'preflop' ? `${STREET_TITLE[a.street]}: ${text}` : text);
    street = a.street;
  });
  return out.join(' → ');
}

// ── Checks ──────────────────────────────────────────────────────────────────────────────────

function sortByStreet(line: Line): Line {
  return { actions: [...line.actions].sort((a, b) => streetIndex(a.street) - streetIndex(b.street)) };
}

function normaliseAction(a: LineAction): LineAction {
  const out: LineAction = { id: a.id, street: a.street, who: a.who, a: a.a };
  if (a.a === 'raise' && (a.raise === 'open' || (a.raise === '3bet' && a.street === 'preflop'))) out.raise = a.raise;
  let pos = normalisePositions(a.pos);
  // Preflop only the big blind can check
  if (a.street === 'preflop' && a.a === 'check') pos = ['BB'];
  if (pos.length) out.pos = pos;
  if (a.who === 'villain') out.same = a.same !== false;
  if (a.last) out.last = true;
  return out;
}

export interface LineCheck {
  /** Normalised: street order, raise kind only where it means something, positions in table order. */
  line: Line;
  /** Why the line can never match (empty = OK). */
  errors: string[];
}

function sameActor(a: LineAction, b: LineAction): boolean {
  if (a.who !== b.who) return false;
  return a.who === 'hero' || (a.same !== false && b.same !== false);
}

const actorName = (a: LineAction) => (a.who === 'hero' ? 'Hero' : 'The villain');

export function validateLine(line: Line): LineCheck {
  const norm = { actions: sortByStreet(line).actions.map(normaliseAction) };
  const errors: string[] = [];
  if (!norm.actions.length) errors.push('Add at least one action.');
  // An actor that folded cannot act later (hero; the bound villain V1 across streets)
  let heroFolded = false;
  let villainFolded = false;
  for (const a of norm.actions) {
    const bound = a.who === 'hero' ? heroFolded : a.same !== false && villainFolded;
    if (bound) errors.push(`${actorName(a)} folded earlier and cannot act again.`);
    if (a.a === 'fold') {
      if (a.who === 'hero') heroFolded = true;
      else if (a.same !== false) villainFolded = true;
    }
  }
  for (const street of LINE_STREETS) {
    const acts = norm.actions.filter((a) => a.street === street);
    const title = STREET_TITLE[street];
    let raises = 0;
    let aggressed = false;
    acts.forEach((a, i) => {
      if (street === 'preflop' && a.a === 'bet') errors.push('Preflop has no bets: use a raise.');
      if (a.a === 'check' && aggressed) errors.push(`${title}: nobody can check after a ${street === 'preflop' ? 'raise' : 'bet'}.`);
      if (a.a === 'bet' && aggressed && street !== 'preflop') errors.push(`${title}: a bet after a bet is a raise.`);
      if (a.a === 'raise' && a.raise === 'open' && raises > 0) errors.push(`${title}: ${raiseKindLabel('open', street)} has to be the first raise.`);
      if (a.a === 'raise' && a.raise === '3bet' && raises > 1) errors.push(`${title}: a 3-bet comes right after the first raise.`);
      const prev = acts[i - 1];
      if (prev && sameActor(prev, a)) errors.push(`${title}: ${actorName(a)} acts twice in a row; add the other player's action between.`);
      const earlierLast = acts.slice(0, i).find((x) => x.last && sameActor(x, a));
      if (earlierLast) errors.push(`${title}: ${actorName(a)} acts again after an action marked last.`);
      if (a.a === 'raise') raises++;
      if (a.a === 'bet' || a.a === 'raise') aggressed = true;
    });
  }
  return { line: norm, errors: [...new Set(errors)] };
}

// ── Notation -> line ────────────────────────────────────────────────────────────────────────

let seq = 0;

/** Stable UI key for a new action. */
export function newActionId(): string {
  seq += 1;
  return `a${Date.now().toString(36)}${seq.toString(36)}${Math.floor(Math.random() * 1e6).toString(36)}`;
}

/**
 * Parse notation that `toDsl` can produce (one row per street, flags fr / 3b / last / pos=).
 * Anything else (several rows, other flags) gives null: the builder cannot show it.
 */
export function fromDsl(dsl: string): Line | null {
  const actions: LineAction[] = [];
  let lastStreet = -1;
  const chunks = dsl.split(';').map((c) => c.trim()).filter(Boolean);
  if (!chunks.length) return null;
  for (const chunk of chunks) {
    const colon = chunk.indexOf(':');
    if (colon < 0) return null;
    const street = KEY_STREET[chunk.slice(0, colon).trim()];
    if (!street || streetIndex(street) <= lastStreet) return null;
    lastStreet = streetIndex(street);
    const body = chunk.slice(colon + 1);
    if (body.includes('|')) return null;
    for (const raw of body.split('>')) {
      const m = /^\s*(H|V1|V):([FXCBR])(?:\[([^\]]*)\])?\s*$/.exec(raw);
      if (!m) return null;
      const a: LineAction = { id: newActionId(), street, who: m[1] === 'H' ? 'hero' : 'villain', a: TYPE_OF[m[2] as Letter] };
      if (a.who === 'villain') a.same = m[1] === 'V1';
      for (const word of (m[3] ?? '').split(',').map((w) => w.trim()).filter(Boolean)) {
        if (word === 'fr' && a.a === 'raise') a.raise = 'open';
        else if (word === '3b' && a.a === 'raise') a.raise = '3bet';
        else if (word === 'last') a.last = true;
        else if (word.startsWith('pos=')) {
          const ps = word.slice(4).split('+');
          if (!ps.every((p) => (LINE_POSITIONS as readonly string[]).includes(p))) return null;
          a.pos = ps as Pos[];
        } else return null;
      }
      actions.push(a);
    }
  }
  return { actions };
}
