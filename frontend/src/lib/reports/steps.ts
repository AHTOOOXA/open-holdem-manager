/** Pure helpers for the filter steps a Reports page edits itself (FilterDialog). */
import { formatLocalDate } from '../format/date';
import type { Pos, Step } from './types';

export type FilterTab = 'quick' | 'positions' | 'general' | 'session';

type Of<K extends Step['k']> = Extract<Step, { k: K }>;

export interface OwnSteps {
  row?: Of<'row'>;
  pos?: Of<'pos'>;
  stakes?: Of<'stakes'>;
  mode?: Of<'mode'>;
  tsize?: Of<'tsize'>;
  stack?: Of<'stack'>;
  date?: Of<'date'>;
  /** Everything the dialog does not edit (and duplicates of an edited kind), original order. */
  other: Step[];
}

export const POSITIONS: Pos[] = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];
const OWN_ORDER = ['row', 'pos', 'stakes', 'mode', 'tsize', 'stack', 'date'] as const;
type OwnKind = (typeof OWN_ORDER)[number];

export function tsizeName(n: number): string {
  return n === 2 ? 'Heads-up' : `${n}-max`;
}

export function stackLabel(lo: number, hi: number | null): string {
  if (hi == null) return `${lo}+ bb`;
  if (lo <= 0) return `< ${hi} bb`;
  return `${lo}-${hi} bb`;
}

export function dateLabel(from?: string, to?: string): string {
  if (from && to) return from === to ? from : `${from} – ${to}`;
  if (from) return `From ${from}`;
  if (to) return `Until ${to}`;
  return 'All Time';
}

/** Chip text for a step; the step's own `label` wins, else a readable fallback. */
export function stepLabel(step: Step): string {
  if (step.label) return step.label;
  switch (step.k) {
    case 'pos': return step.v.join(', ');
    case 'stakes': return step.v.join(', ');
    case 'mode': return step.v === 'fast' ? 'Fast Fold' : 'Regular';
    case 'tsize': return step.v.map(tsizeName).join(', ');
    case 'date': return dateLabel(step.from, step.to);
    case 'hour': return `Hour ${step.v.join(', ')}`;
    case 'stack': return stackLabel(step.lo, step.hi);
    case 'game': return `${step.stakes} ${step.mode} ${tsizeName(step.tsize)}`;
    case 'cells': return step.v.join(', ');
    case 'hv': return step.cats.join(', ');
    case 'row': return step.key;
    case 'next': return `${step.street}: ${step.a}`;
    case 'faced': return `${step.street}: ${step.a}`;
    case 'betsize': return step.bucket;
  }
}

/** Which dialog tab edits this step (double-click on a chip); null = not editable there. */
export function stepKindTab(step: Step): FilterTab | null {
  switch (step.k) {
    case 'row': return 'quick';
    case 'pos': return 'positions';
    case 'stakes': case 'mode': case 'tsize': case 'stack': return 'general';
    case 'date': return 'session';
    default: return null;
  }
}

export function splitOwnSteps(steps: Step[]): OwnSteps {
  const out: OwnSteps = { other: [] };
  for (const s of steps) {
    const kind = s.k as OwnKind;
    if (OWN_ORDER.includes(kind) && out[kind] === undefined) {
      (out as unknown as Record<string, Step>)[kind] = s;
    } else {
      out.other.push(s);
    }
  }
  return out;
}

function isEmpty(s: Step): boolean {
  switch (s.k) {
    case 'pos': case 'stakes': case 'tsize': return s.v.length === 0;
    case 'date': return !s.from && !s.to;
    case 'stack': return s.lo <= 0 && s.hi == null;
    default: return false;
  }
}

/** Drop empty steps, fill labels, order row, pos, stakes, mode, tsize, stack, date; others follow unchanged. */
export function normaliseOwnSteps(steps: Step[]): Step[] {
  const parts = splitOwnSteps(steps);
  const own: Step[] = [];
  for (const kind of OWN_ORDER) {
    const s = parts[kind];
    if (!s || isEmpty(s)) continue;
    own.push({ ...s, label: stepLabel(s) } as Step);
  }
  return [...own, ...parts.other];
}

export interface DatePresetDef {
  id: string;
  label: string;
  from?: string;
  to?: string;
}

/** Session-tab presets relative to `now` (weeks start on Monday). "All Time" has no bounds. */
export function sessionPresets(now: Date = new Date()): DatePresetDef[] {
  const d = (y: number, m: number, day: number) => new Date(y, m, day);
  const y = now.getFullYear();
  const m = now.getMonth();
  const day = now.getDate();
  const mondayOffset = (now.getDay() + 6) % 7;
  const thisMonday = d(y, m, day - mondayOffset);
  const f = formatLocalDate;
  return [
    { id: 'today', label: 'Today', from: f(now), to: f(now) },
    { id: 'yesterday', label: 'Yesterday', from: f(d(y, m, day - 1)), to: f(d(y, m, day - 1)) },
    { id: 'week', label: 'This Week', from: f(thisMonday), to: f(now) },
    { id: 'lastweek', label: 'Last Week', from: f(d(y, m, thisMonday.getDate() - 7)), to: f(d(y, m, thisMonday.getDate() - 1)) },
    { id: 'month', label: 'This Month', from: f(d(y, m, 1)), to: f(now) },
    { id: 'lastmonth', label: 'Last Month', from: f(d(y, m - 1, 1)), to: f(d(y, m, 0)) },
    { id: 'last3', label: 'Last 3 Months', from: f(d(y, m - 3, day)), to: f(now) },
    { id: 'year', label: 'This Year', from: f(d(y, 0, 1)), to: f(now) },
    { id: 'all', label: 'All Time' },
  ];
}
