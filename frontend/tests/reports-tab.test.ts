import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseReportTab, withReportTab } from '../src/lib/reports-tab.ts';

test('parseReportTab accepts known tabs, falls back to graph', () => {
  assert.equal(parseReportTab('range'), 'range');
  assert.equal(parseReportTab('hands'), 'hands');
  assert.equal(parseReportTab('graph'), 'graph');
  assert.equal(parseReportTab('nope'), 'graph');
  assert.equal(parseReportTab(null), 'graph');
  assert.equal(parseReportTab(''), 'graph');
});

test('withReportTab preserves other params and does not mutate input', () => {
  const p = new URLSearchParams('stat_flag=a&stat_flag=b&tab=graph&position=btn');
  const n = withReportTab(p, 'hands');
  assert.equal(n.get('tab'), 'hands');
  assert.deepEqual(n.getAll('stat_flag'), ['a', 'b']);
  assert.equal(n.get('position'), 'btn');
  assert.equal(p.get('tab'), 'graph');
});
