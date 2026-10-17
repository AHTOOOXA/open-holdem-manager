/**
 * Full descriptive names of the General screen stats, and the action each
 * stat measures.
 *
 * The grid shows short row labels ("Open Raise", column "EP"); the stat
 * popup title and the cell's accessible name use the full name, which spells
 * out the position and the preflop line the stat is conditioned on
 * ("Open Raise: Early Position", "Call Raise → Fold to Continuation Bet").
 * Every "->" is drawn as an arrow by `popupTitle`.
 *
 * Pure data + functions, no React.
 */

import type { GeneralCellMeta } from './h2n-layout';

const POSITION_NAMES: Record<string, string> = {
  EP: 'Early Position',
  MP: 'Middle Position',
  CO: 'Cutoff',
  BTN: 'Button',
  SB: 'Small Blind',
  BB: 'Big Blind',
};

const STREET_NAMES = ['Flop', 'Turn', 'River'] as const;

const TITLES: Record<string, string> = {
  // Top line
  'summary.hands.Total': 'Hands',
  'summary.bb100.Total': 'Win Rate (bb/100)',
  'summary.vpip.Total': 'Voluntarily Put Money In Pot (VPIP)',
  'summary.pfr.Total': 'Preflop Raise (PFR)',

  // PRE-FLOP right list
  'preflop.four_bet.Total': 'Open Raise -> 4-Bet',
  'preflop.four_bet_range.Total': '4-Bet Range',
  'preflop.four_bet_fold.Total': 'Open Raise -> 4-Bet -> Fold to 5-Bet',
  'preflop.fold_to_4bet.Total': '3-Bet -> Fold to 4-Bet',
  'preflop.call_4bet.Total': '3-Bet -> Call 4-Bet',
  'preflop.five_bet.Total': '3-Bet -> 5-Bet',
  'preflop.limp.Total': 'Limp',
  'preflop.limp_fold.Total': 'Limp -> Fold to Raise',
  'preflop.squeeze.Total': 'Squeeze',

  // Steal
  'steal.steal.Total': 'Steal (Raise First In): Button, Small Blind',
  'steal.fold_to_3bet.Total': 'Steal -> Fold to 3-Bet from the Blinds',
  'steal.four_bet.Total': 'Steal -> 4-Bet vs. 3-Bet from the Blinds',
  'steal.four_bet_fold.Total': 'Steal -> 4-Bet -> Fold to 5-Bet from the Blinds',
  'steal.vs_steal_fold.SB': 'Small Blind vs. Button Steal: Fold',
  'steal.vs_steal_fold.BB': 'Big Blind vs. Steal: Fold',
  'steal.vs_steal_call.SB': 'Small Blind vs. Button Steal: Call',
  'steal.vs_steal_call.BB': 'Big Blind vs. Steal: Call',
  'steal.vs_steal_3bet.SB': 'Small Blind vs. Button Steal: 3-Bet',
  'steal.vs_steal_3bet.BB': 'Big Blind vs. Steal: 3-Bet',

  // POSTFLOP: vs. c-bet rows
  'postflop.vs_cbet_raised.Fold': 'Call Raise -> Fold to Continuation Bet',
  'postflop.vs_cbet_raised.Call': 'Call Open Raise -> Call Continuation Bet',
  'postflop.vs_cbet_raised.Raise': 'Call Open Raise -> Raise Continuation Bet',
  'postflop.vs_cbet_3bet.Fold': 'Call 3-Bet -> Fold to Continuation Bet',
  'postflop.vs_cbet_3bet.Call': 'Call 3-Bet -> Call Continuation Bet',
  'postflop.vs_cbet_3bet.Raise': 'Call 3-Bet -> Raise Continuation Bet',

  // POSTFLOP: missed c-bet
  'postflop.missed_cbet.Flop': 'Raise 1st -> Check (Missed Continuation Bet)',
  'postflop.missed_cbet_ip.Flop': 'Raise 1st -> Check: In Position',
  'postflop.missed_cbet_ip_fold.Turn': 'Raise 1st -> Check: In Position -> Fold to Turn Bet',
  'postflop.missed_cbet_oop.Flop': 'Raise 1st -> Check: Out of Position',
  'postflop.missed_cbet_oop_fold.Flop': 'Raise 1st -> Check: Out of Position -> Fold',

  // POSTFLOP: vs. missed c-bet
  'postflop.vs_missed_cbet.Flop': 'Bet vs. Missed Continuation Bet',
  'postflop.vs_missed_cbet_bet_ip.Flop': 'Call Raise -> Bet: In Position',
  'postflop.vs_missed_cbet_check_fold_ip.Turn': 'Call Raise -> Check -> Fold: In Position',
  'postflop.vs_missed_cbet_bet_oop.Turn': 'Call Raise -> Check -> Bet: Out of Position',
  'postflop.vs_missed_cbet_check_fold_oop.Turn': 'Call Raise -> Check -> Fold: Out of Position',

  // POSTFLOP: showdown
  'postflop.wtsd.Total': 'Went to Showdown',
  'postflop.wsd.Total': 'Won Hand at Showdown',
  'postflop.wwsf.Total': 'Won Hand After Seeing Flop',
};

function pos(col: string): string {
  return POSITION_NAMES[col] ?? col;
}

/** Positional preflop / steal rows: `Total` keeps the row name, positions append theirs. */
function positionalTitle(meta: GeneralCellMeta): string | null {
  const c = meta.column;
  const at = (base: string) => (c === 'Total' ? base : `${base}: ${pos(c)}`);
  switch (`${meta.section}.${meta.stat}`) {
    case 'preflop.open_raise':
      return at('Open Raise');
    case 'preflop.fold_to_3bet':
      return c === 'Total' ? 'Open Raise -> Fold to 3-Bet' : `Open Raise -> Fold to 3-Bet: ${pos(c)}`;
    case 'preflop.call_open_raise':
      return at('Call Open Raise');
    case 'preflop.three_bet':
    case 'preflop.three_bet_ip':
    case 'preflop.three_bet_oop': {
      // EP..BTN in all three rows are the same stat (a 3-bet against the opener from that seat).
      if (['EP', 'MP', 'CO', 'BTN'].includes(c)) return `3-Bet: ${pos(c)}, In Position`;
      if (c === 'SB') return '3-Bet: Small Blind, Out of Position';
      if (c === 'Total') {
        if (meta.stat === 'three_bet_ip') return '3-Bet: In Position';
        if (meta.stat === 'three_bet_oop') return '3-Bet: Out of Position';
        return '3-Bet';
      }
      if (c === 'BB') {
        if (meta.stat === 'three_bet_ip') return '3-Bet: Big Blind vs. Small Blind, In Position';
        if (meta.stat === 'three_bet_oop') return '3-Bet: Big Blind, Out of Position';
        return '3-Bet: Big Blind';
      }
      return null;
    }
    case 'steal.steal':
      return c === 'Total' ? null : `Steal (Raise First In): ${pos(c)}`;
    case 'steal.fold_to_3bet':
      // The BTN cell repeats the preflop Fold to 3-Bet / BTN stat.
      if (c === 'BTN') return 'Open Raise -> Fold to 3-Bet: Button';
      return c === 'Total' ? null : `Steal -> Fold to 3-Bet: ${pos(c)}`;
    case 'steal.four_bet':
      return c === 'Total' ? null : `Steal -> 4-Bet: ${pos(c)}`;
    case 'steal.four_bet_fold':
      return c === 'Total' ? null : `Steal -> 4-Bet -> Fold to 5-Bet: ${pos(c)}`;
    default:
      return null;
  }
}

/** Per-street postflop rows; the c-bet line is spelled out street by street. */
function streetTitle(meta: GeneralCellMeta): string | null {
  const i = STREET_NAMES.indexOf(meta.column as (typeof STREET_NAMES)[number]);
  if (i < 0) return null;
  const street = STREET_NAMES[i];
  switch (meta.stat) {
    case 'cbet':
      return ['Raise 1st -> Continuation Bet', 'Raise 1st -> Continuation Bet -> Turn Continuation Bet', 'Raise 1st -> Continuation Bet -> Turn Continuation Bet -> River Continuation Bet'][i];
    case 'fold_to_cbet':
      return ['Call Raise -> Fold to Continuation Bet', 'Call Raise -> Call -> Fold to Turn Bet', 'Call Raise -> Call -> Call -> Fold to River Bet'][i];
    case 'donk':
      return ['Call Raise -> Donk Bet: Flop', 'Call Raise -> Call -> Donk Bet: Turn', 'Call Raise -> Call Turn -> Donk Bet: River'][i];
    case 'af':
      return `Aggression: ${street}`;
    case 'afq':
      return `Aggression Frequency: ${street}`;
    default:
      return null;
  }
}

/** The stat's full descriptive name (popup title, cell accessible name). */
export function statTitle(meta: GeneralCellMeta): string {
  return TITLES[meta.id] ?? positionalTitle(meta) ?? streetTitle(meta) ?? meta.name;
}

/** Stats whose value is a built-in total rather than a hand-pattern stat. */
const SYSTEM_STATS = new Set(['summary.hands.Total', 'summary.bb100.Total', 'preflop.four_bet_range.Total']);

/**
 * Native tooltip of a grid cell: built-in totals (Hands, Win Rate, 4-Bet
 * Range) show their full name, other expression stats their formula, and
 * action stats nothing (clicking opens their detail).
 */
export function cellTooltip(meta: GeneralCellMeta): string | undefined {
  if (SYSTEM_STATS.has(meta.id)) return statTitle(meta);
  if (meta.kind === 'expression') return meta.formula ?? statTitle(meta);
  return undefined;
}

/** The action a stat measures; the popup remembers its last tab per (street group, action). */
export type StatAction = 'raise' | 'call' | 'fold' | 'bet' | 'check' | 'vpip';

const ACTION_BY_STAT: Record<string, StatAction> = {
  'summary.vpip': 'vpip',
  'summary.pfr': 'raise',
  'preflop.open_raise': 'raise',
  'preflop.fold_to_3bet': 'fold',
  'preflop.call_open_raise': 'call',
  'preflop.three_bet': 'raise',
  'preflop.three_bet_ip': 'raise',
  'preflop.three_bet_oop': 'raise',
  'preflop.four_bet': 'raise',
  'preflop.four_bet_fold': 'fold',
  'preflop.fold_to_4bet': 'fold',
  'preflop.call_4bet': 'call',
  'preflop.five_bet': 'raise',
  'preflop.limp': 'call',
  'preflop.limp_fold': 'fold',
  'preflop.squeeze': 'raise',
  'steal.steal': 'raise',
  'steal.fold_to_3bet': 'fold',
  'steal.four_bet': 'raise',
  'steal.four_bet_fold': 'fold',
  'steal.vs_steal_fold': 'fold',
  'steal.vs_steal_call': 'call',
  'steal.vs_steal_3bet': 'raise',
  'postflop.cbet': 'bet',
  'postflop.fold_to_cbet': 'fold',
  'postflop.donk': 'bet',
  'postflop.missed_cbet': 'check',
  'postflop.missed_cbet_ip': 'check',
  'postflop.missed_cbet_oop': 'check',
  'postflop.missed_cbet_ip_fold': 'fold',
  'postflop.missed_cbet_oop_fold': 'fold',
  'postflop.vs_missed_cbet_bet_ip': 'bet',
  'postflop.vs_missed_cbet_bet_oop': 'bet',
  'postflop.vs_missed_cbet_check_fold_ip': 'fold',
  'postflop.vs_missed_cbet_check_fold_oop': 'fold',
};

export function statAction(meta: GeneralCellMeta): StatAction | null {
  if (meta.stat === 'vs_cbet_raised' || meta.stat === 'vs_cbet_3bet') {
    return meta.column.toLowerCase() as StatAction;
  }
  return ACTION_BY_STAT[`${meta.section}.${meta.stat}`] ?? null;
}
