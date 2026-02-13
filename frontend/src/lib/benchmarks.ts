import type { StatValue, HeroStats, PositionalStats } from '@/lib/api';

// ── Types ────────────────────────────────────────────────────────────

export interface BenchmarkRange {
  low: number;
  high: number;
  tipLow: string;
  tipHigh: string;
  fix: string;
  weight: number;
  /** hand_players column that must be true for "View hands" link */
  statFlagFilter?: string;
  /** opportunity column (also must be true) for "View hands" link */
  oppFlagFilter?: string;
}

export interface PositionalBenchmarks {
  total: BenchmarkRange;
  ep?: BenchmarkRange;
  mp?: BenchmarkRange;
  co?: BenchmarkRange;
  btn?: BenchmarkRange;
  sb?: BenchmarkRange;
  bb?: BenchmarkRange;
}

export type StatHealth = {
  status: 'green' | 'yellow' | 'red' | 'neutral';
  direction?: 'low' | 'high';
};

// ── Display names ────────────────────────────────────────────────────

export const STAT_DISPLAY_NAMES: Record<string, string> = {
  vpip: 'VPIP',
  pfr: 'PFR',
  open_raise: 'Open Raise',
  three_bet: '3-Bet',
  fold_to_3bet: 'Fold to 3-Bet',
  four_bet: '4-Bet',
  fold_to_4bet: 'Fold to 4-Bet',
  limp: 'Limp',
  steal: 'Steal',
  vs_steal_fold: 'vs Steal Fold',
  cbet_flop: 'C-Bet Flop',
  cbet_turn: 'C-Bet Turn',
  cbet_river: 'C-Bet River',
  fold_to_cbet_flop: 'Fold to CBet Flop',
  fold_to_cbet_turn: 'Fold to CBet Turn',
  wtsd: 'WTSD',
  wsd: 'W$SD',
  wwsf: 'WWSF',
  af_flop: 'AF Flop',
  af_turn: 'AF Turn',
  af_river: 'AF River',
};

// ── Benchmarks ───────────────────────────────────────────────────────

export const BENCHMARKS: Record<string, PositionalBenchmarks> = {
  vpip: {
    total: {
      low: 20, high: 28,
      tipLow: 'Playing too few hands. Widen your opening range, especially in position.',
      tipHigh: 'Playing too many hands. Tighten preflop — fold more weak holdings.',
      fix: 'Review your opening ranges by position. Compare to standard GTO charts.',
      weight: 5,
      statFlagFilter: 'vpip',
    },
    ep: { low: 12, high: 18, tipLow: 'EP VPIP too tight. Missing value with playable hands.', tipHigh: 'EP VPIP too loose. Tighten from early position.', fix: 'EP should play ~15% of hands.', weight: 3 },
    mp: { low: 15, high: 22, tipLow: 'MP VPIP too tight.', tipHigh: 'MP VPIP too loose.', fix: 'MP should play ~18% of hands.', weight: 3 },
    co: { low: 24, high: 32, tipLow: 'CO VPIP too tight. Open wider in the cutoff.', tipHigh: 'CO VPIP too loose.', fix: 'CO should play ~28% of hands.', weight: 3 },
    btn: { low: 35, high: 50, tipLow: 'BTN VPIP too tight. You have position -- play wider.', tipHigh: 'BTN VPIP too loose.', fix: 'BTN should play ~42% of hands.', weight: 3 },
    sb: { low: 28, high: 40, tipLow: 'SB VPIP too tight.', tipHigh: 'SB VPIP too loose. Cold-calling OOP is expensive.', fix: 'SB VPIP-PFR gap should be 0-5%. Raise or fold.', weight: 3 },
    bb: { low: 35, high: 55, tipLow: 'BB VPIP too tight. Defend more vs steals.', tipHigh: 'BB VPIP too loose. Overdefending OOP costs money.', fix: 'BB defends wide vs steals. Adjust by raiser position.', weight: 3 },
  },
  pfr: {
    total: {
      low: 16, high: 24,
      tipLow: 'Too passive preflop. Raise more instead of limping or cold-calling.',
      tipHigh: 'Too aggressive preflop. Narrow your raising range.',
      fix: 'Your VPIP-PFR gap should be ~4-6%. Reduce cold-calls and limps.',
      weight: 5,
      statFlagFilter: 'pfr',
    },
    ep: { low: 10, high: 16, tipLow: 'EP PFR too tight.', tipHigh: 'EP PFR too loose.', fix: 'EP should raise ~13%.', weight: 3 },
    mp: { low: 13, high: 19, tipLow: 'MP PFR too tight.', tipHigh: 'MP PFR too loose.', fix: 'MP should raise ~16%.', weight: 3 },
    co: { low: 20, high: 28, tipLow: 'CO PFR too tight.', tipHigh: 'CO PFR too loose.', fix: 'CO should raise ~24%.', weight: 3 },
    btn: { low: 30, high: 45, tipLow: 'BTN PFR too tight. Raise wider on the button.', tipHigh: 'BTN PFR too loose.', fix: 'BTN should raise ~37%.', weight: 3 },
    sb: { low: 25, high: 38, tipLow: 'SB PFR too tight. Modern SB strategy is raise-or-fold.', tipHigh: 'SB PFR too loose.', fix: 'SB PFR should be close to SB VPIP. Raise or fold.', weight: 3 },
    bb: { low: 8, high: 14, tipLow: 'BB PFR too tight. Missing 3-bet and squeeze opportunities.', tipHigh: 'BB PFR too high. Over-3-betting from the big blind.', fix: 'BB PFR = 3-bets + squeezes from BB.', weight: 3 },
  },
  open_raise: {
    total: {
      low: 15, high: 30,
      tipLow: 'Not opening enough hands when folded to you. Missing value.',
      tipHigh: 'Opening too wide. Opponents will exploit you with 3-bets.',
      fix: 'Study RFI charts for each position. EP ~15%, BTN ~45%.',
      weight: 4,
      statFlagFilter: 'open_raise',
      oppFlagFilter: 'open_raise_opp',
    },
    ep: { low: 12, high: 18, tipLow: 'EP open too tight.', tipHigh: 'EP open too wide.', fix: 'EP should open ~15%.', weight: 3 },
    mp: { low: 15, high: 22, tipLow: 'MP open too tight.', tipHigh: 'MP open too wide.', fix: 'MP should open ~18%.', weight: 3 },
    co: { low: 22, high: 35, tipLow: 'CO open too tight.', tipHigh: 'CO open too wide.', fix: 'CO should open ~28%.', weight: 3 },
    btn: { low: 38, high: 55, tipLow: 'BTN open too tight.', tipHigh: 'BTN open too wide.', fix: 'BTN should open ~45%.', weight: 3 },
    sb: { low: 30, high: 50, tipLow: 'SB open too tight.', tipHigh: 'SB open too wide.', fix: 'SB should open ~40% (raise or fold).', weight: 3 },
  },
  three_bet: {
    total: {
      low: 6, high: 10,
      tipLow: 'Not 3-betting enough. Opponents can open wide without punishment.',
      tipHigh: 'Over 3-betting. Opponents will adjust with wider 4-bet ranges.',
      fix: 'Add more 3-bet bluffs (suited connectors, A-x suited) from good positions.',
      weight: 4,
      statFlagFilter: 'three_bet',
      oppFlagFilter: 'three_bet_opp',
    },
  },
  fold_to_3bet: {
    total: {
      low: 55, high: 65,
      tipLow: 'Calling/4-betting too much vs 3-bets. Tighten your continue range.',
      tipHigh: 'Folding too much to 3-bets. Opponents can 3-bet bluff profitably.',
      fix: 'Defend ~35-45% of your opens vs 3-bets. More IP, less OOP.',
      weight: 4,
      statFlagFilter: 'fold_to_3bet',
      oppFlagFilter: 'three_bet_opp',
    },
  },
  four_bet: {
    total: {
      low: 3, high: 7,
      tipLow: 'Not 4-betting enough. Only premiums — too predictable.',
      tipHigh: 'Over 4-betting. Opponents will trap with strong hands.',
      fix: 'Balance 4-bet range: ~50% value (QQ+, AKs), ~50% bluffs (A5s, A4s).',
      weight: 2,
      statFlagFilter: 'four_bet',
      oppFlagFilter: 'four_bet_opp',
    },
    ep: { low: 8, high: 18, tipLow: 'EP 4-bet too low vs 3-bets.', tipHigh: 'EP 4-bet too high.', fix: 'EP opens tight so 4-bets a large % when 3-bet.', weight: 2 },
    mp: { low: 6, high: 14, tipLow: 'MP 4-bet too low.', tipHigh: 'MP 4-bet too high.', fix: 'Target 6-14% 4-bet from MP.', weight: 2 },
    co: { low: 5, high: 12, tipLow: 'CO 4-bet too low.', tipHigh: 'CO 4-bet too high.', fix: 'Target 5-12% 4-bet from CO.', weight: 2 },
    btn: { low: 5, high: 11, tipLow: 'BTN 4-bet too low.', tipHigh: 'BTN 4-bet too high.', fix: 'Target 5-11% 4-bet from BTN.', weight: 2 },
    sb: { low: 4, high: 10, tipLow: 'SB 4-bet too low.', tipHigh: 'SB 4-bet too high.', fix: 'Target 4-10% 4-bet from SB.', weight: 2 },
    bb: { low: 5, high: 12, tipLow: 'BB 4-bet too low.', tipHigh: 'BB 4-bet too high.', fix: 'BB 4-bets after 3-betting vs an open.', weight: 2 },
  },
  fold_to_4bet: {
    total: {
      low: 55, high: 65,
      tipLow: 'Defending too wide vs 4-bets. Only continue with strong hands.',
      tipHigh: 'Folding too much to 4-bets. Your 3-bet bluffs are getting exploited.',
      fix: 'Continue vs 4-bet with premiums + some suited combos with equity.',
      weight: 2,
      statFlagFilter: 'fold_to_4bet',
      oppFlagFilter: 'four_bet_opp',
    },
    ep: { low: 40, high: 55, tipLow: 'EP: defending too wide vs 4-bets.', tipHigh: 'EP: folding too much vs 4-bets.', fix: 'EP 3-bets tight, so defend more vs 4-bets.', weight: 2 },
    mp: { low: 45, high: 58, tipLow: 'MP: defending too wide vs 4-bets.', tipHigh: 'MP: folding too much vs 4-bets.', fix: 'Target 45-58% fold-to-4-bet from MP.', weight: 2 },
    co: { low: 50, high: 63, tipLow: 'CO: defending too wide vs 4-bets.', tipHigh: 'CO: folding too much vs 4-bets.', fix: 'Target 50-63% fold-to-4-bet from CO.', weight: 2 },
    btn: { low: 55, high: 68, tipLow: 'BTN: defending too wide vs 4-bets.', tipHigh: 'BTN: folding too much vs 4-bets.', fix: 'BTN 3-bets wider so folds more to 4-bets.', weight: 2 },
    sb: { low: 50, high: 65, tipLow: 'SB: defending too wide vs 4-bets.', tipHigh: 'SB: folding too much vs 4-bets.', fix: 'Target 50-65% fold-to-4-bet from SB.', weight: 2 },
    bb: { low: 45, high: 60, tipLow: 'BB: defending too wide vs 4-bets.', tipHigh: 'BB: folding too much vs 4-bets.', fix: 'Target 45-60% fold-to-4-bet from BB.', weight: 2 },
  },
  limp: {
    total: {
      low: 0, high: 5,
      tipLow: 'N/A',
      tipHigh: 'Limping too much. Open raise or fold instead.',
      fix: 'Eliminate open limps from EP-BTN. Raise or fold.',
      weight: 3,
      statFlagFilter: 'limp',
    },
    ep: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from EP is a major leak.', fix: 'Never limp from EP. Raise or fold.', weight: 3 },
    mp: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from MP is a major leak.', fix: 'Never limp from MP. Raise or fold.', weight: 3 },
    co: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from CO is a major leak.', fix: 'Never limp from CO. Raise or fold.', weight: 3 },
    btn: { low: 0, high: 3, tipLow: 'N/A', tipHigh: 'Limping from BTN is a major leak.', fix: 'Never limp from BTN. Raise or fold.', weight: 3 },
    sb: { low: 0, high: 100, tipLow: 'N/A', tipHigh: 'N/A', fix: 'SB limp (completing) is a valid strategy.', weight: 0 },
    bb: { low: 0, high: 100, tipLow: 'N/A', tipHigh: 'N/A', fix: 'BB cannot limp.', weight: 0 },
  },
  steal: {
    total: {
      low: 25, high: 40,
      tipLow: 'Not stealing blinds enough. Missing easy profit from late position.',
      tipHigh: 'Stealing too often. Opponents in the blinds will start defending more.',
      fix: 'Raise wider from CO/BTN/SB when folded to you. Blinds usually fold.',
      weight: 3,
      statFlagFilter: 'steal_attempted',
      oppFlagFilter: 'steal_opp',
    },
  },
  vs_steal_fold: {
    total: {
      low: 40, high: 55,
      tipLow: 'Defending blinds too much vs steals. Calling too wide OOP.',
      tipHigh: 'Folding too much in the blinds. Opponents can steal freely.',
      fix: 'Defend ~45-60% from BB vs BTN opens. Mix 3-bets with calls.',
      weight: 3,
      statFlagFilter: 'fold_to_steal',
      oppFlagFilter: 'faced_steal',
    },
  },
  cbet_flop: {
    total: {
      low: 50, high: 70,
      tipLow: 'Not c-betting the flop enough. Missing value and fold equity.',
      tipHigh: 'C-betting too much. Opponents will exploit with raises and floats.',
      fix: 'C-bet more on dry boards, check more on wet boards. Board texture matters.',
      weight: 4,
      statFlagFilter: 'cbet_flop',
      oppFlagFilter: 'cbet_flop_opp',
    },
  },
  cbet_turn: {
    total: {
      low: 50, high: 70,
      tipLow: 'Not following up on the turn. Giving up too often after c-betting flop.',
      tipHigh: 'Barrelling the turn too often. Be more selective with double barrels.',
      fix: 'Double barrel with strong draws, top pair+, and good bluff cards.',
      weight: 3,
      statFlagFilter: 'cbet_turn',
      oppFlagFilter: 'cbet_turn_opp',
    },
  },
  cbet_river: {
    total: {
      low: 50, high: 70,
      tipLow: 'Missing river value bets and bluffs.',
      tipHigh: 'Over-bluffing the river. Opponents are calling you down.',
      fix: 'River bets should be polarized: strong value hands or clear bluffs.',
      weight: 2,
      statFlagFilter: 'cbet_river',
      oppFlagFilter: 'cbet_river_opp',
    },
  },
  fold_to_cbet_flop: {
    total: {
      low: 40, high: 55,
      tipLow: 'Not folding enough to flop c-bets. Floating too wide.',
      tipHigh: 'Folding too much to flop c-bets. Opponents can c-bet any two cards.',
      fix: 'Defend with pairs, draws, and backdoor equity. Fold pure air.',
      weight: 3,
      statFlagFilter: 'fold_to_cbet_flop',
      oppFlagFilter: 'cbet_flop_opp',
    },
  },
  fold_to_cbet_turn: {
    total: {
      low: 40, high: 55,
      tipLow: 'Not folding enough to turn barrels. Calling too light.',
      tipHigh: 'Folding too much on the turn. Opponents barrel freely.',
      fix: 'Continue with strong draws and pairs. Fold weak one-pair hands.',
      weight: 2,
      statFlagFilter: 'fold_to_cbet_turn',
      oppFlagFilter: 'cbet_turn_opp',
    },
  },
  wtsd: {
    total: {
      low: 24, high: 30,
      tipLow: 'Folding too much postflop. Not going to showdown enough.',
      tipHigh: 'Going to showdown too often. Calling too many streets.',
      fix: 'Review river call decisions. Are you calling with losing hands?',
      weight: 3,
      statFlagFilter: 'went_to_showdown',
      oppFlagFilter: 'saw_flop',
    },
  },
  wsd: {
    total: {
      low: 50, high: 55,
      tipLow: 'Not winning enough at showdown. Taking bad hands to showdown.',
      tipHigh: 'Winning too much at showdown. Probably not bluffing enough.',
      fix: 'If WSD is low, tighten your calling range on later streets.',
      weight: 3,
      statFlagFilter: 'won_at_showdown',
      oppFlagFilter: 'went_to_showdown',
    },
  },
  wwsf: {
    total: {
      low: 42, high: 50,
      tipLow: 'Not winning enough after seeing the flop. Need more aggression.',
      tipHigh: 'Winning too much post-flop. Likely over-bluffing or running hot.',
      fix: 'Increase aggression with continuation bets and semi-bluffs.',
      weight: 3,
      statFlagFilter: 'saw_flop',
    },
  },
  af_flop: {
    total: {
      low: 2, high: 4,
      tipLow: 'Flop play too passive. Bet and raise more with strong hands and draws.',
      tipHigh: 'Hyper-aggressive on the flop. Opponents will trap and check-raise you.',
      fix: 'Target AF 2-4. Balance bets/raises with some checks and calls.',
      weight: 2,
    },
  },
  af_turn: {
    total: {
      low: 2, high: 4,
      tipLow: 'Turn play too passive. Follow through on your flop aggression.',
      tipHigh: 'Over-aggressive on the turn. Be more selective with second barrels.',
      fix: 'Target AF 2-4. Bet strong hands, check medium-strength holdings.',
      weight: 2,
    },
  },
  af_river: {
    total: {
      low: 2, high: 4,
      tipLow: 'River play too passive. Missing value bets and bluffs.',
      tipHigh: 'Over-bluffing the river. Polarize your betting range.',
      fix: 'Target AF 2-4. Bet big with nuts and air, check medium hands.',
      weight: 2,
    },
  },
};

// ── Villain Response Benchmarks ──────────────────────────────────────
// Population averages for how villains respond to hero's action, by position.
// Each entry: { [scenarioLabel]: percentage }
// Used as reference lines on the VillainResponseBar widget.

export interface VillainResponseBenchmark {
  [label: string]: number;
}

export const VILLAIN_RESPONSE_BENCHMARKS: Record<string, Record<string, VillainResponseBenchmark>> = {
  open_raise: {
    EP:  { 'Fold-through': 70, 'Called': 18, '3-Bet faced': 12 },
    MP:  { 'Fold-through': 65, 'Called': 23, '3-Bet faced': 12 },
    CO:  { 'Fold-through': 58, 'Called': 30, '3-Bet faced': 12 },
    BTN: { 'Fold-through': 52, 'Called': 33, '3-Bet faced': 15 },
    SB:  { 'Fold-through': 60, 'Called': 20, '3-Bet faced': 20 },
  },
};

// ── Health computation ───────────────────────────────────────────────

/**
 * Yellow zone = 30% of range width outside each boundary.
 * E.g. range [20, 28], width=8, margin=2.4 → yellow below 20 down to 17.6, yellow above 28 up to 30.4
 */
export function getStatHealth(
  value: number | null | undefined,
  benchmark: BenchmarkRange,
  sample: number,
  minSample = 100,
): StatHealth {
  if (value == null || sample < minSample) return { status: 'neutral' };

  const width = benchmark.high - benchmark.low;
  const margin = width * 0.3;

  if (value >= benchmark.low && value <= benchmark.high) {
    return { status: 'green' };
  }

  if (value < benchmark.low) {
    return value >= benchmark.low - margin
      ? { status: 'yellow', direction: 'low' }
      : { status: 'red', direction: 'low' };
  }

  // value > benchmark.high
  return value <= benchmark.high + margin
    ? { status: 'yellow', direction: 'high' }
    : { status: 'red', direction: 'high' };
}

export function getBenchmarkForPosition(
  statKey: string,
  position?: string,
): BenchmarkRange | undefined {
  const benchmarks = BENCHMARKS[statKey];
  if (!benchmarks) return undefined;

  if (position && position !== 'total') {
    const posKey = position.toLowerCase() as keyof PositionalBenchmarks;
    if (benchmarks[posKey]) return benchmarks[posKey];
  }

  return benchmarks.total;
}

// ── Leak computation ─────────────────────────────────────────────────

export interface Leak {
  statKey: string;
  displayName: string;
  value: number;
  sample: number;
  benchmark: BenchmarkRange;
  direction: 'low' | 'high';
  impact: number;
  handFilterUrl: string;
}

export interface OnTrackStat {
  statKey: string;
  displayName: string;
  value: number;
  low: number;
  high: number;
}

/** Extract the total StatValue for a stat key from HeroStats */
function getStatValue(stats: HeroStats, key: string): StatValue | undefined {
  const val = stats[key as keyof HeroStats];
  if (!val) return undefined;
  // PositionalStats have a .total property
  if (typeof val === 'object' && 'total' in val) {
    return (val as PositionalStats).total;
  }
  // StatValue directly
  if (typeof val === 'object' && 'sample' in val) {
    return val as StatValue;
  }
  return undefined;
}

export function computeLeaks(stats: HeroStats, minSample = 200): Leak[] {
  const leaks: Leak[] = [];

  for (const [key, posBenchmarks] of Object.entries(BENCHMARKS)) {
    const sv = getStatValue(stats, key);
    if (!sv || sv.value == null || sv.sample < minSample) continue;

    const benchmark = posBenchmarks.total;
    const health = getStatHealth(sv.value, benchmark, sv.sample, minSample);
    if (health.status !== 'red' || !health.direction) continue;

    const midpoint = (benchmark.low + benchmark.high) / 2;
    const impact = Math.abs(sv.value - midpoint) * benchmark.weight;

    // Build URL for hand browser filter
    const params = new URLSearchParams();
    if (benchmark.statFlagFilter) params.append('stat_flag', benchmark.statFlagFilter);
    if (benchmark.oppFlagFilter) params.append('stat_flag', benchmark.oppFlagFilter);
    const handFilterUrl = params.toString() ? `/hands?${params}` : '/hands';

    leaks.push({
      statKey: key,
      displayName: STAT_DISPLAY_NAMES[key] || key,
      value: sv.value,
      sample: sv.sample,
      benchmark,
      direction: health.direction,
      impact,
      handFilterUrl,
    });
  }

  leaks.sort((a, b) => b.impact - a.impact);
  return leaks.slice(0, 5);
}

export function computeOnTrack(stats: HeroStats, minSample = 200): OnTrackStat[] {
  const onTrack: OnTrackStat[] = [];

  for (const [key, posBenchmarks] of Object.entries(BENCHMARKS)) {
    const sv = getStatValue(stats, key);
    if (!sv || sv.value == null || sv.sample < minSample) continue;

    const benchmark = posBenchmarks.total;
    const health = getStatHealth(sv.value, benchmark, sv.sample, minSample);
    if (health.status !== 'green') continue;

    onTrack.push({
      statKey: key,
      displayName: STAT_DISPLAY_NAMES[key] || key,
      value: sv.value,
      low: benchmark.low,
      high: benchmark.high,
    });
  }

  return onTrack;
}
