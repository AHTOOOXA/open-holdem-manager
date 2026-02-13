import type {
  GraphPoint,
  GraphResponse,
  SessionMarker,
  VarianceStats,
  FilterOptions,
  ResultsBreakdown,
} from '@/lib/api';

// Seeded pseudo-random number generator (mulberry32)
function seededRng(seed: number) {
  return () => {
    seed |= 0;
    seed = (seed + 0x6d2b79f5) | 0;
    let t = Math.imul(seed ^ (seed >>> 15), 1 | seed);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function generateGraphPoints(count: number): GraphPoint[] {
  const rng = seededRng(42);
  const points: GraphPoint[] = [];

  let cumBB = 0;
  let cumEvBB = 0;
  let cumRakeBB = 0;
  let cumJackpotBB = 0;
  let cumShowdownBB = 0;
  let cumNonshowdownBB = 0;

  const bbAmount = 0.10; // NL10 for USD conversion
  const startDate = new Date('2025-06-01T10:00:00Z');

  for (let i = 1; i <= count; i++) {
    // Random walk with slight positive drift (winning player ~5bb/100)
    const handResult = (rng() - 0.475) * 4; // slight positive bias
    const evResult = handResult + (rng() - 0.5) * 1.5; // EV diverges slightly
    const rake = 0.03 + rng() * 0.04; // ~3-7 bb rake per hand
    const jackpot = rng() < 0.3 ? 0.01 : 0; // occasional jackpot

    // ~60% of hands see flop, of those ~40% go to showdown
    const isShowdown = rng() < 0.25;
    const sdResult = isShowdown ? handResult * 0.7 : 0;
    const nsdResult = handResult - sdResult;

    cumBB += handResult;
    cumEvBB += evResult;
    cumRakeBB += rake;
    cumJackpotBB += jackpot;
    cumShowdownBB += sdResult;
    cumNonshowdownBB += nsdResult;

    // Advance time: ~1 minute per hand on average (rush & cash is fast)
    const playedAt = new Date(startDate.getTime() + i * 55000 + rng() * 20000);

    points.push({
      hand_number: i,
      played_at: playedAt.toISOString(),
      cumulative_bb: Math.round(cumBB * 100) / 100,
      cumulative_ev_bb: Math.round(cumEvBB * 100) / 100,
      cumulative_rake_bb: Math.round(cumRakeBB * 100) / 100,
      cumulative_jackpot_bb: Math.round(cumJackpotBB * 100) / 100,
      cumulative_showdown_bb: Math.round(cumShowdownBB * 100) / 100,
      cumulative_nonshowdown_bb: Math.round(cumNonshowdownBB * 100) / 100,
      cumulative_usd: Math.round(cumBB * bbAmount * 100) / 100,
      cumulative_ev_usd: Math.round(cumEvBB * bbAmount * 100) / 100,
      cumulative_rake_usd: Math.round(cumRakeBB * bbAmount * 100) / 100,
      cumulative_jackpot_usd: Math.round(cumJackpotBB * bbAmount * 100) / 100,
      cumulative_showdown_usd: Math.round(cumShowdownBB * bbAmount * 100) / 100,
      cumulative_nonshowdown_usd: Math.round(cumNonshowdownBB * bbAmount * 100) / 100,
    });
  }

  return points;
}

function generateSessions(points: GraphPoint[]): SessionMarker[] {
  const sessions: SessionMarker[] = [];
  // Sessions of 100-400 hands each
  let cursor = 0;
  const rng = seededRng(99);

  while (cursor < points.length) {
    const sessionLen = Math.floor(100 + rng() * 300);
    const end = Math.min(cursor + sessionLen - 1, points.length - 1);

    sessions.push({
      start_hand: points[cursor].hand_number,
      end_hand: points[end].hand_number,
      start_time: points[cursor].played_at,
      end_time: points[end].played_at,
    });

    cursor = end + 1;
  }

  return sessions;
}

const POINTS = generateGraphPoints(800);
const SESSIONS = generateSessions(POINTS);

const lastPoint = POINTS[POINTS.length - 1];
const n = POINTS.length;
const winrateBB100 = (lastPoint.cumulative_bb / n) * 100;

export const mockVariance: VarianceStats = {
  sd_bb: 85.2,
  sd_bb100: 85.2,
  winrate_bb100: Math.round(winrateBB100 * 100) / 100,
  ci_lower_bb100: Math.round((winrateBB100 - 1.96 * 85.2 / Math.sqrt(n) * 10) * 100) / 100,
  ci_upper_bb100: Math.round((winrateBB100 + 1.96 * 85.2 / Math.sqrt(n) * 10) * 100) / 100,
  n,
};

export const mockGraphResponse: GraphResponse = {
  points: POINTS,
  sessions: SESSIONS,
  variance: mockVariance,
};

export const mockFilterOptions: FilterOptions = {
  stakes: ['$0.05/$0.10', '$0.10/$0.25', '$0.25/$0.50'],
  game_modes: ['', 'Rush & Cash'],
  date_range: {
    min: POINTS[0].played_at.slice(0, 10),
    max: POINTS[POINTS.length - 1].played_at.slice(0, 10),
  },
};

export const mockBreakdown: ResultsBreakdown = {
  by_stakes: [
    {
      stakes: '$0.05/$0.10', game_mode: '', bb_amount: 0.10, hands: 520,
      won_bb: lastPoint.cumulative_bb * 0.65, won_usd: lastPoint.cumulative_usd * 0.65,
      ev_bb: lastPoint.cumulative_ev_bb * 0.65, rake_bb: lastPoint.cumulative_rake_bb * 0.65,
      rake_usd: lastPoint.cumulative_rake_usd * 0.65, jackpot_bb: lastPoint.cumulative_jackpot_bb * 0.65,
      jackpot_usd: lastPoint.cumulative_jackpot_usd * 0.65,
      bb_per_100: 4.82, ev_bb_per_100: 5.13,
    },
    {
      stakes: '$0.10/$0.25', game_mode: '', bb_amount: 0.25, hands: 280,
      won_bb: lastPoint.cumulative_bb * 0.35, won_usd: lastPoint.cumulative_usd * 0.35,
      ev_bb: lastPoint.cumulative_ev_bb * 0.35, rake_bb: lastPoint.cumulative_rake_bb * 0.35,
      rake_usd: lastPoint.cumulative_rake_usd * 0.35, jackpot_bb: lastPoint.cumulative_jackpot_bb * 0.35,
      jackpot_usd: lastPoint.cumulative_jackpot_usd * 0.35,
      bb_per_100: 3.21, ev_bb_per_100: 4.55,
    },
  ],
  by_month: [
    {
      month: '2025-06', hands: 450,
      won_bb: lastPoint.cumulative_bb * 0.55, won_usd: lastPoint.cumulative_usd * 0.55,
      ev_bb: lastPoint.cumulative_ev_bb * 0.55, rake_bb: lastPoint.cumulative_rake_bb * 0.55,
      rake_usd: lastPoint.cumulative_rake_usd * 0.55, jackpot_bb: lastPoint.cumulative_jackpot_bb * 0.55,
      jackpot_usd: lastPoint.cumulative_jackpot_usd * 0.55,
      bb_per_100: 5.12, ev_bb_per_100: 4.88,
    },
    {
      month: '2025-07', hands: 350,
      won_bb: lastPoint.cumulative_bb * 0.45, won_usd: lastPoint.cumulative_usd * 0.45,
      ev_bb: lastPoint.cumulative_ev_bb * 0.45, rake_bb: lastPoint.cumulative_rake_bb * 0.45,
      rake_usd: lastPoint.cumulative_rake_usd * 0.45, jackpot_bb: lastPoint.cumulative_jackpot_bb * 0.45,
      jackpot_usd: lastPoint.cumulative_jackpot_usd * 0.45,
      bb_per_100: 3.67, ev_bb_per_100: 5.01,
    },
  ],
  by_position: [
    { position: 'BTN', hands: 140, won_bb: 42.3, won_usd: 4.23, ev_bb: 38.1, rake_bb: 5.2, rake_usd: 0.52, jackpot_bb: 0.4, jackpot_usd: 0.04, bb_per_100: 30.21, ev_bb_per_100: 27.21 },
    { position: 'CO', hands: 135, won_bb: 18.6, won_usd: 1.86, ev_bb: 22.4, rake_bb: 4.8, rake_usd: 0.48, jackpot_bb: 0.3, jackpot_usd: 0.03, bb_per_100: 13.78, ev_bb_per_100: 16.59 },
    { position: 'MP', hands: 130, won_bb: -5.2, won_usd: -0.52, ev_bb: -2.1, rake_bb: 3.1, rake_usd: 0.31, jackpot_bb: 0.2, jackpot_usd: 0.02, bb_per_100: -4.0, ev_bb_per_100: -1.62 },
    { position: 'EP', hands: 125, won_bb: -12.8, won_usd: -1.28, ev_bb: -8.5, rake_bb: 2.4, rake_usd: 0.24, jackpot_bb: 0.2, jackpot_usd: 0.02, bb_per_100: -10.24, ev_bb_per_100: -6.8 },
    { position: 'SB', hands: 135, won_bb: -22.1, won_usd: -2.21, ev_bb: -18.3, rake_bb: 4.9, rake_usd: 0.49, jackpot_bb: 0.3, jackpot_usd: 0.03, bb_per_100: -16.37, ev_bb_per_100: -13.56 },
    { position: 'BB', hands: 135, won_bb: -15.4, won_usd: -1.54, ev_bb: -12.7, rake_bb: 5.1, rake_usd: 0.51, jackpot_bb: 0.3, jackpot_usd: 0.03, bb_per_100: -11.41, ev_bb_per_100: -9.41 },
  ],
};
