import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import type { HeroStats, StatValue, PositionalStats } from '@/lib/api';
import { BENCHMARKS, getStatHealth } from '@/lib/benchmarks';
import type { BenchmarkRange } from '@/lib/benchmarks';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { DatePicker } from '@/components/ui/date-picker';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { formatStakes } from '@/lib/utils';

const BASE = '/api';

interface PeriodStats {
  date_from: string;
  date_to: string | null;
  hands: number;
  win_rate_bb100: number | null;
  win_rate_ev_bb100: number | null;
  stats: HeroStats;
}

interface CompareResponse {
  period_a: PeriodStats;
  period_b: PeriodStats;
}

async function fetchCompare(params: {
  workspace_id: number;
  period_a_from: string;
  period_a_to: string;
  period_b_from: string;
  period_b_to?: string;
  stakes?: string;
  game_mode?: string;
}): Promise<CompareResponse> {
  const sp = new URLSearchParams();
  sp.set('workspace_id', String(params.workspace_id));
  sp.set('period_a_from', params.period_a_from);
  sp.set('period_a_to', params.period_a_to);
  sp.set('period_b_from', params.period_b_from);
  if (params.period_b_to) sp.set('period_b_to', params.period_b_to);
  if (params.stakes) sp.set('stakes', params.stakes);
  if (params.game_mode) sp.set('game_mode', params.game_mode);
  const res = await fetch(`${BASE}/compare/stats?${sp}`);
  if (!res.ok) throw new Error('Compare failed');
  return res.json();
}

// Stat row definition for the compare table
interface StatRow {
  key: string;
  label: string;
  getValue: (stats: HeroStats) => StatValue;
  benchmark?: BenchmarkRange;
}

interface StatGroup {
  label: string;
  rows: StatRow[];
}

function formatCpDate(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const time = `${hh}:${mm}`;
  return time !== '00:00' ? `${date} ${time}` : date;
}

function sv(ps: PositionalStats): StatValue {
  return ps.total;
}

const STAT_GROUPS: StatGroup[] = [
  {
    label: 'Preflop',
    rows: [
      { key: 'vpip', label: 'VPIP', getValue: (s) => sv(s.vpip) },
      { key: 'pfr', label: 'PFR', getValue: (s) => sv(s.pfr) },
      { key: 'open_raise', label: 'Open Raise', getValue: (s) => sv(s.open_raise) },
      { key: 'three_bet', label: '3-Bet', getValue: (s) => sv(s.three_bet) },
      { key: 'fold_to_3bet', label: 'Fold to 3-Bet', getValue: (s) => sv(s.fold_to_3bet) },
      { key: 'four_bet', label: '4-Bet', getValue: (s) => sv(s.four_bet) },
      { key: 'fold_to_4bet', label: 'Fold to 4-Bet', getValue: (s) => sv(s.fold_to_4bet) },
      { key: 'limp', label: 'Limp', getValue: (s) => sv(s.limp) },
      { key: 'squeeze', label: 'Squeeze', getValue: (s) => s.squeeze },
      { key: 'steal', label: 'Steal', getValue: (s) => sv(s.steal) },
    ],
  },
  {
    label: 'Postflop',
    rows: [
      { key: 'cbet_flop', label: 'C-Bet Flop', getValue: (s) => sv(s.cbet_flop) },
      { key: 'cbet_turn', label: 'C-Bet Turn', getValue: (s) => sv(s.cbet_turn) },
      { key: 'cbet_river', label: 'C-Bet River', getValue: (s) => sv(s.cbet_river) },
      { key: 'fold_to_cbet_flop', label: 'Fold to CBet Flop', getValue: (s) => sv(s.fold_to_cbet_flop) },
      { key: 'fold_to_cbet_turn', label: 'Fold to CBet Turn', getValue: (s) => sv(s.fold_to_cbet_turn) },
    ],
  },
  {
    label: 'Aggression',
    rows: [
      { key: 'af_flop', label: 'AF Flop', getValue: (s) => s.af_flop },
      { key: 'af_turn', label: 'AF Turn', getValue: (s) => s.af_turn },
      { key: 'af_river', label: 'AF River', getValue: (s) => s.af_river },
      { key: 'afq_flop', label: 'AFq Flop', getValue: (s) => s.afq_flop },
      { key: 'afq_turn', label: 'AFq Turn', getValue: (s) => s.afq_turn },
      { key: 'afq_river', label: 'AFq River', getValue: (s) => s.afq_river },
    ],
  },
  {
    label: 'Showdown',
    rows: [
      { key: 'wtsd', label: 'WTSD', getValue: (s) => s.wtsd },
      { key: 'wsd', label: 'W$SD', getValue: (s) => s.wsd },
      { key: 'wwsf', label: 'WWSF', getValue: (s) => s.wwsf },
    ],
  },
];

// Add benchmarks to rows
for (const group of STAT_GROUPS) {
  for (const row of group.rows) {
    const bm = BENCHMARKS[row.key];
    if (bm) row.benchmark = bm.total;
  }
}

function fmtPct(v: number | null): string {
  if (v === null) return '—';
  return `${v.toFixed(1)}%`;
}

function fmtDelta(a: number | null, b: number | null): { text: string; value: number | null } {
  if (a === null || b === null) return { text: '—', value: null };
  const d = b - a;
  const sign = d > 0 ? '+' : '';
  return { text: `${sign}${d.toFixed(1)}`, value: d };
}

function getDeltaColor(
  delta: number | null,
  benchmark: BenchmarkRange | undefined,
  bValue: number | null,
): string {
  if (delta === null || !benchmark || bValue === null) return 'text-text-muted';
  const healthB = getStatHealth(bValue, benchmark);
  if (healthB.status === 'green') return 'text-green';
  if (healthB.status === 'red') return 'text-red';
  return 'text-yellow';
}

export default function ComparePage() {
  const { activeWorkspaceId, checkpoints } = useWorkspace();
  const { data: filterOpts } = useFilterOptions();

  // Period A dates
  const [aFrom, setAFrom] = useState('');
  const [aTo, setATo] = useState('');
  // Period B dates
  const [bFrom, setBFrom] = useState('');
  const [bTo, setBTo] = useState('');
  // Shared filters
  const [stakes, setStakes] = useState('');
  const [gameMode, setGameMode] = useState('');

  // Checkpoint quick-select for periods
  const sortedCheckpoints = useMemo(
    () => [...checkpoints].sort((a, b) => a.checkpoint_at.localeCompare(b.checkpoint_at)),
    [checkpoints],
  );

  const handleQuickA = (value: string) => {
    const cp = sortedCheckpoints.find((c) => String(c.id) === value);
    if (cp) {
      setAFrom('');
      setATo(cp.checkpoint_at.slice(0, 19));
    }
  };

  const handleQuickB = (value: string) => {
    const cp = sortedCheckpoints.find((c) => String(c.id) === value);
    if (cp) {
      setBFrom(cp.checkpoint_at.slice(0, 19));
      setBTo('');
    }
  };

  const canCompare = aFrom || aTo;

  const { data, isPending } = useQuery({
    queryKey: ['compare', activeWorkspaceId, aFrom, aTo, bFrom, bTo, stakes, gameMode],
    queryFn: () =>
      fetchCompare({
        workspace_id: activeWorkspaceId,
        period_a_from: aFrom || '2000-01-01',
        period_a_to: aTo || new Date().toISOString().slice(0, 10),
        period_b_from: bFrom || '2000-01-01',
        period_b_to: bTo || undefined,
        stakes: stakes || undefined,
        game_mode: gameMode || undefined,
      }),
    enabled: !!canCompare,
  });

  const pa = data?.period_a;
  const pb = data?.period_b;

  const lowSample = pa && pb && (pa.hands < 10000 || pb.hands < 10000);

  return (
    <div className="max-w-5xl mx-auto space-y-3">
      {/* Shared filters */}
      <Card className="gap-0 py-0">
        <CardContent className="px-3 py-2 flex flex-wrap items-center gap-3">
          {filterOpts && filterOpts.stakes.length > 0 && (
            <Select
              value={stakes || '__all__'}
              onValueChange={(v) => setStakes(v === '__all__' ? '' : v)}
            >
              <SelectTrigger className="w-[130px] h-8 text-sm">
                <SelectValue placeholder="All Stakes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Stakes</SelectItem>
                {filterOpts.stakes.map((s) => (
                  <SelectItem key={s} value={s}>{formatStakes(s)}</SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
          {filterOpts && filterOpts.game_modes.length > 1 && (
            <Select
              value={gameMode || '__all__'}
              onValueChange={(v) => setGameMode(v === '__all__' ? '' : v)}
            >
              <SelectTrigger className="w-[130px] h-8 text-sm">
                <SelectValue placeholder="All Modes" />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="__all__">All Modes</SelectItem>
                {filterOpts.game_modes.map((m) => (
                  <SelectItem key={m || '__reg__'} value={m || '__reg__'}>
                    {m || 'Regular'}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          )}
        </CardContent>
      </Card>

      {/* Period selectors */}
      <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
        <PeriodCard
          label="Period A"
          variant="a"
          dateFrom={aFrom}
          dateTo={aTo}
          onDateFromChange={setAFrom}
          onDateToChange={setATo}
          checkpoints={sortedCheckpoints}
          onQuickSelect={handleQuickA}
          summary={pa}
        />
        <PeriodCard
          label="Period B"
          variant="b"
          dateFrom={bFrom}
          dateTo={bTo}
          onDateFromChange={setBFrom}
          onDateToChange={setBTo}
          checkpoints={sortedCheckpoints}
          onQuickSelect={handleQuickB}
          summary={pb}
        />
      </div>

      {/* Sample size warning */}
      {lowSample && (
        <Alert>
          <AlertDescription className="text-xs">
            One or both periods have fewer than 10,000 hands. Results may not be statistically significant.
          </AlertDescription>
        </Alert>
      )}

      {/* Compare table */}
      {isPending && canCompare && (
        <Card className="gap-0 py-0">
          <CardContent className="p-6 text-center text-text-muted text-sm">
            Loading comparison...
          </CardContent>
        </Card>
      )}

      {pa && pb && (
        <div className="space-y-3">
          {STAT_GROUPS.map((group) => (
            <Card key={group.label} className="overflow-hidden gap-0 py-0">
              <CardHeader className="px-3 py-1.5">
                <h2 className="text-xs font-semibold text-text">{group.label}</h2>
              </CardHeader>
              <div className="overflow-x-auto">
                <Table style={{ tableLayout: 'fixed', width: '100%' }}>
                  <colgroup>
                    <col style={{ width: '25%' }} />
                    <col style={{ width: '15%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '15%' }} />
                    <col style={{ width: '10%' }} />
                    <col style={{ width: '12%' }} />
                    <col style={{ width: '13%' }} />
                  </colgroup>
                  <TableHeader>
                    <TableRow>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px]">Stat</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">Period A</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right text-text-muted">n</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">Period B</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right text-text-muted">n</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-right">Delta</TableHead>
                      <TableHead className="px-3 py-1.5 h-auto text-[11px] text-center">Range</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {group.rows.map((row) => {
                      const valA = row.getValue(pa.stats);
                      const valB = row.getValue(pb.stats);
                      const delta = fmtDelta(valA.value, valB.value);
                      const deltaColor = getDeltaColor(delta.value, row.benchmark, valB.value);
                      const lowN = (valA.sample < 50 && valA.sample > 0) || (valB.sample < 50 && valB.sample > 0);

                      return (
                        <TableRow key={row.key} className="hover:bg-surface-hover">
                          <TableCell className="px-3 py-1.5 text-sm font-medium">
                            {row.label}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 text-right font-mono text-sm">
                            {fmtPct(valA.value)}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 text-right font-mono text-xs text-text-muted">
                            {valA.sample > 0 ? valA.sample.toLocaleString() : '—'}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 text-right font-mono text-sm">
                            {fmtPct(valB.value)}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 text-right font-mono text-xs text-text-muted">
                            {valB.sample > 0 ? valB.sample.toLocaleString() : '—'}
                          </TableCell>
                          <TableCell className={`px-3 py-1.5 text-right font-mono text-sm ${lowN ? 'text-text-muted' : deltaColor}`}>
                            {delta.text}
                          </TableCell>
                          <TableCell className="px-3 py-1.5 text-center text-xs text-text-muted">
                            {row.benchmark ? `${row.benchmark.low}–${row.benchmark.high}` : '—'}
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
      )}

      {!canCompare && (
        <Card className="gap-0 py-0">
          <CardContent className="p-8 text-center text-text-muted text-sm">
            Select date ranges for both periods to compare your stats.
            {sortedCheckpoints.length > 0 && (
              <span className="block mt-1">
                Use checkpoints for quick before/after comparisons.
              </span>
            )}
          </CardContent>
        </Card>
      )}
    </div>
  );
}

// ── Period Card ──────────────────────────────────────────────────────

interface PeriodCardProps {
  label: string;
  variant: 'a' | 'b';
  dateFrom: string;
  dateTo: string;
  onDateFromChange: (v: string) => void;
  onDateToChange: (v: string) => void;
  checkpoints: Array<{ id: number; name: string; checkpoint_at: string }>;
  onQuickSelect: (cpId: string) => void;
  summary?: PeriodStats;
}

function PeriodCard({
  label,
  variant,
  dateFrom,
  dateTo,
  onDateFromChange,
  onDateToChange,
  checkpoints,
  onQuickSelect,
  summary,
}: PeriodCardProps) {
  const borderColor = variant === 'a' ? 'border-l-blue-500' : 'border-l-emerald-500';

  return (
    <Card className={`gap-0 py-0 border-l-2 ${borderColor}`}>
      <CardContent className="p-3 space-y-3">
        <div className="flex items-center justify-between">
          <span className="text-sm font-semibold">{label}</span>
          {summary && (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] font-mono">
                {summary.hands.toLocaleString()} hands
              </Badge>
              {summary.win_rate_bb100 !== null && (
                <Badge
                  variant="outline"
                  className={`text-[10px] font-mono ${summary.win_rate_bb100 >= 0 ? 'text-green' : 'text-red'}`}
                >
                  {summary.win_rate_bb100.toFixed(2)} bb/100
                </Badge>
              )}
            </div>
          )}
        </div>

        {/* Quick select from checkpoints */}
        {checkpoints.length > 0 && (
          <Select onValueChange={onQuickSelect}>
            <SelectTrigger className="h-8 text-xs">
              <SelectValue placeholder={variant === 'a' ? 'Before checkpoint...' : 'After checkpoint...'} />
            </SelectTrigger>
            <SelectContent>
              {checkpoints.map((cp) => (
                <SelectItem key={cp.id} value={String(cp.id)}>
                  {cp.name}
                  <span className="text-muted-foreground ml-1.5 text-xs">
                    ({formatCpDate(cp.checkpoint_at)})
                  </span>
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        )}

        {/* Date pickers */}
        <div className="flex items-center gap-2">
          <DatePicker
            value={dateFrom}
            onChange={(v) => onDateFromChange(v)}
            placeholder="From"
            className="h-8 text-sm flex-1"
          />
          <span className="text-text-muted text-xs">to</span>
          <DatePicker
            value={dateTo}
            onChange={(v) => onDateToChange(v)}
            placeholder="To"
            className="h-8 text-sm flex-1"
          />
        </div>
      </CardContent>
    </Card>
  );
}
