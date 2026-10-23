import { test } from 'node:test';
import assert from 'node:assert/strict';
import { parseLegacyReportLink, parseReportTab, withReportTab, withoutLegacyParams } from '../src/lib/reports-tab.ts';

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

test('parseLegacyReportLink reads old preview links, null without legacy params', () => {
  assert.equal(parseLegacyReportLink(new URLSearchParams('')), null);
  assert.equal(parseLegacyReportLink(new URLSearchParams('foo=1')), null);
  assert.deepEqual(parseLegacyReportLink(new URLSearchParams('tab=range')), {
    tab: 'range', statFlags: [], statKey: undefined, position: [],
  });
  assert.deepEqual(parseLegacyReportLink(new URLSearchParams('tab=hands&stat_flag=a&stat_flag=b&position=btn&stat_key=vpip')), {
    tab: 'hands', statFlags: ['a', 'b'], statKey: 'vpip', position: ['BTN'],
  });
  // hand filters without a tab land on the hands list
  assert.equal(parseLegacyReportLink(new URLSearchParams('stat_flag=a'))?.tab, 'hands');
});

test('withoutLegacyParams strips only the legacy params', () => {
  const n = withoutLegacyParams(new URLSearchParams('tab=hands&stat_flag=a&position=btn&stat_key=x&keep=1'));
  assert.equal(n.toString(), 'keep=1');
});
