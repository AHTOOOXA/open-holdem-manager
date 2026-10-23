/** Run: cd frontend && npx tsx --test tests/page-chain.test.ts */
import { test } from 'node:test';
import assert from 'node:assert/strict';
import {
  closeFrom, createChain, leftNeighbourId, levelOf, openNext, setWidth, truncateAfter, DEFAULT_PAGE_WIDTH,
} from '../src/lib/page-chain.ts';

const np = (title: string, inherited = title, state = 0) => ({ title, inherited, state });
const base = () => createChain(np('root'));

test('append when opening from the last page', () => {
  const c = openNext(openNext(base(), 0, np('a')), 1, np('b'));
  assert.deepEqual(c.pages.map((p) => p.title), ['root', 'a', 'b']);
  assert.equal(c.pages[1].width, DEFAULT_PAGE_WIDTH);
  assert.equal(new Set(c.pages.map((p) => p.id)).size, 3);
});

test('reuse slot and truncate when opening from a middle page', () => {
  const c = openNext(openNext(openNext(base(), 0, np('a')), 1, np('b')), 2, np('c'));
  const r = openNext(c, 0, np('a2'));
  assert.equal(r.pages.length, 2);
  assert.equal(r.pages[1].id, c.pages[1].id);
  assert.equal(r.pages[1].title, 'a2');
  assert.equal(r.pages[1].inherited, 'a2');
  assert.equal(r.pages[1].rev, c.pages[1].rev + 1);
});

test('state and width are kept on reuse, inherited replaced', () => {
  let c = openNext(base(), 0, np('a', 'x', 1));
  c = openNext(c, 1, np('b'));
  c = setWidth(c, 1, 640);
  c = { ...c, pages: c.pages.map((p, i) => (i === 1 ? { ...p, state: 42 } : p)) };
  const r = openNext(c, 0, np('a2', 'y', 99));
  assert.equal(r.pages[1].state, 42);
  assert.equal(r.pages[1].width, 640);
  assert.equal(r.pages[1].inherited, 'y');
});

test('closeFrom closes the page and everything right; page 0 is protected', () => {
  const c = openNext(openNext(openNext(base(), 0, np('a')), 1, np('b')), 2, np('c'));
  assert.equal(closeFrom(c, 2).pages.length, 2);
  assert.equal(closeFrom(c, 1).pages.length, 1);
  assert.equal(closeFrom(c, 0), c);
  assert.equal(closeFrom(c, 9), c);
});

test('truncateAfter keeps pages up to index', () => {
  const c = openNext(openNext(base(), 0, np('a')), 1, np('b'));
  assert.equal(truncateAfter(c, 0).pages.length, 1);
  assert.equal(truncateAfter(c, 2), c);
});

test('setWidth clamps and is immutable', () => {
  const c = openNext(base(), 0, np('a'));
  const w = setWidth(c, 1, 5);
  assert.equal(w.pages[1].width, 20);
  assert.equal(c.pages[1].width, DEFAULT_PAGE_WIDTH);
  assert.equal(setWidth(c, 1, DEFAULT_PAGE_WIDTH), c);
  assert.equal(setWidth(c, 7, 100), c);
});

test('levels cycle through three; lower is the next level', () => {
  assert.deepEqual([0, 1, 2, 3, 4].map((i) => levelOf(i).upper), [0, 1, 2, 0, 1]);
  assert.deepEqual([0, 1, 2, 3].map((i) => levelOf(i).lower), [1, 2, 0, 1]);
});

test('leftNeighbourId: the page on the left of the closing one, by id', () => {
  let c = base();
  c = openNext(c, 0, np('B'));
  c = openNext(c, 1, np('C'));
  assert.equal(leftNeighbourId(c.pages, 2), c.pages[1].id);
  assert.equal(leftNeighbourId(c.pages, 1), c.pages[0].id);
  assert.equal(leftNeighbourId(c.pages, 0), null);
  assert.equal(leftNeighbourId(c.pages, 3), null);
});
