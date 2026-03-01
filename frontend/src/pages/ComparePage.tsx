import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { useWorkspace } from '@/contexts/WorkspaceContext';
import type { Workspace } from '@/contexts/WorkspaceContext';
import { useFilterOptions } from '@/hooks/useFilterOptions';
import type { HeroStats } from '@/lib/api';
import { Card, CardContent } from '@/components/ui/card';
import { DatePicker } from '@/components/ui/date-picker';
import { Badge } from '@/components/ui/badge';
import { Alert, AlertDescription } from '@/components/ui/alert';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import CompareTable from '@/components/stats/CompareTable';
import { formatStakes } from '@/lib/utils';

const BASE = '/api';

type CompareMode = 'periods' | 'population' | 'workspace';

interface PeriodStats {
  date_from: string;
  date_to: string | null;
  hands: number;
  win_rate_bb100: number | null;
  win_rate_ev_bb100: number | null;
  stats: HeroStats;
  player_count?: number | null;
}

interface CompareResponse {
  period_a: PeriodStats;
  period_b: PeriodStats;
}

// ── API ──────────────────────────────────────────────────────────────

async function fetchCompare(params: {
  workspace_id: number;
  mode: CompareMode;
  period_a_from?: string;
  period_a_to?: string;
  period_b_from?: string;
  period_b_to?: string;
  workspace_id_b?: number;
  stakes?: string;
  game_mode?: string;
}): Promise<CompareResponse> {
  const sp = new URLSearchParams();
  sp.set('workspace_id', String(params.workspace_id));
  sp.set('mode', params.mode);
  if (params.period_a_from) sp.set('period_a_from', params.period_a_from);
  if (params.period_a_to) sp.set('period_a_to', params.period_a_to);
  if (params.period_b_from) sp.set('period_b_from', params.period_b_from);
  if (params.period_b_to) sp.set('period_b_to', params.period_b_to);
  if (params.workspace_id_b != null) sp.set('workspace_id_b', String(params.workspace_id_b));
  if (params.stakes) sp.set('stakes', params.stakes);
  if (params.game_mode) sp.set('game_mode', params.game_mode === '__reg__' ? '' : params.game_mode);
  const res = await fetch(`${BASE}/compare/stats?${sp}`);
  if (!res.ok) throw new Error('Compare failed');
  return res.json();
}

// ── Helpers ──────────────────────────────────────────────────────────

function formatCpDate(iso: string): string {
  const d = new Date(iso);
  const date = d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
  const hh = String(d.getHours()).padStart(2, '0');
  const mm = String(d.getMinutes()).padStart(2, '0');
  const time = `${hh}:${mm}`;
  return time !== '00:00' ? `${date} ${time}` : date;
}

// ── Main Component ───────────────────────────────────────────────────

export default function ComparePage() {
  const { activeWorkspaceId, activeWorkspace, workspaces, checkpoints } = useWorkspace();
  const { data: filterOpts } = useFilterOptions();

  // Mode
  const [mode, setMode] = useState<CompareMode>('periods');

  // Periods mode
  const [aFrom, setAFrom] = useState('');
  const [aTo, setATo] = useState('');
  const [bFrom, setBFrom] = useState('');
  const [bTo, setBTo] = useState('');

  // Workspace mode
  const [wsIdB, setWsIdB] = useState<number | null>(null);

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

  // Can we run the query?
  const canCompare = mode === 'periods'
    ? !!(aFrom || aTo)
    : mode === 'population'
      ? true
      : wsIdB != null;

  const queryParams = useMemo(() => {
    const base = {
      workspace_id: activeWorkspaceId,
      mode,
      stakes: stakes || undefined,
      game_mode: gameMode || undefined,
    };
    if (mode === 'periods') {
      return {
        ...base,
        period_a_from: aFrom || '2000-01-01',
        period_a_to: aTo || new Date().toISOString().slice(0, 10),
        period_b_from: bFrom || '2000-01-01',
        period_b_to: bTo || undefined,
      };
    }
    if (mode === 'workspace') {
      return { ...base, workspace_id_b: wsIdB ?? undefined };
    }
    // population
    return base;
  }, [activeWorkspaceId, mode, aFrom, aTo, bFrom, bTo, wsIdB, stakes, gameMode]);

  const { data, isPending } = useQuery({
    queryKey: ['compare', queryParams],
    queryFn: () => fetchCompare(queryParams as Parameters<typeof fetchCompare>[0]),
    enabled: canCompare,
  });

  const pa = data?.period_a;
  const pb = data?.period_b;

  const lowSample = pa && pb && (pa.hands < 10000 || pb.hands < 10000);

  // Labels for the compare table
  const labels = useMemo(() => {
    if (mode === 'periods') return { a: 'Period A', b: 'Period B' };
    if (mode === 'population') return { a: 'Hero', b: 'Population' };
    // workspace
    const nameA = activeWorkspace?.name || 'Workspace A';
    const wsB = workspaces.find((w) => w.id === wsIdB);
    const nameB = wsB?.name || 'Workspace B';
    return { a: nameA, b: nameB };
  }, [mode, activeWorkspace, workspaces, wsIdB]);

  return (
    <div className="max-w-5xl mx-auto space-y-3">
      {/* Mode selector */}
      <Card className="gap-0 py-0">
        <CardContent className="px-3 py-2 flex flex-wrap items-center gap-3">
          <ToggleGroup
            type="single"
            value={mode}
            onValueChange={(v) => { if (v) setMode(v as CompareMode); }}
            className="h-8"
          >
            <ToggleGroupItem value="periods" className="h-7 px-3 text-xs">Periods</ToggleGroupItem>
            <ToggleGroupItem value="population" className="h-7 px-3 text-xs">vs Population</ToggleGroupItem>
            <ToggleGroupItem value="workspace" className="h-7 px-3 text-xs">vs Workspace</ToggleGroupItem>
          </ToggleGroup>
          <div className="h-4 w-px bg-border" />
          {/* Shared filters */}
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

      {/* Mode-specific controls */}
      {mode === 'periods' && (
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
      )}

      {mode === 'population' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <SummaryCard
            label="Hero"
            variant="a"
            info={activeWorkspace ? `${activeWorkspace.hero_username} @ ${activeWorkspace.name}` : undefined}
            hands={pa?.hands}
            winRate={pa?.win_rate_bb100}
          />
          <SummaryCard
            label="Population"
            variant="b"
            info={pb?.player_count != null ? `${pb.player_count.toLocaleString()} players` : undefined}
            hands={pb?.hands}
            winRate={pb?.win_rate_bb100}
          />
        </div>
      )}

      {mode === 'workspace' && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <WorkspaceCard
            label="Workspace A"
            variant="a"
            workspace={activeWorkspace}
            summary={pa}
          />
          <Card className="gap-0 py-0 border-l-2 border-l-emerald-500">
            <CardContent className="p-3 space-y-3">
              <div className="flex items-center justify-between">
                <span className="text-sm font-semibold">Workspace B</span>
                {pb && (
                  <div className="flex items-center gap-2">
                    <Badge variant="outline" className="text-[10px] font-mono">
                      {pb.hands.toLocaleString()} hands
                    </Badge>
                    {pb.win_rate_bb100 !== null && (
                      <Badge
                        variant="outline"
                        className={`text-[10px] font-mono ${pb.win_rate_bb100 >= 0 ? 'text-green' : 'text-red'}`}
                      >
                        {pb.win_rate_bb100.toFixed(2)} bb/100
                      </Badge>
                    )}
                  </div>
                )}
              </div>
              <Select
                value={wsIdB != null ? String(wsIdB) : '__none__'}
                onValueChange={(v) => setWsIdB(v === '__none__' ? null : parseInt(v, 10))}
              >
                <SelectTrigger className="h-8 text-sm">
                  <SelectValue placeholder="Select workspace..." />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="__none__">Select workspace...</SelectItem>
                  {workspaces.map((ws) => (
                    <SelectItem key={ws.id} value={String(ws.id)}>
                      {ws.name} ({ws.hero_username})
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </CardContent>
          </Card>
        </div>
      )}

      {/* Sample size warning */}
      {lowSample && (
        <Alert>
          <AlertDescription className="text-xs">
            One or both sides have fewer than 10,000 hands. Results may not be statistically significant.
          </AlertDescription>
        </Alert>
      )}

      {/* Loading state */}
      {isPending && canCompare && (
        <Card className="gap-0 py-0">
          <CardContent className="p-6 text-center text-text-muted text-sm">
            Loading comparison...
          </CardContent>
        </Card>
      )}

      {/* Comparison table */}
      {pa && pb && (
        <CompareTable
          statsA={pa.stats}
          statsB={pb.stats}
          labelA={labels.a}
          labelB={labels.b}
        />
      )}

      {/* Empty state */}
      {!canCompare && (
        <Card className="gap-0 py-0">
          <CardContent className="p-8 text-center text-text-muted text-sm">
            {mode === 'periods' && (
              <>
                Select date ranges for both periods to compare your stats.
                {sortedCheckpoints.length > 0 && (
                  <span className="block mt-1">
                    Use checkpoints for quick before/after comparisons.
                  </span>
                )}
              </>
            )}
            {mode === 'workspace' && 'Select a workspace to compare against.'}
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

// ── Summary Card ─────────────────────────────────────────────────────

function SummaryCard({
  label,
  variant,
  info,
  hands,
  winRate,
}: {
  label: string;
  variant: 'a' | 'b';
  info?: string;
  hands?: number;
  winRate?: number | null;
}) {
  const borderColor = variant === 'a' ? 'border-l-blue-500' : 'border-l-emerald-500';

  return (
    <Card className={`gap-0 py-0 border-l-2 ${borderColor}`}>
      <CardContent className="p-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold">{label}</span>
            {info && <span className="text-xs text-text-muted ml-2">{info}</span>}
          </div>
          {hands != null && (
            <div className="flex items-center gap-2">
              <Badge variant="outline" className="text-[10px] font-mono">
                {hands.toLocaleString()} hands
              </Badge>
              {winRate !== null && winRate !== undefined && (
                <Badge
                  variant="outline"
                  className={`text-[10px] font-mono ${winRate >= 0 ? 'text-green' : 'text-red'}`}
                >
                  {winRate.toFixed(2)} bb/100
                </Badge>
              )}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

// ── Workspace Card ───────────────────────────────────────────────────

function WorkspaceCard({
  label,
  variant,
  workspace,
  summary,
}: {
  label: string;
  variant: 'a' | 'b';
  workspace: Workspace | null;
  summary?: PeriodStats;
}) {
  const borderColor = variant === 'a' ? 'border-l-blue-500' : 'border-l-emerald-500';

  return (
    <Card className={`gap-0 py-0 border-l-2 ${borderColor}`}>
      <CardContent className="p-3">
        <div className="flex items-center justify-between">
          <div>
            <span className="text-sm font-semibold">{label}</span>
            {workspace && (
              <span className="text-xs text-text-muted ml-2">
                {workspace.name} ({workspace.hero_username})
              </span>
            )}
          </div>
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
      </CardContent>
    </Card>
  );
}
