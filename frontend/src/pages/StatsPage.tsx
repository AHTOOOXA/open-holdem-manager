import { useState, useEffect } from 'react';
import { getHeroStats } from '@/lib/api';
import type { HeroStats, PositionalStats, StatValue } from '@/lib/api';

const POSITIONS = ['total', 'ep', 'mp', 'co', 'btn', 'sb', 'bb'] as const;
const POS_LABELS = ['Total', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];

function fmt(sv: StatValue | undefined): string {
  if (!sv || sv.value === null || sv.value === undefined) return '-';
  return sv.value.toFixed(1);
}

function sampleStr(sv: StatValue | undefined): string {
  if (!sv) return '';
  return `(${sv.sample})`;
}

function StatRow({
  label,
  stats,
  positional,
}: {
  label: string;
  stats?: PositionalStats;
  positional?: boolean;
}) {
  if (!stats) return null;
  const cells = positional !== false
    ? POSITIONS.map((pos) => stats[pos])
    : [stats.total];

  return (
    <tr className="border-b border-border/50 hover:bg-surface-hover">
      <td className="py-1.5 px-3 text-sm font-medium text-text-muted whitespace-nowrap">
        {label}
      </td>
      {cells.map((sv, i) => (
        <td
          key={i}
          className="py-1.5 px-3 text-sm text-center font-mono"
          title={sampleStr(sv)}
        >
          <span className={getColor(label, sv?.value)}>
            {fmt(sv)}
          </span>
        </td>
      ))}
      {/* Pad remaining cells if not positional */}
      {positional === false &&
        Array.from({ length: 6 }).map((_, i) => (
          <td key={`pad-${i}`} className="py-1.5 px-3"></td>
        ))}
    </tr>
  );
}

function SimpleStatRow({
  label,
  sv,
}: {
  label: string;
  sv?: StatValue;
}) {
  return (
    <tr className="border-b border-border/50 hover:bg-surface-hover">
      <td className="py-1.5 px-3 text-sm font-medium text-text-muted whitespace-nowrap">
        {label}
      </td>
      <td className="py-1.5 px-3 text-sm text-center font-mono" title={sampleStr(sv)}>
        <span className={getColor(label, sv?.value)}>{fmt(sv)}</span>
      </td>
      {Array.from({ length: 6 }).map((_, i) => (
        <td key={i} className="py-1.5 px-3"></td>
      ))}
    </tr>
  );
}

function SectionHeader({ title }: { title: string }) {
  return (
    <tr>
      <td
        colSpan={8}
        className="py-2 px-3 text-xs font-bold uppercase tracking-wider text-primary bg-surface"
      >
        {title}
      </td>
    </tr>
  );
}

function getColor(label: string, value: number | null | undefined): string {
  if (value === null || value === undefined) return 'text-text-muted';

  // Some heuristic coloring
  const l = label.toLowerCase();
  if (l.includes('fold') && value > 70) return 'text-red';
  if (l.includes('fold') && value < 40) return 'text-green';
  if (l === 'vpip' && value > 30) return 'text-yellow';
  if (l === 'vpip' && value >= 20 && value <= 28) return 'text-green';
  if (l === 'pfr' && value >= 16 && value <= 24) return 'text-green';

  return 'text-text';
}

export default function StatsPage() {
  const [stats, setStats] = useState<HeroStats | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    getHeroStats()
      .then(setStats)
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-text-muted">Loading stats...</p>;
  if (!stats || stats.hands === 0) {
    return (
      <div className="text-center py-12">
        <p className="text-text-muted text-lg">No hands imported yet.</p>
        <p className="text-text-muted text-sm mt-2">Upload hand histories first.</p>
      </div>
    );
  }

  return (
    <div className="max-w-5xl mx-auto">
      <div className="flex items-center justify-between mb-4">
        <h1 className="text-2xl font-bold">Player Stats</h1>
        <div className="text-sm text-text-muted">
          {stats.hands.toLocaleString()} hands |{' '}
          <span
            className={
              (stats.win_rate_bb100 ?? 0) >= 0 ? 'text-green font-bold' : 'text-red font-bold'
            }
          >
            {stats.win_rate_bb100?.toFixed(2) ?? '-'} bb/100
          </span>
        </div>
      </div>

      <div className="bg-surface rounded-lg border border-border overflow-x-auto">
        <table className="w-full">
          <thead>
            <tr className="border-b border-border">
              <th className="py-2 px-3 text-left text-xs font-medium text-text-muted uppercase w-40">
                Stat
              </th>
              {POS_LABELS.map((p) => (
                <th
                  key={p}
                  className="py-2 px-3 text-center text-xs font-medium text-text-muted uppercase"
                >
                  {p}
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            <SectionHeader title="Pre-Flop" />
            <StatRow label="VPIP" stats={stats.vpip} />
            <StatRow label="PFR" stats={stats.pfr} />
            <StatRow label="Open Raise" stats={stats.open_raise} />
            <StatRow label="3-Bet" stats={stats.three_bet} />
            <SimpleStatRow label="3-Bet IP" sv={stats.three_bet_ip} />
            <SimpleStatRow label="3-Bet OOP" sv={stats.three_bet_oop} />
            <StatRow label="4-Bet" stats={stats.four_bet} />
            <SimpleStatRow label="5-Bet" sv={stats.five_bet} />
            <StatRow label="Fold to 3-Bet" stats={stats.fold_to_3bet} />
            <StatRow label="Fold to 4-Bet" stats={stats.fold_to_4bet} />
            <StatRow label="Call Open Raise" stats={stats.call_open_raise} />
            <StatRow label="Limp" stats={stats.limp} />
            <SimpleStatRow label="Squeeze" sv={stats.squeeze} />

            <SectionHeader title="Steal" />
            <StatRow label="Steal" stats={stats.steal} />
            <SimpleStatRow label="Fold to 3Bet (steal)" sv={stats.fold_to_3bet_steal} />
            <SimpleStatRow label="4-Bet (steal)" sv={stats.four_bet_steal} />
            <SimpleStatRow label="vs Steal: Fold" sv={stats.vs_steal_fold} />
            <SimpleStatRow label="vs Steal: Call" sv={stats.vs_steal_call} />
            <SimpleStatRow label="vs Steal: 3-Bet" sv={stats.vs_steal_3bet} />

            <SectionHeader title="Post-Flop" />
            <StatRow label="CBet Flop" stats={stats.cbet_flop} />
            <StatRow label="CBet Turn" stats={stats.cbet_turn} />
            <StatRow label="CBet River" stats={stats.cbet_river} />
            <StatRow label="Fold to CBet Flop" stats={stats.fold_to_cbet_flop} />
            <StatRow label="Fold to CBet Turn" stats={stats.fold_to_cbet_turn} />
            <StatRow label="Fold to CBet River" stats={stats.fold_to_cbet_river} />
            <SimpleStatRow label="Donk Bet Flop" sv={stats.donk_bet_flop} />
            <SimpleStatRow label="Missed CBet Flop" sv={stats.missed_cbet_flop} />
            <SimpleStatRow label="Missed CBet Turn" sv={stats.missed_cbet_turn} />

            <SectionHeader title="Aggression" />
            <SimpleStatRow label="AF Flop" sv={stats.af_flop} />
            <SimpleStatRow label="AF Turn" sv={stats.af_turn} />
            <SimpleStatRow label="AF River" sv={stats.af_river} />
            <SimpleStatRow label="AFq Flop" sv={stats.afq_flop} />
            <SimpleStatRow label="AFq Turn" sv={stats.afq_turn} />
            <SimpleStatRow label="AFq River" sv={stats.afq_river} />

            <SectionHeader title="Showdown" />
            <SimpleStatRow label="WTSD%" sv={stats.wtsd} />
            <SimpleStatRow label="W$SD%" sv={stats.wsd} />
            <SimpleStatRow label="WWSF%" sv={stats.wwsf} />
          </tbody>
        </table>
      </div>
    </div>
  );
}
