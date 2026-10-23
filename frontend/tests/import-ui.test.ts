import assert from 'node:assert/strict';
import { test } from 'node:test';

import {
  importCompletedMessage,
  isZipBytes,
  totalHands,
  importFailedMessage,
  importStartedMessage,
  progressLine,
  progressPct,
  rebuildCompletedMessage,
  stageLabel,
  welcomeState,
} from '../src/lib/import-ui';

test('welcomeState', () => {
  assert.equal(welcomeState({ handCount: 0, phase: 'idle', importingIntoActive: false }), 'welcome');
  assert.equal(welcomeState({ handCount: 0, phase: 'uploading', importingIntoActive: true }), 'progress');
  assert.equal(welcomeState({ handCount: 0, phase: 'uploading', importingIntoActive: false }), 'welcome');
  assert.equal(welcomeState({ handCount: 10, phase: 'uploading', importingIntoActive: false }), 'content');
  assert.equal(welcomeState({ handCount: null, phase: 'idle', importingIntoActive: false }), 'content');
  assert.equal(welcomeState({ handCount: 0, phase: 'rebuilding', importingIntoActive: false }), 'welcome');
});

test('progressLine', () => {
  assert.equal(
    progressLine({ type: 'progress', processed: 1234, total: 5000, hands_per_sec: 2100, duplicates: 12, errors: 3 }),
    '1,234 / 5,000 hands · 2,100 h/s · 12 duplicates · 3 errors',
  );
  assert.equal(progressLine({ type: 'progress', processed: 1, total: 2, duplicates: 1, errors: 1 }), '1 / 2 hands · 1 duplicate · 1 error');
  assert.equal(progressLine(null), '');
});

test('progressPct and stageLabel', () => {
  assert.equal(progressPct({ type: 'progress', processed: 1, total: 4 }), 25);
  assert.equal(progressPct({ type: 'start' }), 0);
  assert.equal(stageLabel('h2n'), 'Importing from Hand2Note…');
  assert.equal(stageLabel('sample'), 'Importing sample data…');
  assert.equal(stageLabel('files'), 'Importing hand histories…');
});

test('toast messages', () => {
  assert.deepEqual(importCompletedMessage({ imported: 1234, duplicates: 56, errors: 0 }), {
    kind: 'success',
    title: 'Import completed',
    description: '1,234 hands imported · 56 duplicates · 0 errors',
  });
  assert.equal(importCompletedMessage({ imported: 0, duplicates: 5, errors: 0 }).title, 'No new hands');
  assert.equal(importFailedMessage('boom').kind, 'error');
  assert.equal(importFailedMessage('').description, 'Unknown error');
  assert.equal(importStartedMessage('files', 3).description, '3 files');
  assert.equal(importStartedMessage('files', 1).description, '1 file');
  assert.equal(rebuildCompletedMessage(2000).description, '2,000 hands recalculated');
});

test('totalHands sums every workspace', () => {
  assert.equal(totalHands([]), 0);
  assert.equal(totalHands([{ hand_count: 0 }, { hand_count: 2000 }, { hand_count: 5 }]), 2005);
});

test('isZipBytes checks the PK magic', () => {
  assert.equal(isZipBytes(new Uint8Array([0x50, 0x4b, 3, 4])), true);
  assert.equal(isZipBytes(new TextEncoder().encode('<!doctype html>')), false);
  assert.equal(isZipBytes(new Uint8Array([0x50])), false);
});
