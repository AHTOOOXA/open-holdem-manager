import { STAT_DISPLAY_NAMES } from '@/lib/benchmarks';

export interface StatRegistryEntry {
  displayName: string;
  /** The field key on HeroStats (may be PositionalStats or StatValue) */
  heroStatsField: string;
  /** Whether this stat has positional breakdown in HeroStats */
  isPositional: boolean;
}

const REGISTRY: Record<string, StatRegistryEntry> = {
  // Preflop action
  vpip:              { displayName: 'VPIP',              heroStatsField: 'vpip',              isPositional: true  },
  pfr:               { displayName: 'PFR',               heroStatsField: 'pfr',               isPositional: true  },
  open_raise:        { displayName: 'Open Raise',        heroStatsField: 'open_raise',        isPositional: true  },
  call_open_raise:   { displayName: 'Call Open Raise',   heroStatsField: 'call_open_raise',   isPositional: true  },
  three_bet:         { displayName: '3-Bet',             heroStatsField: 'three_bet',         isPositional: true  },
  three_bet_ip:      { displayName: '3-Bet IP',          heroStatsField: 'three_bet_ip',      isPositional: true  },
  three_bet_oop:     { displayName: '3-Bet OOP',         heroStatsField: 'three_bet_oop',     isPositional: true  },
  four_bet:          { displayName: '4-Bet',             heroStatsField: 'four_bet',          isPositional: true  },
  five_bet:          { displayName: '5-Bet',             heroStatsField: 'five_bet',          isPositional: false },
  // Preflop defense
  fold_to_3bet:      { displayName: 'Fold to 3-Bet',    heroStatsField: 'fold_to_3bet',      isPositional: true  },
  fold_to_4bet:      { displayName: 'Fold to 4-Bet',    heroStatsField: 'fold_to_4bet',      isPositional: true  },
  limp:              { displayName: 'Limp',              heroStatsField: 'limp',              isPositional: true  },
  squeeze:           { displayName: 'Squeeze',           heroStatsField: 'squeeze',           isPositional: false },
  limp_fold:         { displayName: 'Limp-Fold',         heroStatsField: 'limp_fold',         isPositional: false },
  four_bet_fold:     { displayName: '4-Bet-Fold',        heroStatsField: 'four_bet_fold',     isPositional: false },
  call_4bet:         { displayName: 'Call 4-Bet',        heroStatsField: 'call_4bet',         isPositional: false },
  // New preflop stats
  bb_defense:        { displayName: 'BB Defense',        heroStatsField: 'bb_defense',        isPositional: false },
  iso_raise:         { displayName: 'Iso Raise',         heroStatsField: 'iso_raise',         isPositional: false },
  fold_to_squeeze:   { displayName: 'Fold to Squeeze',   heroStatsField: 'fold_to_squeeze',   isPositional: false },
  // Steal
  steal:             { displayName: 'Steal',             heroStatsField: 'steal',             isPositional: true  },
  fold_to_steal:     { displayName: 'Fold to Steal',     heroStatsField: 'vs_steal_fold',     isPositional: true  },
  call_steal:        { displayName: 'Call Steal',        heroStatsField: 'vs_steal_call',     isPositional: true  },
  three_bet_vs_steal:{ displayName: '3-Bet vs Steal',   heroStatsField: 'vs_steal_3bet',     isPositional: true  },
  four_bet_fold_steal: { displayName: '4-Bet-Fold (Steal)', heroStatsField: 'four_bet_fold_steal', isPositional: false },
  // Postflop action
  cbet_flop:         { displayName: 'C-Bet Flop',       heroStatsField: 'cbet_flop',         isPositional: true  },
  cbet_turn:         { displayName: 'C-Bet Turn',       heroStatsField: 'cbet_turn',         isPositional: true  },
  cbet_river:        { displayName: 'C-Bet River',      heroStatsField: 'cbet_river',        isPositional: true  },
  // Postflop defense
  fold_to_cbet_flop: { displayName: 'Fold to CBet Flop',heroStatsField: 'fold_to_cbet_flop', isPositional: true  },
  fold_to_cbet_turn: { displayName: 'Fold to CBet Turn',heroStatsField: 'fold_to_cbet_turn', isPositional: true  },
  fold_to_cbet_river:{ displayName: 'Fold to CBet River',heroStatsField:'fold_to_cbet_river', isPositional: true  },
  // vs C-Bet Flop (Raised Pot)
  fold_cbet_flop_raised:  { displayName: 'Fold to CBet (Raised Pot)',  heroStatsField: 'fold_cbet_flop_raised',  isPositional: false },
  call_cbet_flop_raised:  { displayName: 'Call CBet (Raised Pot)',     heroStatsField: 'call_cbet_flop_raised',  isPositional: false },
  raise_cbet_flop_raised: { displayName: 'Raise CBet (Raised Pot)',    heroStatsField: 'raise_cbet_flop_raised', isPositional: false },
  // vs C-Bet Flop (3-Bet Pot)
  fold_cbet_flop_3bet:    { displayName: 'Fold to CBet (3-Bet Pot)',   heroStatsField: 'fold_cbet_flop_3bet',    isPositional: false },
  call_cbet_flop_3bet:    { displayName: 'Call CBet (3-Bet Pot)',      heroStatsField: 'call_cbet_flop_3bet',    isPositional: false },
  raise_cbet_flop_3bet:   { displayName: 'Raise CBet (3-Bet Pot)',     heroStatsField: 'raise_cbet_flop_3bet',   isPositional: false },
  donk_bet_flop:     { displayName: 'Donk Bet Flop',    heroStatsField: 'donk_bet_flop',     isPositional: false },
  donk_bet_turn:     { displayName: 'Donk Bet Turn',    heroStatsField: 'donk_bet_turn',     isPositional: false },
  donk_bet_river:    { displayName: 'Donk Bet River',   heroStatsField: 'donk_bet_river',    isPositional: false },
  // Missed C-Bet
  missed_cbet_flop:  { displayName: 'Missed C-Bet Flop',heroStatsField: 'missed_cbet_flop',  isPositional: false },
  missed_cbet_flop_ip:  { displayName: 'Missed C-Bet IP', heroStatsField: 'missed_cbet_flop_ip', isPositional: false },
  missed_cbet_flop_oop: { displayName: 'Missed C-Bet OOP',heroStatsField: 'missed_cbet_flop_oop',isPositional: false },
  missed_cbet_fold_ip:  { displayName: 'Missed C-Bet → Fold IP', heroStatsField: 'missed_cbet_fold_ip', isPositional: false },
  missed_cbet_fold_oop: { displayName: 'Missed C-Bet → Fold OOP',heroStatsField: 'missed_cbet_fold_oop',isPositional: false },
  // vs Missed C-Bet
  vs_missed_cbet:              { displayName: 'vs Missed C-Bet',          heroStatsField: 'vs_missed_cbet',              isPositional: false },
  vs_missed_cbet_bet_ip:       { displayName: 'vs Missed C-Bet Bet IP',   heroStatsField: 'vs_missed_cbet_bet_ip',       isPositional: false },
  vs_missed_cbet_check_fold_ip:{ displayName: 'vs MC Check-Fold IP',      heroStatsField: 'vs_missed_cbet_check_fold_ip',isPositional: false },
  vs_missed_cbet_bet_oop_turn: { displayName: 'vs MC Bet OOP Turn',       heroStatsField: 'vs_missed_cbet_bet_oop_turn', isPositional: false },
  vs_missed_cbet_check_fold_oop:{ displayName: 'vs MC Check-Fold OOP',    heroStatsField: 'vs_missed_cbet_check_fold_oop',isPositional: false },
  // Aggression Factor
  af_flop:           { displayName: 'AF Flop',           heroStatsField: 'af_flop',           isPositional: false },
  af_turn:           { displayName: 'AF Turn',           heroStatsField: 'af_turn',           isPositional: false },
  af_river:          { displayName: 'AF River',          heroStatsField: 'af_river',          isPositional: false },
  // Aggression Frequency
  afq_flop:          { displayName: 'Agg Freq Flop',   heroStatsField: 'afq_flop',          isPositional: false },
  afq_turn:          { displayName: 'Agg Freq Turn',   heroStatsField: 'afq_turn',          isPositional: false },
  afq_river:         { displayName: 'Agg Freq River',  heroStatsField: 'afq_river',         isPositional: false },
  // Showdown
  saw_flop:          { displayName: 'Saw Flop',         heroStatsField: 'saw_flop',          isPositional: false },
  went_to_showdown:  { displayName: 'WTSD',             heroStatsField: 'wtsd',              isPositional: false },
  won_at_showdown:   { displayName: 'W$SD',             heroStatsField: 'wsd',               isPositional: false },
  wwsf:              { displayName: 'WWSF',             heroStatsField: 'wwsf',              isPositional: false },
};

// Merge display names from benchmarks.ts where available
for (const [key, entry] of Object.entries(REGISTRY)) {
  if (STAT_DISPLAY_NAMES[key]) {
    entry.displayName = STAT_DISPLAY_NAMES[key];
  }
}

/** Check if a stat key is drillable (has a detail view) */
export function isDrillable(statKey: string | undefined): boolean {
  return statKey != null && statKey in REGISTRY;
}

/** Get display name for a stat key */
export function getStatDisplayName(statKey: string): string {
  return REGISTRY[statKey]?.displayName ?? STAT_DISPLAY_NAMES[statKey] ?? statKey;
}

/** Get the full registry entry */
export function getStatEntry(statKey: string): StatRegistryEntry | undefined {
  return REGISTRY[statKey];
}

export { REGISTRY as STAT_REGISTRY };
