import type { HeroStats, PositionalStats, StatValue, DriftResponse } from '@/lib/api';

/** Helper to create a PositionalStats with realistic positional variance */
function ps(total: number, ep: number, mp: number, co: number, btn: number, sb: number, bb: number, baseSample = 800): PositionalStats {
  const f = baseSample / 800;
  return {
    total: { value: total, sample: Math.round(baseSample * f) },
    ep: { value: ep, sample: Math.round(baseSample * 0.16 * f) },
    mp: { value: mp, sample: Math.round(baseSample * 0.16 * f) },
    co: { value: co, sample: Math.round(baseSample * 0.17 * f) },
    btn: { value: btn, sample: Math.round(baseSample * 0.17 * f) },
    sb: { value: sb, sample: Math.round(baseSample * 0.17 * f) },
    bb: { value: bb, sample: Math.round(baseSample * 0.17 * f) },
  };
}

function sv(value: number | null, sample: number = 800): StatValue {
  return { value, sample };
}

export const mockHeroStats: HeroStats = {
  hands: 800,
  win_rate_bb100: 4.82,
  win_rate_ev_bb100: 5.13,

  // Pre-flop
  vpip:            ps(24.5, 15.2, 18.8, 26.4, 32.1, 30.5, 22.8),
  pfr:             ps(19.8, 13.1, 16.2, 22.8, 28.4, 20.1, 12.5),
  open_raise:      ps(18.2, 12.5, 15.8, 22.1, 27.6, 19.3, 0),
  three_bet:       ps(8.2,  5.1,  6.8,  8.5,  9.2,  10.8, 9.5),
  three_bet_ip:    ps(9.1,  0,    7.2,  9.8,  10.1, 0,    0),
  three_bet_oop:   ps(7.4,  5.1,  6.5,  0,    0,    10.8, 9.5),
  four_bet:        ps(3.8,  2.5,  3.1,  4.2,  4.8,  3.5,  3.2),
  five_bet:        sv(1.2, 45),
  fold_to_3bet:    ps(55.2, 62.1, 58.4, 52.3, 48.1, 55.8, 58.2),
  fold_to_4bet:    ps(60.5, 65.2, 62.8, 58.1, 55.4, 62.3, 64.1),
  call_open_raise: ps(8.5,  5.2,  6.8,  9.1,  10.2, 12.5, 14.8),
  limp:            ps(1.2,  0,    0,    0,    0,    2.1,  4.5),
  limp_fold:       sv(65.0, 35),
  squeeze:         sv(6.5, 120),
  four_bet_range:  sv(3.8, 180),
  four_bet_fold:   sv(42.1, 80),
  call_4bet:       sv(38.5, 80),
  bb_defense:      sv(52.3, 136),
  iso_raise:       sv(8.2, 95),
  fold_to_squeeze: sv(58.4, 65),

  // Steal
  steal:               ps(32.5, 0, 0, 28.4, 38.2, 35.1, 0, 340),
  fold_to_3bet_steal:  ps(52.8, 0, 0, 0, 48.5, 55.2, 0, 180),
  four_bet_steal:      ps(5.2, 0, 0, 0, 6.1, 4.5, 0, 180),
  four_bet_fold_steal: ps(38.5, 0, 0, 0, 35.2, 42.1, 0, 45),
  vs_steal_fold:       ps(62.1, 0, 0, 0, 0, 65.8, 58.4, 280),
  vs_steal_call:       ps(22.5, 0, 0, 0, 0, 18.2, 26.8, 280),
  vs_steal_3bet:       ps(15.4, 0, 0, 0, 0, 16.0, 14.8, 280),

  // Postflop
  cbet_flop:            ps(62.5, 55.2, 58.4, 65.1, 68.2, 60.5, 58.8, 450),
  cbet_turn:            ps(55.8, 48.2, 52.1, 58.4, 62.5, 52.8, 50.1, 280),
  cbet_river:           ps(48.2, 42.1, 45.5, 50.8, 52.4, 44.2, 42.8, 180),
  fold_to_cbet_flop:    ps(42.5, 45.2, 43.8, 40.1, 38.5, 44.2, 45.8, 350),
  fold_to_cbet_turn:    ps(38.2, 40.5, 39.1, 36.8, 35.2, 40.1, 41.5, 220),
  fold_to_cbet_river:   ps(35.1, 38.2, 36.5, 33.8, 32.1, 36.8, 38.2, 140),
  donk_bet_flop:        sv(5.2, 180),
  donk_bet_turn:        sv(4.8, 120),
  donk_bet_river:       sv(3.5, 85),

  fold_cbet_flop_raised:   sv(42.5, 200),
  call_cbet_flop_raised:   sv(48.2, 200),
  raise_cbet_flop_raised:  sv(9.3, 200),
  fold_cbet_flop_3bet:     sv(38.1, 85),
  call_cbet_flop_3bet:     sv(52.4, 85),
  raise_cbet_flop_3bet:    sv(9.5, 85),

  af_flop:  sv(2.8, 450),
  af_turn:  sv(2.2, 280),
  af_river: sv(1.8, 180),
  afq_flop:  sv(48.5, 450),
  afq_turn:  sv(42.1, 280),
  afq_river: sv(35.8, 180),

  missed_cbet_flop:            sv(37.5, 450),
  missed_cbet_flop_ip:         sv(32.1, 250),
  missed_cbet_flop_oop:        sv(42.8, 200),
  missed_cbet_fold_ip:         sv(28.5, 80),
  missed_cbet_fold_oop:        sv(35.2, 85),
  missed_cbet_turn:            sv(45.2, 120),
  vs_missed_cbet:              sv(52.8, 130),
  vs_missed_cbet_bet_ip:       sv(58.4, 65),
  vs_missed_cbet_check_fold_ip: sv(22.1, 65),
  vs_missed_cbet_bet_oop_turn: sv(42.5, 65),
  vs_missed_cbet_check_fold_oop: sv(38.2, 65),

  // Showdown
  wtsd: sv(28.5, 450),
  wsd:  sv(52.8, 128),
  wwsf: sv(48.2, 450),
};

export const mockDriftResponse: DriftResponse = {
  stats: [],
  window_hands: 0,
  total_hands: 800,
};
