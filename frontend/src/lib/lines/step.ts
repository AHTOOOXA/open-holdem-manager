/**
 * The Reports `line` step as the page state keeps it. The backend only takes `{ k: 'line', dsl }`
 * (+ label); the editors keep their model on the step so a chip can reopen them:
 *  - `rows`  the filter dialog's Actions tab (ActionRows)
 *  - `line`  the line builder's actions, `name` its optional name
 * `stripUiFields` (lib/reports/steps.ts) removes these before a request.
 */
import type { Pos, Step, Street } from '../reports/types';
import { cleanRows, describeLine, describeRows, fromDsl, LINE_POSITIONS, LINE_STREETS, ROW_ORDER, FACED_PREFLOP, rowsIssues, rowsToDsl, toDsl, validateLine } from './dsl';
import type { ActionRows, Line, LineAction } from './types';

export type LineStep = Extract<Step, { k: 'line' }> & { rows?: ActionRows; line?: Line; name?: string };

/** UI-only fields of a line step. */
export const LINE_UI_FIELDS = ['rows', 'line', 'name'] as const;

export function isLineStep(s: Step): s is LineStep {
  return s.k === 'line';
}

/** A line step made by the filter dialog's Actions tab. */
export function isActionsLineStep(s: Step): s is LineStep & { rows: ActionRows } {
  return s.k === 'line' && (s as LineStep).rows !== undefined;
}

/** A line step for the line builder (anything not made by the Actions tab). */
export function isCustomLineStep(s: Step): s is LineStep {
  return s.k === 'line' && (s as LineStep).rows === undefined;
}

/** Actions tab rows -> one line step; null when nothing is selected. */
export function actionsLineStep(rows: ActionRows): LineStep | null {
  const clean = cleanRows(rows);
  if (rowsIssues(clean).length) return null;
  const dsl = rowsToDsl(clean);
  return dsl ? { k: 'line', dsl, label: describeRows(clean), rows: clean } : null;
}

/** Builder line -> line step; null when the line is empty or can never match. */
export function customLineStep(line: Line, name?: string): LineStep | null {
  const check = validateLine(line);
  if (check.errors.length || !check.line.actions.length) return null;
  const n = name?.trim();
  const step: LineStep = { k: 'line', dsl: toDsl(check.line), label: n || describeLine(check.line), line: check.line };
  if (n) step.name = n;
  return step;
}

/** Readable description of a line step (the chip tooltip; its label may be a name). */
export function lineStepDescription(s: LineStep): string {
  if (s.rows) return describeRows(s.rows);
  const line = lineOfStep(s);
  return line ? describeLine(line) : s.dsl;
}

/** The builder model of a line step: its stored line, else parsed from the notation (null = cannot show). */
export function lineOfStep(s: LineStep): Line | null {
  return s.line ?? fromDsl(s.dsl);
}

// ── Structural checks (persisted chains) ────────────────────────────────────────────────────

const isObj = (x: unknown): x is Record<string, unknown> => !!x && typeof x === 'object' && !Array.isArray(x);
const STREET_SET = new Set<string>(LINE_STREETS);
const ROW_SET = new Set<string>(ROW_ORDER);
const FACED_SET = new Set<string>(FACED_PREFLOP.map((f) => f.id));
const POS_SET = new Set<string>(LINE_POSITIONS);
const TYPES = new Set(['fold', 'check', 'call', 'bet', 'raise']);

export function isActionRows(x: unknown): x is ActionRows {
  if (!isObj(x) || !isObj(x.streets) || !isObj(x.last)) return false;
  for (const [k, v] of Object.entries(x.streets)) {
    if (!STREET_SET.has(k) || !Array.isArray(v) || !v.every((r) => typeof r === 'string' && ROW_SET.has(r))) return false;
  }
  for (const [k, v] of Object.entries(x.last)) if (!STREET_SET.has(k) || typeof v !== 'boolean') return false;
  if (x.faced !== undefined && !(Array.isArray(x.faced) && x.faced.every((f) => typeof f === 'string' && FACED_SET.has(f)))) return false;
  return true;
}

function isLineAction(x: unknown): x is LineAction {
  if (!isObj(x)) return false;
  return typeof x.id === 'string'
    && typeof x.street === 'string' && STREET_SET.has(x.street as Street)
    && (x.who === 'hero' || x.who === 'villain')
    && typeof x.a === 'string' && TYPES.has(x.a)
    && (x.raise === undefined || x.raise === 'any' || x.raise === 'open' || x.raise === '3bet')
    && (x.pos === undefined || (Array.isArray(x.pos) && x.pos.every((p) => typeof p === 'string' && POS_SET.has(p as Pos))))
    && (x.same === undefined || typeof x.same === 'boolean')
    && (x.last === undefined || typeof x.last === 'boolean');
}

export function isLine(x: unknown): x is Line {
  return isObj(x) && Array.isArray(x.actions) && x.actions.every(isLineAction);
}

/** A stored line step with malformed UI fields loses them (the notation still applies). */
export function sanitizeLineStep(step: Step): Step {
  if (step.k !== 'line') return step;
  const s = { ...step } as Record<string, unknown>;
  if (s.rows !== undefined && !isActionRows(s.rows)) delete s.rows;
  if (s.line !== undefined && !isLine(s.line)) delete s.line;
  if (s.name !== undefined && typeof s.name !== 'string') delete s.name;
  return s as unknown as Step;
}
