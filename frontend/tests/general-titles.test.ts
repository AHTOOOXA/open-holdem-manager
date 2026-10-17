/**
 * Unit tests for src/lib/general-titles.ts (popup titles, tooltips, tab-memory action type).
 *
 * Run: cd frontend && npx tsx --test tests/general-titles.test.ts
 */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import { GENERAL_CELLS } from '../src/lib/h2n-layout';
import { cellTooltip, statAction, statTitle } from '../src/lib/general-titles';
import { popupTitle } from '../src/lib/general-notation';

const cell = (id: string) => {
  const meta = GENERAL_CELLS[id];
  assert.ok(meta, `missing cell ${id}`);
  return meta;
};

test('titles spell out the position and the preflop line', () => {
  assert.equal(statTitle(cell('preflop.open_raise.EP')), 'Open Raise: Early Position');
  assert.equal(statTitle(cell('preflop.open_raise.Total')), 'Open Raise');
  assert.equal(statTitle(cell('preflop.three_bet.CO')), '3-Bet: Cutoff, In Position');
  assert.equal(statTitle(cell('preflop.three_bet_ip.CO')), statTitle(cell('preflop.three_bet.CO')));
  assert.equal(statTitle(cell('preflop.three_bet_oop.SB')), statTitle(cell('preflop.three_bet.SB')));
  assert.equal(statTitle(cell('steal.fold_to_3bet.BTN')), statTitle(cell('preflop.fold_to_3bet.BTN')));
  assert.equal(popupTitle(statTitle(cell('postflop.cbet.Flop'))), 'Raise 1st → Continuation Bet');
  assert.equal(statTitle(cell('postflop.vs_cbet_raised.Fold')), statTitle(cell('postflop.fold_to_cbet.Flop')));
});

test('every action cell has a descriptive title and a measured action', () => {
  for (const meta of Object.values(GENERAL_CELLS)) {
    if (meta.kind !== 'action') continue;
    const title = statTitle(meta);
    assert.ok(title.length > 0, meta.id);
    // A bare column suffix ("...: EP") means the fallback name leaked through.
    assert.doesNotMatch(title, /: (EP|MP|CO|BTN|SB|BB)$/, meta.id);
    assert.ok(statAction(meta), `no action type for ${meta.id}`);
  }
});

test('tooltips: built-in totals show their name, expressions their formula, actions nothing', () => {
  assert.equal(cellTooltip(cell('summary.hands.Total')), 'Hands');
  assert.equal(cellTooltip(cell('summary.bb100.Total')), 'Win Rate (bb/100)');
  assert.equal(cellTooltip(cell('preflop.four_bet_range.Total')), '4-Bet Range');
  assert.equal(cellTooltip(cell('postflop.wtsd.Total')), cell('postflop.wtsd.Total').formula);
  assert.equal(cellTooltip(cell('preflop.open_raise.EP')), undefined);
});

test('tab memory groups by action type', () => {
  assert.equal(statAction(cell('postflop.cbet.Flop')), 'bet');
  assert.equal(statAction(cell('postflop.fold_to_cbet.Turn')), 'fold');
  assert.equal(statAction(cell('postflop.vs_cbet_3bet.Call')), 'call');
  assert.equal(statAction(cell('postflop.missed_cbet_ip.Flop')), 'check');
  assert.equal(statAction(cell('preflop.three_bet.BB')), 'raise');
});
