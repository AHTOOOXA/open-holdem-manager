/** Pure helpers for the import UX (welcome view, status text, toasts). No React, no DOM. */

import type { ImportProgress, ImportResult } from './api';

export type ImportKind = 'files' | 'h2n' | 'sample';
export type ImportPhase = 'idle' | 'uploading' | 'rebuilding' | 'done' | 'error';
export type WelcomeState = 'welcome' | 'progress' | 'content';

const intFmt = new Intl.NumberFormat('en-US', { maximumFractionDigits: 0 });

/** 1234 -> "1,234" (locale independent). */
export function int(n: number): string {
  return intFmt.format(n);
}

function plural(n: number, one: string, many: string): string {
  return n === 1 ? one : many;
}

/**
 * What the Reports/Statistics/Sessions screens show.
 * - `progress`: an import that started into the (then empty) active workspace is running
 * - `welcome`: the active workspace has 0 hands
 * - `content`: otherwise (also while the workspace list is still loading: handCount null)
 */
export function welcomeState(args: {
  handCount: number | null;
  phase: ImportPhase;
  importingIntoActive: boolean;
}): WelcomeState {
  if (args.importingIntoActive && args.phase === 'uploading') return 'progress';
  if (args.handCount === 0) return 'welcome';
  return 'content';
}

export function stageLabel(kind: ImportKind): string {
  if (kind === 'h2n') return 'Importing from Hand2Note…';
  if (kind === 'sample') return 'Importing sample data…';
  return 'Importing hand histories…';
}

/** "1,234 / 5,000 hands · 2,100 h/s · 12 duplicates · 3 errors"; parts without data are skipped. */
export function progressLine(p: ImportProgress | null): string {
  if (!p) return '';
  const parts: string[] = [];
  const processed = p.processed ?? 0;
  if (p.total != null && p.total > 0) parts.push(`${int(processed)} / ${int(p.total)} hands`);
  else if (p.total_hands != null) parts.push(`${int(p.total_hands)} hands found`);
  if ((p.hands_per_sec ?? 0) > 0) parts.push(`${int(p.hands_per_sec ?? 0)} h/s`);
  if (p.duplicates != null) parts.push(`${int(p.duplicates)} ${plural(p.duplicates, 'duplicate', 'duplicates')}`);
  if (p.errors != null) parts.push(`${int(p.errors)} ${plural(p.errors, 'error', 'errors')}`);
  return parts.join(' · ');
}

/** Progress bar value, 0-100. */
export function progressPct(p: ImportProgress | null): number {
  if (!p || p.total == null || p.total <= 0) return 0;
  return Math.min(100, Math.round(((p.processed ?? 0) / p.total) * 100));
}

export interface ToastMessage {
  kind: 'success' | 'info' | 'error';
  title: string;
  description: string;
}

export function importStartedMessage(kind: ImportKind, fileCount: number, label?: string | null): ToastMessage {
  const description =
    kind === 'h2n' ? (label ?? 'Hand2Note database') : `${int(fileCount)} ${plural(fileCount, 'file', 'files')}`;
  return { kind: 'info', title: 'Import started', description };
}

export function importCompletedMessage(r: Pick<ImportResult, 'imported' | 'duplicates' | 'errors'>): ToastMessage {
  const description = `${int(r.imported)} hands imported · ${int(r.duplicates)} ${plural(r.duplicates, 'duplicate', 'duplicates')} · ${int(r.errors)} ${plural(r.errors, 'error', 'errors')}`;
  if (r.imported === 0) return { kind: 'info', title: 'No new hands', description };
  return { kind: 'success', title: 'Import completed', description };
}

export function importFailedMessage(error: string | null | undefined): ToastMessage {
  return { kind: 'error', title: 'Import failed', description: error || 'Unknown error' };
}

export function rebuildCompletedMessage(hands: number): ToastMessage {
  return { kind: 'success', title: 'Statistics rebuilt', description: `${int(hands)} ${plural(hands, 'hand', 'hands')} recalculated` };
}
