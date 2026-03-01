/**
 * CompareTable — renders two HeroStats side-by-side with delta column.
 * Reuses fmtStat / benchmark coloring from StatDisplay.
 */
import type { HeroStats, StatValue, PositionalStats } from '@/lib/api';
import type { ColorClass } from '@/components/stats/StatDisplay';
import { BENCHMARKS, getStatHealth, getBenchmarkForPosition } from '@/lib/benchmarks';
import type { BenchmarkRange } from '@/lib/benchmarks';
import { Card, CardHeader } from '@/components/ui/card';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import {
  TooltipProvider,
} from '@/components/ui/tooltip';

// ── Row definition ───────────────────────────────────────────────────

interface StatRow {
  key: string;
  label: string;
  getValue: (stats: HeroStats) => StatValue;
  statKey?: string; // for benchmark lookup (defaults to key)
  isAF?: boolean;   // aggression factor uses different formatting
}

interface StatGroup {
  label: string;
  rows: StatRow[];
}

function sv(ps: PositionalStats): StatValue {
  return ps.total;
}

const COMPARE_GROUPS: StatGroup[] = [
  {
    label: 'Preflop',
    rows: [
      { key: 'vpip', label: 'VPIP', getValue: (s) => sv(s.vpip), statKey: 'vpip' },
      { key: 'pfr', label: 'PFR', getValue: (s) => sv(s.pfr), statKey: 'pfr' },
      { key: 'open_raise', label: 'Open Raise', getValue: (s) => sv(s.open_raise), statKey: 'open_raise' },
      { key: 'three_bet', label: '3-Bet', getValue: (s) => sv(s.three_bet), statKey: 'three_bet' },
      { key: 'fold_to_3bet', label: 'Fold to 3-Bet', getValue: (s) => sv(s.fold_to_3bet), statKey: 'fold_to_3bet' },
      { key: 'four_bet', label: '4-Bet', getValue: (s) => sv(s.four_bet), statKey: 'four_bet' },
      { key: 'fold_to_4bet', label: 'Fold to 4-Bet', getValue: (s) => sv(s.fold_to_4bet), statKey: 'fold_to_4bet' },
      { key: 'limp', label: 'Limp', getValue: (s) => sv(s.limp), statKey: 'limp' },
      { key: 'squeeze', label: 'Squeeze', getValue: (s) => s.squeeze },
      { key: 'steal', label: 'Steal', getValue: (s) => sv(s.steal), statKey: 'steal' },
    ],
  },
  {
    label: 'Postflop',
    rows: [
      { key: 'cbet_flop', label: 'C-Bet Flop', getValue: (s) => sv(s.cbet_flop), statKey: 'cbet_flop' },
      { key: 'cbet_turn', label: 'C-Bet Turn', getValue: (s) => sv(s.cbet_turn), statKey: 'cbet_turn' },
      { key: 'cbet_river', label: 'C-Bet River', getValue: (s) => sv(s.cbet_river), statKey: 'cbet_river' },
      { key: 'fold_to_cbet_flop', label: 'Fold to CBet Flop', getValue: (s) => sv(s.fold_to_cbet_flop), statKey: 'fold_to_cbet_flop' },
      { key: 'fold_to_cbet_turn', label: 'Fold to CBet Turn', getValue: (s) => sv(s.fold_to_cbet_turn), statKey: 'fold_to_cbet_turn' },
    ],
  },
  {
    label: 'Aggression',
    rows: [
      { key: 'af_flop', label: 'AF Flop', getValue: (s) => s.af_flop, statKey: 'af_flop', isAF: true },
      { key: 'af_turn', label: 'AF Turn', getValue: (s) => s.af_turn, statKey: 'af_turn', isAF: true },
      { key: 'af_river', label: 'AF River', getValue: (s) => s.af_river, statKey: 'af_river', isAF: true },
      { key: 'afq_flop', label: 'AFq Flop', getValue: (s) => s.afq_flop },
      { key: 'afq_turn', label: 'AFq Turn', getValue: (s) => s.afq_turn },
      { key: 'afq_river', label: 'AFq River', getValue: (s) => s.afq_river },
    ],
  },
  {
    label: 'Showdown',
    rows: [
      { key: 'wtsd', label: 'WTSD', getValue: (s) => s.wtsd, statKey: 'wtsd' },
      { key: 'wsd', label: 'W$SD', getValue: (s) => s.wsd, statKey: 'wsd' },
      { key: 'wwsf', label: 'WWSF', getValue: (s) => s.wwsf, statKey: 'wwsf' },
    ],
  },
];

// ── Helpers ──────────────────────────────────────────────────────────

function fmtPct(v: number | null, isAF?: boolean): string {
  if (v === null) return '\u2014';
  if (isAF) return v.toFixed(2);
  return `${v.toFixed(1)}%`;
}

function fmtDelta(a: number | null, b: number | null, isAF?: boolean): { text: string; value: number | null } {
  if (a === null || b === null) return { text: '\u2014', value: null };
  const d = b - a;
  const sign = d > 0 ? '+' : '';
  if (isAF) return { text: `${sign}${d.toFixed(2)}`, value: d };
  return { text: `${sign}${d.toFixed(1)}`, value: d };
}

function getDeltaColor(
  delta: number | null,
  benchmark: BenchmarkRange | undefined,
  bValue: number | null,
): ColorClass {
  if (delta === null || !benchmark || bValue === null) return 'text-text-muted';
  const healthB = getStatHealth(bValue, benchmark, 999);
  if (healthB.status === 'green') return 'text-green';
  if (healthB.status === 'red') return 'text-red';
  return 'text-yellow';
}

function getValueColor(
  v: number | null,
  statKey: string | undefined,
  sample: number,
): ColorClass {
  if (v === null || !statKey) return 'text-text';
  const benchmark = getBenchmarkForPosition(statKey);
  if (!benchmark) return 'text-text';
  const health = getStatHealth(v, benchmark, sample);
  if (health.status === 'green') return 'text-green';
  if (health.status === 'red') return 'text-red';
  if (health.status === 'yellow') return 'text-yellow';
  return 'text-text';
}

// ── Component ────────────────────────────────────────────────────────

interface CompareTableProps {
  statsA: HeroStats;
  statsB: HeroStats;
  labelA: string;
  labelB: string;
}

export default function CompareTable({ statsA, statsB, labelA, labelB }: CompareTableProps) {
  return (
    <TooltipProvider delayDuration={200}>
      <div className="space-y-3">
        {COMPARE_GROUPS.map((group) => (
          <Card key={group.label} className="overflow-hidden gap-0 py-0">
            <CardHeader className="px-3 py-1.5">
              <h2 className="text-[11px] font-bold uppercase tracking-wider text-primary">{group.label}</h2>
            </CardHeader>
            <div className="overflow-x-auto">
              <Table style={{ tableLayout: 'fixed', width: '100%' }}>
                <colgroup>
                  <col style={{ width: '22%' }} />
                  <col style={{ width: '15%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '15%' }} />
                  <col style={{ width: '9%' }} />
                  <col style={{ width: '12%' }} />
                  <col style={{ width: '18%' }} />
                </colgroup>
                <TableHeader>
                  <TableRow>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px]">Stat</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">{labelA}</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right text-text-muted">n</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">{labelB}</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right text-text-muted">n</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">Delta</TableHead>
                    <TableHead className="px-3 py-1.5 h-auto text-[11px] text-center">Range</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {group.rows.map((row) => {
                    const valA = row.getValue(statsA);
                    const valB = row.getValue(statsB);
                    const benchmark = row.statKey ? BENCHMARKS[row.statKey]?.total : undefined;
                    const delta = fmtDelta(valA.value, valB.value, row.isAF);
                    const deltaColor = getDeltaColor(delta.value, benchmark, valB.value);
                    const lowN = (valA.sample < 50 && valA.sample > 0) || (valB.sample < 50 && valB.sample > 0);
                    const colorA = getValueColor(valA.value, row.statKey, valA.sample);
                    const colorB = getValueColor(valB.value, row.statKey, valB.sample);

                    return (
                      <TableRow key={row.key} className="hover:bg-surface-hover">
                        <TableCell className="px-3 py-1.5 text-sm font-medium">
                          {row.label}
                        </TableCell>
                        <TableCell className={`px-3 py-1.5 text-right font-mono text-sm ${colorA}`}>
                          {fmtPct(valA.value, row.isAF)}
                        </TableCell>
                        <TableCell className="px-3 py-1.5 text-right font-mono text-xs text-text-muted">
                          {valA.sample > 0 ? valA.sample.toLocaleString() : '\u2014'}
                        </TableCell>
                        <TableCell className={`px-3 py-1.5 text-right font-mono text-sm ${colorB}`}>
                          {fmtPct(valB.value, row.isAF)}
                        </TableCell>
                        <TableCell className="px-3 py-1.5 text-right font-mono text-xs text-text-muted">
                          {valB.sample > 0 ? valB.sample.toLocaleString() : '\u2014'}
                        </TableCell>
                        <TableCell className={`px-3 py-1.5 text-right font-mono text-sm ${lowN ? 'text-text-muted' : deltaColor}`}>
                          {delta.text}
                        </TableCell>
                        <TableCell className="px-3 py-1.5 text-center text-xs text-text-muted">
                          {benchmark ? `${benchmark.low}\u2013${benchmark.high}` : '\u2014'}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
          </Card>
        ))}
      </div>
    </TooltipProvider>
  );
}
