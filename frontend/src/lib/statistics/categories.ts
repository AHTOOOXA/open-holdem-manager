/**
 * The "Existing Stat…" picker: the General screen's action stats, their categories and search.
 *
 * Categories follow the line the stat starts from (a stat can be in several):
 *  - Raise 1st     hero raised first in preflop (Open Raise, Steal and everything after them, C-Bets, missed C-Bets)
 *  - Preflop Call  hero called a raise preflop (Call Open Raise, vs. Steal call, play after calling)
 *  - 3Bet          hero 3-bet preflop (3-Bet, Squeeze and what follows)
 *  - Call 3Bet     hero called a 3-bet (the vs. C-Bet in 3-bet pot block)
 *  - Flop bet      the stat's line has a hero flop bet (C-Bet flop and the turn / river barrels, flop donk, bet vs. missed C-Bet)
 *  - Flop call     the line has a hero flop call (calling the flop C-Bet, the turn / river spots after it)
 * Expression stats (Aggression, WTSD...) have no detail view and are not offered; cells that only
 * repeat another cell (`sameAs`) are listed once.
 */
import { GENERAL_CELL_IDS, GENERAL_CELLS } from '../h2n-layout';
import type { GeneralCellMeta } from '../h2n-layout';
import { matchesSearch } from './tree';
import { statLabel } from './definition';

export type StatCategory = 'all' | 'raise1st' | 'pf_call' | '3bet' | 'call_3bet' | 'flop_bet' | 'flop_call';

export const STAT_CATEGORIES: readonly { id: StatCategory; label: string }[] = [
  { id: 'all', label: 'All stats' },
  { id: 'raise1st', label: 'Raise 1st' },
  { id: 'pf_call', label: 'Preflop Call' },
  { id: '3bet', label: '3Bet' },
  { id: 'call_3bet', label: 'Call 3Bet' },
  { id: 'flop_bet', label: 'Flop bet' },
  { id: 'flop_call', label: 'Flop call' },
];

/** section.stat → categories (besides 'all'); a column-specific entry wins (`section.stat.Column`). */
const BY_STAT: Record<string, StatCategory[]> = {
  'preflop.open_raise': ['raise1st'],
  'preflop.fold_to_3bet': ['raise1st'],
  'preflop.four_bet': ['raise1st'],
  'preflop.four_bet_fold': ['raise1st'],
  'steal.steal': ['raise1st'],
  'steal.fold_to_3bet': ['raise1st'],
  'steal.four_bet': ['raise1st'],
  'steal.four_bet_fold': ['raise1st'],
  'postflop.cbet': ['raise1st', 'flop_bet'],
  'postflop.missed_cbet': ['raise1st'],
  'postflop.missed_cbet_ip': ['raise1st'],
  'postflop.missed_cbet_ip_fold': ['raise1st'],
  'postflop.missed_cbet_oop': ['raise1st'],
  'postflop.missed_cbet_oop_fold': ['raise1st'],

  'preflop.call_open_raise': ['pf_call'],
  'steal.vs_steal_call': ['pf_call'],
  'postflop.fold_to_cbet.Flop': ['pf_call'],
  'postflop.fold_to_cbet': ['pf_call', 'flop_call'],
  'postflop.donk.Flop': ['pf_call', 'flop_bet'],
  'postflop.donk': ['pf_call', 'flop_call'],
  'postflop.vs_cbet_raised.Call': ['pf_call', 'flop_call'],
  'postflop.vs_cbet_raised': ['pf_call'],
  'postflop.vs_missed_cbet_bet_ip': ['pf_call', 'flop_bet'],
  'postflop.vs_missed_cbet_check_fold_ip': ['pf_call'],
  'postflop.vs_missed_cbet_bet_oop': ['pf_call'],
  'postflop.vs_missed_cbet_check_fold_oop': ['pf_call'],

  'preflop.three_bet': ['3bet'],
  'preflop.three_bet_ip': ['3bet'],
  'preflop.three_bet_oop': ['3bet'],
  'preflop.fold_to_4bet': ['3bet'],
  'preflop.call_4bet': ['3bet'],
  'preflop.five_bet': ['3bet'],
  'preflop.squeeze': ['3bet'],
  'steal.vs_steal_3bet': ['3bet'],

  'postflop.vs_cbet_3bet.Call': ['call_3bet', 'flop_call'],
  'postflop.vs_cbet_3bet': ['call_3bet'],
};

/** Categories of one stat, 'all' first. */
export function statCategories(meta: GeneralCellMeta): StatCategory[] {
  const own = BY_STAT[`${meta.section}.${meta.stat}.${meta.column}`] ?? BY_STAT[`${meta.section}.${meta.stat}`] ?? [];
  return ['all', ...own];
}

export interface PickableStat {
  id: string;
  label: string;
  street: GeneralCellMeta['street'];
  categories: StatCategory[];
}

/** Every action stat the picker offers, in General screen order. */
export const PICKABLE_STATS: readonly PickableStat[] = GENERAL_CELL_IDS
  .map((id) => GENERAL_CELLS[id])
  .filter((m) => m.kind === 'action' && !m.sameAs)
  .map((m) => ({ id: m.id, label: statLabel(m), street: m.street, categories: statCategories(m) }));

export function categoryCounts(stats: readonly PickableStat[]): Record<StatCategory, number> {
  const out = Object.fromEntries(STAT_CATEGORIES.map((c) => [c.id, 0])) as Record<StatCategory, number>;
  for (const s of stats) for (const c of s.categories) out[c] += 1;
  return out;
}

/** Stats matching the search (same rule as the tree search), optionally in one category. */
export function filterStats(stats: readonly PickableStat[], search: string, category: StatCategory = 'all'): PickableStat[] {
  return stats.filter((s) => s.categories.includes(category) && matchesSearch(s.label, search));
}
