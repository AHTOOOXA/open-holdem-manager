/**
 * A dashboard definition (player, date, game, profile) ↔ what the header shows and what the
 * General endpoints get. Pure, no React.
 *
 * Filters are plain steps in the order date, stakes, mode. A relative date preset keeps its id
 * (`PresetDateStep.preset`) and is re-derived from "now" every time params are built; the
 * backend never sees `preset` (stripUiFields).
 */
import type { GeneralFilterParams } from '../api-general';
import { GENERAL_CELLS } from '../h2n-layout';
import type { GeneralCellMeta } from '../h2n-layout';
import { popupTitle } from '../general-notation';
import { statTitle } from '../general-titles';
import {
  dateLabel, presetDateStep, presetOf, resolvePresets, sessionPresets, stepLabel, stripUiFields,
  type DatePresetDef,
} from '../reports/steps';
import type { Step } from '../reports/types';
import type { DashboardDefinition } from './types';

type Of<K extends Step['k']> = Extract<Step, { k: K }>;
export type GameMode = 'fast' | 'regular';

export const DEFAULT_PROFILE_ID = 'default';
export const PROFILE_IDS: readonly string[] = [DEFAULT_PROFILE_ID];

// ── Profile / dashboard type ─────────────────────────────────────────────────────────────────

/** An action cell of the General screen = a single-stat dashboard; anything else = a profile. */
export function singleStatMeta(profileId: string): GeneralCellMeta | null {
  const meta = GENERAL_CELLS[profileId];
  return meta && meta.kind === 'action' ? meta : null;
}

export function dashboardType(profileId: string): 'single' | 'profile' {
  return singleStatMeta(profileId) ? 'single' : 'profile';
}

/** Full stat name with arrows, as the popup title and the stat picker show it. */
export function statLabel(meta: GeneralCellMeta): string {
  return popupTitle(statTitle(meta));
}

/** Profile dropdown label: the profile name, the stat's name, or "--" when the id resolves to nothing. */
export function profileLabel(profileId: string): string {
  if (PROFILE_IDS.includes(profileId)) return profileId;
  const meta = singleStatMeta(profileId);
  return meta ? statLabel(meta) : '--';
}

// ── Reading the filters ─────────────────────────────────────────────────────────────────────

function stepOf<K extends Step['k']>(filters: readonly Step[], k: K): Of<K> | undefined {
  return filters.find((s) => s.k === k) as Of<K> | undefined;
}

export function dateStepOf(def: DashboardDefinition): Of<'date'> | undefined {
  return stepOf(def.filters, 'date');
}

export function stakesOf(def: DashboardDefinition): string | null {
  return stepOf(def.filters, 'stakes')?.v[0] ?? null;
}

export function modeOf(def: DashboardDefinition): GameMode | null {
  return stepOf(def.filters, 'mode')?.v ?? null;
}

/** 'all', a relative preset id ('week', ...) or 'custom'. */
export function dateChoiceId(def: DashboardDefinition): string {
  const d = dateStepOf(def);
  if (!d || (!d.from && !d.to)) return 'all';
  const id = presetOf(d);
  return id && sessionPresets().some((p) => p.id === id && p.from) ? id : 'custom';
}

/** Date button label: the preset name, the custom range, or "All Time". */
export function dateButtonLabel(def: DashboardDefinition): string {
  const d = dateStepOf(def);
  if (!d) return 'All Time';
  const id = presetOf(d);
  const preset = id ? sessionPresets().find((p) => p.id === id && p.from) : undefined;
  return preset ? preset.label : dateLabel(d.from, d.to);
}

/** The date range the filters mean right now (presets re-derived); nulls = unbounded. */
export function resolvedDateRange(def: DashboardDefinition, now: Date = new Date()): { from: string | null; to: string | null } {
  const d = resolvePresets(def.filters, now).find((s) => s.k === 'date') as Of<'date'> | undefined;
  return { from: d?.from ?? null, to: d?.to ?? null };
}

// ── Changing the filters ────────────────────────────────────────────────────────────────────

export type DateChoice =
  | { kind: 'all' }
  | { kind: 'preset'; preset: DatePresetDef }
  | { kind: 'custom'; from?: string; to?: string };

const ORDER: Step['k'][] = ['date', 'stakes', 'mode'];

/** Plain steps in date, stakes, mode order, empties dropped, labels filled. */
export function normaliseFilters(filters: readonly Step[]): Step[] {
  const out: Step[] = [];
  for (const k of ORDER) {
    const s = filters.find((x) => x.k === k);
    if (!s) continue;
    if (s.k === 'date' && !s.from && !s.to) continue;
    if (s.k === 'stakes' && s.v.length === 0) continue;
    // A relative preset keeps its own name ("This Week"); other steps get the readable fallback
    const label = presetOf(s) && s.label ? s.label : stepLabel({ ...s, label: undefined } as Step);
    out.push({ ...s, label } as Step);
  }
  return out;
}

function replaceStep(def: DashboardDefinition, k: Step['k'], step: Step | null): DashboardDefinition {
  const rest = def.filters.filter((s) => s.k !== k);
  return { ...def, filters: normaliseFilters(step ? [...rest, step] : rest) };
}

export function withDate(def: DashboardDefinition, choice: DateChoice, now: Date = new Date()): DashboardDefinition {
  if (choice.kind === 'all') return replaceStep(def, 'date', null);
  if (choice.kind === 'preset') {
    if (!choice.preset.from && !choice.preset.to) return replaceStep(def, 'date', null);
    return replaceStep(def, 'date', presetDateStep(choice.preset, now));
  }
  const from = choice.from || undefined;
  const to = choice.to || undefined;
  if (!from && !to) return replaceStep(def, 'date', null);
  return replaceStep(def, 'date', { k: 'date', from, to });
}

export function withStakes(def: DashboardDefinition, stakes: string | null): DashboardDefinition {
  return replaceStep(def, 'stakes', stakes ? { k: 'stakes', v: [stakes] } : null);
}

export function withMode(def: DashboardDefinition, mode: GameMode | null): DashboardDefinition {
  return replaceStep(def, 'mode', mode ? { k: 'mode', v: mode } : null);
}

export function withPlayer(def: DashboardDefinition, playerId: number | null): DashboardDefinition {
  return { ...def, player_id: playerId };
}

export function withProfile(def: DashboardDefinition, profileId: string): DashboardDefinition {
  return { ...def, profile_id: profileId };
}

/** Stable identity of a definition (labels ignored): same key = same results, nothing to rebuild. */
export function definitionKey(def: DashboardDefinition): string {
  const filters = def.filters.map((s) => {
    const preset = presetOf(s);
    return preset ? { k: 'date', preset } : stripUiFields([s], false)[0];
  });
  return JSON.stringify([def.player_id ?? null, def.profile_id, filters]);
}

export function sameDefinition(a: DashboardDefinition, b: DashboardDefinition): boolean {
  return definitionKey(a) === definitionKey(b);
}

// ── To the backend ──────────────────────────────────────────────────────────────────────────

/** /api/general params: the filters as `chain` (presets re-derived, UI fields stripped) + player. */
export function generalParams(def: DashboardDefinition, workspaceId: number, now: Date = new Date()): GeneralFilterParams {
  const chain = stripUiFields(resolvePresets(def.filters, now), false);
  const p: GeneralFilterParams = { workspace_id: workspaceId };
  if (def.player_id != null) p.player_id = def.player_id;
  if (chain.length > 0) p.chain = chain;
  return p;
}

/** Characters not allowed in file names on Windows / macOS, and control characters. */
// eslint-disable-next-line no-control-regex
const ILLEGAL_FILE_CHARS = /[\\/:*?"<>|\u0000-\u001f]/g;

/** "<dashboard name>, <player>.json" with illegal characters removed. */
export function exportFileName(dashboardName: string, player: string | null | undefined): string {
  const base = player ? `${dashboardName}, ${player}` : dashboardName;
  const clean = base.replace(ILLEGAL_FILE_CHARS, '').trim();
  return `${clean || 'dashboard'}.json`;
}
