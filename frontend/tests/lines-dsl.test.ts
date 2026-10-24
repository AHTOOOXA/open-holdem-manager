/** Run: cd frontend && npx tsx --test tests/lines-dsl.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  actionToDsl, cleanRows, describeLine, describeRows, fromDsl, normalisePositions, rowAllowed, rowsToDsl,
  streetHasRows, streetRowsDsl, toDsl, validateLine, ROW_ORDER,
} from '../src/lib/lines/dsl.ts';
import {
  actionsLineStep, customLineStep, isActionRows, isActionsLineStep, isCustomLineStep, isLine, lineOfStep, sanitizeLineStep,
} from '../src/lib/lines/step.ts';
import type { ActionRows, Line, LineAction, StreetRow } from '../src/lib/lines/types.ts';
import { normaliseOwnSteps, splitOwnSteps, stepKindTab, stripUiFields } from '../src/lib/reports/steps.ts';
import { filterTabFor, isStep, parseStoredChain, serializeChain, freshChain, setOwnSteps } from '../src/lib/reports/pages.ts';
import type { Step } from '../src/lib/reports/types.ts';

let n = 0;
const act = (p: Omit<LineAction, 'id'>): LineAction => ({ id: `t${++n}`, ...p });
const H = (street: LineAction['street'], a: LineAction['a'], extra: Partial<LineAction> = {}) => act({ street, who: 'hero', a, ...extra });
const V = (street: LineAction['street'], a: LineAction['a'], extra: Partial<LineAction> = {}) => act({ street, who: 'villain', a, ...extra });

/** The M8 gate line: hero 3-bets from BTN, villain calls, hero bets flop, villain raises. */
const GATE: Line = {
  actions: [
    H('preflop', 'raise', { raise: '3bet', pos: ['BTN'] }),
    V('preflop', 'call'),
    H('flop', 'bet'),
    V('flop', 'raise'),
  ],
};

// ── toDsl ───────────────────────────────────────────────────────────────────────────────────

test('gate line', () => {
  assert.equal(toDsl(GATE), 'pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R');
  assert.equal(describeLine(GATE), '3-Bet BTN → Villain calls → Flop: C-Bet → Villain raises');
  const check = validateLine(GATE);
  assert.deepEqual(check.errors, []);
  assert.equal(toDsl(check.line), 'pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R');
});

test('sides: hero H, villain V1 by default, V when not the same villain', () => {
  assert.equal(actionToDsl(H('flop', 'check')), 'H:X');
  assert.equal(actionToDsl(V('flop', 'bet')), 'V1:B');
  assert.equal(actionToDsl(V('flop', 'bet', { same: true })), 'V1:B');
  assert.equal(actionToDsl(V('flop', 'bet', { same: false })), 'V:B');
});

test('types F X C B R', () => {
  const types: [LineAction['a'], string][] = [['fold', 'F'], ['check', 'X'], ['call', 'C'], ['bet', 'B'], ['raise', 'R']];
  for (const [a, l] of types) assert.equal(actionToDsl(H('turn', a)), `H:${l}`);
});

test('raise kinds: open -> fr, 3bet -> 3b (preflop only), any -> none; kinds only on raises', () => {
  assert.equal(actionToDsl(H('preflop', 'raise', { raise: 'open' })), 'H:R[fr]');
  assert.equal(actionToDsl(H('preflop', 'raise', { raise: '3bet' })), 'H:R[3b]');
  assert.equal(actionToDsl(H('preflop', 'raise', { raise: 'any' })), 'H:R');
  assert.equal(actionToDsl(H('flop', 'raise', { raise: 'open' })), 'H:R[fr]');
  assert.equal(actionToDsl(H('flop', 'raise', { raise: '3bet' })), 'H:R');
  assert.equal(actionToDsl(H('preflop', 'call', { raise: 'open' })), 'H:C');
  assert.equal(actionToDsl(V('preflop', 'raise', { raise: 'open', pos: ['CO', 'BTN'] })), 'V1:R[fr,pos=CO+BTN]');
});

test('last and positions: table order, deduplicated, all six = any', () => {
  assert.equal(actionToDsl(H('flop', 'bet', { last: true })), 'H:B[last]');
  assert.equal(actionToDsl(H('preflop', 'raise', { raise: 'open', last: true, pos: ['BB', 'SB'] })), 'H:R[fr,last,pos=SB+BB]');
  assert.equal(actionToDsl(H('flop', 'bet', { pos: ['BTN', 'BTN'] })), 'H:B[pos=BTN]');
  assert.equal(actionToDsl(H('flop', 'bet', { pos: ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] })), 'H:B');
  assert.equal(actionToDsl(H('flop', 'bet', { pos: [] })), 'H:B');
  assert.deepEqual(normalisePositions(['BB', 'EP', 'CO']), ['EP', 'CO', 'BB']);
  assert.deepEqual(normalisePositions(undefined), []);
});

test('streets in order whatever the action order; empty streets dropped; empty line is ""', () => {
  const line: Line = { actions: [H('river', 'bet'), H('preflop', 'call'), V('turn', 'check'), H('preflop', 'fold')] };
  assert.equal(toDsl(line), 'pre: H:C > H:F; turn: V1:X; river: H:B');
  assert.equal(toDsl({ actions: [] }), '');
  assert.equal(toDsl({ actions: [H('turn', 'bet')] }), 'turn: H:B');
});

test('three-street line with mixed villains', () => {
  const line: Line = {
    actions: [
      V('preflop', 'raise', { raise: 'open', pos: ['CO'] }),
      H('preflop', 'call', { last: true, pos: ['BB'] }),
      H('flop', 'check'),
      V('flop', 'bet'),
      H('flop', 'call'),
      H('turn', 'check'),
      V('turn', 'check', { same: false }),
      H('river', 'bet', { last: true }),
    ],
  };
  assert.equal(
    toDsl(line),
    'pre: V1:R[fr,pos=CO] > H:C[last,pos=BB]; flop: H:X > V1:B > H:C; turn: H:X > V:X; river: H:B[last]',
  );
  assert.equal(
    describeLine(line),
    'Villain CO open-raises → Call BB (last) → Flop: Check → Villain bets → Call → Turn: Check → Any villain checks → River: Bet (last)',
  );
  assert.deepEqual(validateLine(line).errors, []);
});

// ── describeLine ────────────────────────────────────────────────────────────────────────────

test('describeLine: raise kinds, C-Bet only for the preflop raiser, empty line', () => {
  assert.equal(describeLine({ actions: [] }), '');
  assert.equal(describeLine({ actions: [H('preflop', 'raise', { raise: 'open' })] }), 'Open Raise');
  assert.equal(describeLine({ actions: [H('preflop', 'raise')] }), 'Raise');
  assert.equal(describeLine({ actions: [H('flop', 'raise', { raise: 'open' })] }), 'Flop: First Raise');
  assert.equal(describeLine({ actions: [V('preflop', 'raise', { raise: '3bet' })] }), 'Villain 3-bets');
  assert.equal(describeLine({ actions: [V('flop', 'raise', { raise: 'open' })] }), 'Flop: Villain raises first');
  // villain raised last preflop: hero's flop bet is a donk / plain bet
  assert.equal(
    describeLine({ actions: [H('preflop', 'raise'), V('preflop', 'raise'), H('preflop', 'call'), H('flop', 'bet')] }),
    'Raise → Villain raises → Call → Flop: Bet',
  );
  // villain bet first on the flop
  assert.equal(
    describeLine({ actions: [H('preflop', 'raise'), V('preflop', 'call'), V('flop', 'bet'), H('flop', 'raise'), V('flop', 'call'), H('turn', 'bet')] }),
    'Raise → Villain calls → Flop: Villain bets → Raise → Villain calls → Turn: Bet',
  );
  assert.equal(describeLine({ actions: [H('flop', 'bet', { pos: ['SB', 'BB'] })] }), 'Flop: Bet SB/BB');
});

// ── validateLine ────────────────────────────────────────────────────────────────────────────

test('validateLine normalises: street order, raise kind only on raises, 3-bet only preflop, hero has no `same`', () => {
  const line: Line = {
    actions: [
      H('flop', 'raise', { raise: '3bet' }),
      H('preflop', 'call', { raise: 'open', same: false, last: false }),
      V('preflop', 'raise', { pos: ['BB', 'BTN'] }),
    ],
  };
  const { line: norm } = validateLine(line);
  assert.deepEqual(norm.actions.map((a) => [a.street, a.who, a.a]), [['preflop', 'hero', 'call'], ['preflop', 'villain', 'raise'], ['flop', 'hero', 'raise']]);
  assert.equal(norm.actions[0].raise, undefined);
  assert.equal(norm.actions[0].same, undefined);
  assert.equal(norm.actions[0].last, undefined);
  assert.deepEqual(norm.actions[1].pos, ['BTN', 'BB']);
  assert.equal(norm.actions[1].same, true);
  assert.equal(norm.actions[2].raise, undefined);
  // ids are kept (the builder keeps its selection)
  assert.deepEqual(norm.actions.map((a) => a.id), [line.actions[1].id, line.actions[2].id, line.actions[0].id]);
});

test('validateLine: preflop check is the big blind', () => {
  const { line, errors } = validateLine({ actions: [V('preflop', 'call'), H('preflop', 'check', { pos: ['SB', 'BB'] })] });
  assert.deepEqual(errors, []);
  assert.deepEqual(line.actions[1].pos, ['BB']);
  assert.equal(toDsl(line), 'pre: V1:C > H:X[pos=BB]');
  assert.deepEqual(validateLine({ actions: [H('preflop', 'check')] }).line.actions[0].pos, ['BB']);
});

test('validateLine errors', () => {
  const errs = (actions: LineAction[]) => validateLine({ actions }).errors;
  assert.deepEqual(errs([]), ['Add at least one action.']);
  assert.deepEqual(errs([H('preflop', 'bet')]), ['Preflop has no bets: use a raise.']);
  assert.deepEqual(errs([V('preflop', 'raise'), H('preflop', 'check')]), ['Preflop: nobody can check after a raise.']);
  assert.deepEqual(errs([H('flop', 'bet'), V('flop', 'check')]), ['Flop: nobody can check after a bet.']);
  assert.deepEqual(errs([V('turn', 'bet'), H('turn', 'bet')]), ['Turn: a bet after a bet is a raise.']);
  assert.deepEqual(errs([V('preflop', 'raise'), H('preflop', 'raise', { raise: 'open' })]), ['Preflop: Open Raise has to be the first raise.']);
  assert.deepEqual(errs([V('flop', 'bet'), V('flop', 'raise', { same: false }), H('flop', 'raise', { raise: 'open' })]), ['Flop: First Raise has to be the first raise.']);
  assert.deepEqual(
    errs([V('preflop', 'raise'), H('preflop', 'raise'), V('preflop', 'raise', { same: false }), H('preflop', 'raise', { raise: '3bet' })]),
    ['Preflop: a 3-bet comes right after the first raise.'],
  );
  assert.deepEqual(errs([H('flop', 'check'), H('flop', 'bet')]), ["Flop: Hero acts twice in a row; add the other player's action between."]);
  assert.deepEqual(errs([V('flop', 'bet'), V('flop', 'raise')]), ["Flop: The villain acts twice in a row; add the other player's action between."]);
  // two different villains in a row are fine
  assert.deepEqual(errs([V('preflop', 'raise'), V('preflop', 'call', { same: false }), H('preflop', 'raise')]), []);
  assert.deepEqual(
    errs([H('river', 'bet', { last: true }), V('river', 'raise'), H('river', 'call')]),
    ['River: Hero acts again after an action marked last.'],
  );
  // last on another street does not matter
  assert.deepEqual(errs([H('preflop', 'call', { last: true }), H('flop', 'bet')]), []);
});

// ── rowsToDsl ───────────────────────────────────────────────────────────────────────────────

const rows = (streets: ActionRows['streets'], last: ActionRows['last'] = {}, faced?: ActionRows['faced']): ActionRows =>
  faced ? { streets, last, faced } : { streets, last };

test('each row is hero\'s whole action on the street', () => {
  const expect: Record<StreetRow, string> = {
    raise: 'H:R', raise_fold: 'H:R > V:R > H:F', raise_call: 'H:R > V:R > H:C', raise_raise: 'H:R > V:R > H:R',
    fold: 'H:F',
    call: 'H:C', call_fold: 'H:C > V:R > H:F', call_call: 'H:C > V:R > H:C', call_raise: 'H:C > V:R > H:R',
    bet: 'H:B', bet_fold: 'H:B > V:R > H:F', bet_call: 'H:B > V:R > H:C', bet_raise: 'H:B > V:R > H:R',
    check: 'H:X', check_fold: 'H:X > V:B > H:F', check_call: 'H:X > V:B > H:C', check_raise: 'H:X > V:B > H:R',
  };
  for (const r of ROW_ORDER) assert.equal(rowsToDsl(rows({ flop: [r] })), `flop: ${expect[r]}`, r);
});

test('last goes on the row\'s last hero action', () => {
  assert.equal(rowsToDsl(rows({ turn: ['bet_call'] }, { turn: true })), 'turn: H:B > V:R > H:C[last]');
  assert.equal(rowsToDsl(rows({ turn: ['check'] }, { turn: true })), 'turn: H:X[last]');
  assert.equal(rowsToDsl(rows({ preflop: ['raise'] }, { preflop: true })), 'pre: H:R[last]');
  // last on a street without rows does nothing
  assert.equal(rowsToDsl(rows({ flop: ['bet'] }, { turn: true })), 'flop: H:B');
});

test('rows of a street OR\'d in canonical order, streets AND\'d in order', () => {
  assert.equal(
    rowsToDsl(rows({ river: ['check_fold'], flop: ['check_raise', 'bet_call'], preflop: ['call', 'raise'] })),
    'pre: H:R | H:C; flop: H:B > V:R > H:C | H:X > V:B > H:R; river: H:X > V:B > H:F',
  );
  assert.equal(rowsToDsl(rows({ flop: ['bet', 'bet'] })), 'flop: H:B');
  assert.equal(rowsToDsl(rows({})), '');
  assert.equal(rowsToDsl(rows({ flop: [] })), '');
});

test('preflop has no bet rows and no check_* rows; the BB check stays', () => {
  assert.equal(rowAllowed('preflop', 'bet'), false);
  assert.equal(rowAllowed('preflop', 'bet_call'), false);
  assert.equal(rowAllowed('preflop', 'check_raise'), false);
  assert.equal(rowAllowed('preflop', 'check'), true);
  assert.equal(rowAllowed('flop', 'check_raise'), true);
  assert.equal(rowsToDsl(rows({ preflop: ['bet', 'check_fold', 'check', 'fold'] })), 'pre: H:F | H:X');
});

test('the Hand2Note example: Preflop Raise + Flop Bet Call + Turn Check Fold', () => {
  const r = rows({ preflop: ['raise'], flop: ['bet_call'], turn: ['check_fold'] });
  assert.equal(rowsToDsl(r), 'pre: H:R; flop: H:B > V:R > H:C; turn: H:X > V:B > H:F');
  assert.equal(describeRows(r), 'Preflop: Raise · Flop: Bet Call · Turn: Check Fold');
});

test('describeRows lists rows per street, marks last, faced first', () => {
  assert.equal(describeRows(rows({ flop: ['bet_call'], turn: ['check_fold'] })), 'Flop: Bet Call · Turn: Check Fold');
  assert.equal(describeRows(rows({ preflop: ['call_fold', 'raise'] })), 'Preflop: Raise, Call Fold');
  assert.equal(describeRows(rows({ flop: ['bet'] }, { flop: true })), 'Flop: Bet (last)');
  assert.equal(describeRows(rows({ preflop: ['raise'] }, {}, ['one_limp', 'open_raise'])), 'Faced One Limp, Open Raise · Preflop: Raise');
  assert.equal(describeRows(rows({})), '');
});

// ── Faced preflop ───────────────────────────────────────────────────────────────────────────

test('faced preflop: villain actions in front of hero\'s first action', () => {
  const pre = (faced: ActionRows['faced'], streets: ActionRows['streets'] = {}, last = false) =>
    streetRowsDsl(rows(streets, { preflop: last }, faced), 'preflop');
  assert.deepEqual(pre(['open_raise'], { preflop: ['call', 'raise_fold'] }), ['V:R[open] > H:R > V:R > H:F', 'V:R[open] > H:C']);
  assert.deepEqual(pre(['one_limp'], { preflop: ['raise'] }), ['V:C[open] > H:R']);
  assert.deepEqual(pre(['two_plus_limps'], { preflop: ['raise'] }), ['V:C[limp] > V:C > H:R']);
  assert.deepEqual(pre(['limp_raise'], { preflop: ['fold'] }), ['V:C[open] > V:R > H:F']);
  assert.deepEqual(pre(['open_3bet'], { preflop: ['call'] }), ['V:R[open] > V:R > H:C']);
  assert.deepEqual(pre(['raise_call'], { preflop: ['raise'] }), ['V:R[open] > V:C > H:R']);
  assert.deepEqual(pre(['raise_calls'], { preflop: ['raise'] }), ['V:R[open] > V:C > V:C > H:R', 'V:R[open] > V:C > V:C > V:C > H:R']);
  // last goes on hero's last action, after the prefix
  assert.deepEqual(pre(['open_raise'], { preflop: ['raise_call'] }, true), ['V:R[open] > H:R > V:R > H:C[last]']);
});

test('faced Unopened: `open` on hero\'s first raise / call; folds and checks cannot be expressed', () => {
  const pre = (streets: ActionRows['streets']) => streetRowsDsl(rows(streets, {}, ['unopened']), 'preflop');
  assert.deepEqual(pre({ preflop: ['raise', 'raise_call', 'call', 'fold'] }), ['H:R[open]', 'H:R[open] > V:R > H:C', 'H:C[open]']);
  assert.deepEqual(pre({ preflop: ['fold'] }), []);
  assert.deepEqual(pre({}), ['H:C[open]', 'H:R[open]']);
});

test('faced alone: any first action (checks only behind limps); several faced OR\'d', () => {
  assert.equal(rowsToDsl(rows({}, {}, ['open_raise'])), 'pre: V:R[open] > H:F | V:R[open] > H:C | V:R[open] > H:R');
  assert.equal(rowsToDsl(rows({}, {}, ['one_limp'])), 'pre: V:C[open] > H:F | V:C[open] > H:X | V:C[open] > H:C | V:C[open] > H:R');
  assert.equal(
    rowsToDsl(rows({ preflop: ['raise'], flop: ['bet'] }, {}, ['open_raise', 'unopened'])),
    'pre: H:R[open] | V:R[open] > H:R; flop: H:B',
  );
  assert.equal(rowsToDsl(rows({ preflop: ['fold'] }, {}, ['unopened'])), '');
});

test('cleanRows / streetHasRows', () => {
  const r: ActionRows = { streets: { flop: ['bet_call', 'bet'], turn: [], preflop: ['bet'] }, last: { flop: false, turn: true }, faced: ['open_raise', 'unopened'] };
  assert.deepEqual(cleanRows(r), { streets: { flop: ['bet', 'bet_call'] }, last: { turn: true }, faced: ['unopened', 'open_raise'] });
  assert.equal(streetHasRows(r, 'flop'), true);
  assert.equal(streetHasRows(r, 'turn'), false);
  assert.equal(streetHasRows(r, 'preflop'), true); // faced
  assert.equal(streetHasRows({ streets: { preflop: ['bet'] }, last: {} }, 'preflop'), false);
});

// ── fromDsl ─────────────────────────────────────────────────────────────────────────────────

const strip = (l: Line | null) => l && l.actions.map((a) => {
  const rest: Partial<LineAction> = { ...a };
  delete rest.id;
  return rest;
});

test('fromDsl inverts toDsl', () => {
  const back = fromDsl(toDsl(GATE));
  assert.ok(back);
  assert.equal(toDsl(back), toDsl(GATE));
  assert.deepEqual(strip(back), [
    { street: 'preflop', who: 'hero', a: 'raise', raise: '3bet', pos: ['BTN'] },
    { street: 'preflop', who: 'villain', a: 'call', same: true },
    { street: 'flop', who: 'hero', a: 'bet' },
    { street: 'flop', who: 'villain', a: 'raise', same: true },
  ]);
  const l2 = fromDsl('pre: V:R[fr,pos=SB+BB] > H:C[last]; river: H:X');
  assert.deepEqual(strip(l2), [
    { street: 'preflop', who: 'villain', a: 'raise', same: false, raise: 'open', pos: ['SB', 'BB'] },
    { street: 'preflop', who: 'hero', a: 'call', last: true },
    { street: 'river', who: 'hero', a: 'check' },
  ]);
});

test('fromDsl gives null for what the builder cannot show', () => {
  assert.equal(fromDsl(''), null);
  assert.equal(fromDsl('pre: H:R | H:C'), null);
  assert.equal(fromDsl('pre: H:C[limp]'), null);
  assert.equal(fromDsl('pre: H:C[amt=2-]'), null);
  assert.equal(fromDsl('flop: H:B; pre: H:R'), null);
  assert.equal(fromDsl('pre: H:Q'), null);
  assert.equal(fromDsl('pre: H:R[pos=XX]'), null);
  assert.equal(fromDsl('nope'), null);
});

// ── Line steps ──────────────────────────────────────────────────────────────────────────────

test('customLineStep: notation, label = name or description, model kept', () => {
  const s = customLineStep(GATE);
  assert.ok(s);
  assert.equal(s.k, 'line');
  assert.equal(s.dsl, 'pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R');
  assert.equal(s.label, '3-Bet BTN → Villain calls → Flop: C-Bet → Villain raises');
  assert.equal(s.name, undefined);
  assert.equal(s.line?.actions.length, 4);
  const named = customLineStep(GATE, '  3BP raised  ');
  assert.equal(named?.label, '3BP raised');
  assert.equal(named?.name, '3BP raised');
  assert.equal(customLineStep({ actions: [] }), null);
  assert.equal(customLineStep({ actions: [H('preflop', 'bet')] }), null);
  assert.equal(isCustomLineStep(s), true);
  assert.equal(isActionsLineStep(s), false);
  assert.equal(lineOfStep(s), s.line);
  // a line step without a model (e.g. typed by hand) is parsed back when possible
  assert.equal(toDsl(lineOfStep({ k: 'line', dsl: 'flop: H:B' })!), 'flop: H:B');
  assert.equal(lineOfStep({ k: 'line', dsl: 'flop: H:B | H:X' }), null);
});

test('actionsLineStep: one step from the rows, null when empty', () => {
  const s = actionsLineStep(rows({ flop: ['bet_call'], turn: ['check_fold'] }));
  assert.ok(s);
  assert.equal(s.dsl, 'flop: H:B > V:R > H:C; turn: H:X > V:B > H:F');
  assert.equal(s.label, 'Flop: Bet Call · Turn: Check Fold');
  assert.deepEqual(s.rows, { streets: { flop: ['bet_call'], turn: ['check_fold'] }, last: {} });
  assert.equal(isActionsLineStep(s), true);
  assert.equal(isCustomLineStep(s), false);
  assert.equal(actionsLineStep(rows({})), null);
  assert.equal(actionsLineStep(rows({ preflop: ['fold'] }, {}, ['unopened'])), null);
});

test('stripUiFields drops rows / line / name of line steps, keeps dsl and label', () => {
  const a = actionsLineStep(rows({ flop: ['bet'] }))!;
  const c = customLineStep(GATE, 'Mine')!;
  assert.deepEqual(stripUiFields([a, c]), [
    { k: 'line', dsl: 'flop: H:B', label: 'Flop: Bet' },
    { k: 'line', dsl: 'pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R', label: 'Mine' },
  ]);
  assert.deepEqual(stripUiFields([c], false), [{ k: 'line', dsl: 'pre: H:R[3b,pos=BTN] > V1:C; flop: H:B > V1:R' }]);
  // the page state is not touched
  assert.ok(a.rows && c.line && c.name);
});

test('own steps: Actions-tab and Custom Filter line steps, spot steps first', () => {
  const a = actionsLineStep(rows({ flop: ['bet'] }))!;
  const c = customLineStep(GATE)!;
  const pos: Step = { k: 'pos', v: ['BTN'] };
  const row: Step = { k: 'row', key: 'P01', label: 'Raise 1st In' };
  const parts = splitOwnSteps([pos, c, a, row]);
  assert.equal(parts.actions, a);
  assert.equal(parts.custom, c);
  assert.deepEqual(normaliseOwnSteps([pos, c, a, row]).map((s) => s.k), ['row', 'line', 'line', 'pos']);
  assert.equal((normaliseOwnSteps([pos, c, a, row])[1] as typeof a).rows !== undefined, true);
  // a second step of a kind goes to `other`
  const extra = customLineStep({ actions: [H('river', 'bet')] })!;
  assert.deepEqual(splitOwnSteps([c, extra]).other, [extra]);
  assert.equal(stepKindTab(a), 'actions');
  assert.equal(stepKindTab(c), null);
  assert.equal(filterTabFor(a), 'actions');
});

test('persisted chains keep line steps and their editor models', () => {
  const a = actionsLineStep(rows({ flop: ['bet_call'] }, { flop: true }, ['open_raise']))!;
  const c = customLineStep(GATE, 'Gate')!;
  const chain = setOwnSteps(freshChain(), 0, [a, c]);
  const back = parseStoredChain(serializeChain(chain, null));
  assert.ok(back);
  const own = back.chain.pages[0].state.own;
  assert.deepEqual(own, [a, c]);
  assert.equal(isStep(own[0]) && isStep(own[1]), true);
});

test('malformed editor models are dropped, the notation stays', () => {
  assert.equal(isActionRows({ streets: { flop: ['bet'] }, last: {} }), true);
  assert.equal(isActionRows({ streets: { flop: ['nope'] }, last: {} }), false);
  assert.equal(isActionRows({ streets: { flop: ['bet'] }, last: { flop: 1 } }), false);
  assert.equal(isActionRows({ streets: {}, last: {}, faced: ['posted_blind'] }), false);
  assert.equal(isLine(GATE), true);
  assert.equal(isLine({ actions: [{ id: 'x', street: 'flop', who: 'hero', a: 'jam' }] }), false);
  const bad = { k: 'line', dsl: 'flop: H:B', label: 'x', rows: { streets: 3 }, line: { actions: 'no' }, name: 7 } as unknown as Step;
  assert.deepEqual(sanitizeLineStep(bad), { k: 'line', dsl: 'flop: H:B', label: 'x' });
  const raw = JSON.stringify({ v: 1, player: null, pages: [{ title: 'Reports', inherited: [], own: [bad], lower: [], upperTab: 'stats', lowerTabs: ['hands'], lowerTab: 'hands', selectedRow: null, openedFrom: 'hands' }] });
  assert.deepEqual(parseStoredChain(raw)?.chain.pages[0].state.own, [{ k: 'line', dsl: 'flop: H:B', label: 'x' }]);
});

test('actionChipLabel', async () => {
  const { actionChipLabel } = await import('../src/lib/lines/dsl.ts');
  assert.equal(actionChipLabel(H('preflop', 'raise', { raise: '3bet', pos: ['BTN'] })), 'Hero BTN 3-bets');
  assert.equal(actionChipLabel(V('preflop', 'call')), 'Villain calls');
  assert.equal(actionChipLabel(V('flop', 'check', { same: false, last: true })), 'Any villain checks (last)');
  assert.equal(actionChipLabel(H('preflop', 'raise', { raise: 'open' })), 'Hero open-raises');
  assert.equal(actionChipLabel(H('turn', 'raise', { raise: 'open' })), 'Hero raises first');
});

test('lineStepDescription: the line, not its name', async () => {
  const { lineStepDescription } = await import('../src/lib/lines/step.ts');
  assert.equal(lineStepDescription(customLineStep(GATE, 'Gate')!), '3-Bet BTN → Villain calls → Flop: C-Bet → Villain raises');
  assert.equal(lineStepDescription(actionsLineStep(rows({ flop: ['bet'] }))!), 'Flop: Bet');
  assert.equal(lineStepDescription({ k: 'line', dsl: 'flop: H:B | H:X' }), 'flop: H:B | H:X');
});
