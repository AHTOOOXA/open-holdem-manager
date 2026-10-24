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

export function tsizeName(n: number | null): string {
  if (n == null) return 'unknown table size';
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
    case 'session': return `Session ${step.start.slice(0, 16).replace('T', ' ')}`;
    case 'table': return step.v.join(', ');
    case 'with': return `With player ${step.player_id}`;
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

/** Date of `base` shifted by whole days / months (day-of-month clamped to the target month). */
function shiftMonths(base: Date, months: number): Date {
  const first = new Date(base.getFullYear(), base.getMonth() + months, 1);
  const last = new Date(first.getFullYear(), first.getMonth() + 1, 0).getDate();
  return new Date(first.getFullYear(), first.getMonth(), Math.min(base.getDate(), last));
}

let appDayStartHour = 0;

/** The app-wide "Day starts at (hour)" setting; presets default to it (kept in sync by `useDayStartHour`). */
export function setAppDayStartHour(hour: number): void {
  appDayStartHour = Number.isInteger(hour) && hour >= 0 && hour <= 23 ? hour : 0;
}

export function getAppDayStartHour(): number {
  return appDayStartHour;
}

/** "Day starts at (hour)": before that hour it is still the previous calendar day. */
export function shiftForDayStart(now: Date, dayStartHour: number): Date {
  return dayStartHour > 0 ? new Date(now.getTime() - dayStartHour * 3_600_000) : now;
}

/**
 * The one date-preset function (Reports, Statistics, Sessions): presets relative to `now` shifted back
 * by `dayStartHour` (weeks start on Monday). "All Time" has no bounds.
 */
export function sessionPresets(realNow: Date = new Date(), dayStartHour: number = appDayStartHour): DatePresetDef[] {
  const now = shiftForDayStart(realNow, dayStartHour);
  const f = formatLocalDate;
  const today = new Date(now.getFullYear(), now.getMonth(), now.getDate());
  const addDays = (base: Date, n: number) => {
    const r = new Date(base);
    r.setDate(r.getDate() + n);
    return r;
  };
  const yesterday = addDays(today, -1);
  const thisMonday = addDays(today, -((today.getDay() + 6) % 7));
  const lastMonday = addDays(thisMonday, -7);
  const lastSunday = addDays(thisMonday, -1);
  const y = today.getFullYear();
  const m = today.getMonth();
  return [
    { id: 'today', label: 'Today', from: f(today), to: f(today) },
    { id: 'yesterday', label: 'Yesterday', from: f(yesterday), to: f(yesterday) },
    { id: 'week', label: 'This Week', from: f(thisMonday), to: f(today) },
    { id: 'lastweek', label: 'Last Week', from: f(lastMonday), to: f(lastSunday) },
    { id: 'month', label: 'This Month', from: f(new Date(y, m, 1)), to: f(today) },
    { id: 'lastmonth', label: 'Last Month', from: f(new Date(y, m - 1, 1)), to: f(new Date(y, m, 0)) },
    { id: 'last3', label: 'Last 3 Months', from: f(shiftMonths(today, -3)), to: f(today) },
    { id: 'year', label: 'This Year', from: f(new Date(y, 0, 1)), to: f(today) },
    { id: 'all', label: 'All Time' },
  ];
}

// ── Relative date presets stored on date steps ──────────────────────────────────────────────

/** A date step as the page state keeps it: the backend never sees `preset` (see `stripUiFields`). */
export type PresetDateStep = Of<'date'> & { preset?: string };

/** Preset id stored on a date step ('today', 'week', ...), if it is a relative preset. */
export function presetOf(step: Step): string | undefined {
  if (step.k !== 'date') return undefined;
  const id = (step as PresetDateStep).preset;
  return typeof id === 'string' ? id : undefined;
}

/** A date step that follows a preset: from/to are re-derived from `now` by `resolvePresets`. */
export function presetDateStep(preset: DatePresetDef, now: Date = new Date()): Step {
  const fresh = sessionPresets(now).find((x) => x.id === preset.id) ?? preset;
  return { k: 'date', from: fresh.from, to: fresh.to, label: preset.label, preset: preset.id } as PresetDateStep as Step;
}

/** Re-derive from/to of every date step carrying a known preset id. Same array when nothing changes. */
export function resolvePresets(steps: readonly Step[], now: Date = new Date()): Step[] {
  if (!steps.some((s) => presetOf(s))) return steps as Step[];
  const presets = sessionPresets(now);
  return steps.map((s) => {
    const id = presetOf(s);
    const p = id ? presets.find((x) => x.id === id && x.from) : undefined;
    return p ? ({ ...s, from: p.from, to: p.to } as Step) : s;
  });
}

/** Drop the fields the backend does not take (`preset`); keeps `label` unless `keepLabel` is false. */
export function stripUiFields(steps: readonly Step[], keepLabel = true): Step[] {
  return steps.map((step) => {
    const rest = { ...step } as Record<string, unknown>;
    delete rest.preset;
    if (!keepLabel) delete rest.label;
    return rest as unknown as Step;
  });
}
