import { useState, useMemo } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useQuery } from '@tanstack/react-query';
import {
  ComposedChart,
  Area,
  Line,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from 'recharts';
import {
  getSessions,
  getSessionDetail,
  getHands,
} from '@/lib/api';
import type {
  SessionDetailResponse,
  SessionGraphPoint,
  SessionBigHand,
} from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { formatStakes, formatRelativeDate } from '@/lib/utils';
import EmptyState from '@/components/EmptyState';
import { CardBoxPair, CardBoxRow, CardBox } from '@/components/hands/CardDisplay';
import Actions from '@/components/hands/Actions';
import Pagination from '@/components/hands/Pagination';
import HandDrawer from '@/components/hands/HandDrawer';
import { Card, CardContent, CardHeader } from '@/components/ui/card';
import { Badge } from '@/components/ui/badge';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import { Skeleton } from '@/components/ui/skeleton';
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from '@/components/ui/table';
import { queryClient } from '@/lib/query-client';

// ── Helpers ──────────────────────────────────────────────────────────

function formatSessionDate(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleDateString('en-US', {
    weekday: 'short',
    month: 'short',
    day: 'numeric',
    year: 'numeric',
  });
}

function formatTime(iso: string): string {
  if (!iso) return '';
  const d = new Date(iso);
  return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false });
}

function formatDuration(mins: number): string {
  if (mins < 60) return `${Math.round(mins)}m`;
  const h = Math.floor(mins / 60);
  const m = Math.round(mins % 60);
  return m > 0 ? `${h}h ${m}m` : `${h}h`;
}

const clr = (v: number) => v >= 0 ? 'text-green' : 'text-red';
const fmtUSD = (v: number) => `${v >= 0 ? '' : '-'}$${Math.abs(v).toFixed(2)}`;
const fmtBB = (v: number) => `${v.toFixed(1)} BB`;

function colorVal(v: number): string {
  if (v > 0) return 'text-green';
  if (v < 0) return 'text-red';
  return 'text-text-muted';
}

// ── Main Component ───────────────────────────────────────────────────

export default function SessionsPage() {
  const { sessionIndex } = useParams<{ sessionIndex?: string }>();

  if (sessionIndex !== undefined) {
    return <SessionDetail index={parseInt(sessionIndex, 10)} />;
  }
  return <SessionList />;
}

// ── Session List View ────────────────────────────────────────────────

function SessionList() {
  const navigate = useNavigate();
  const { data, isPending } = useQuery({
    queryKey: queryKeys.sessions.list,
    queryFn: getSessions,
  });

  const sessions = data?.sessions ?? [];
  const latestIndex = sessions.length > 0 ? sessions[0].session_index : undefined;

  // Fetch latest session detail for hero card
  const { data: latestDetail } = useQuery({
    queryKey: queryKeys.sessions.detail(latestIndex!),
    queryFn: () => getSessionDetail(latestIndex!),
    enabled: latestIndex !== undefined,
  });

  if (!isPending && sessions.length === 0) {
    return (
      <div className="max-w-6xl mx-auto">
        <EmptyState variant="no-data" />
      </div>
    );
  }

  return (
    <div className="max-w-6xl mx-auto space-y-1.5">

      {isPending ? (
        <Card className="gap-0 py-0">
          <CardContent className="px-3 py-3 space-y-2">
            <Skeleton className="h-4 w-48" />
            <Skeleton className="h-64 w-full" />
          </CardContent>
        </Card>
      ) : (
        <Card className="overflow-hidden gap-0 py-0">
          <div className="overflow-x-auto">
            <Table style={{ tableLayout: 'fixed', width: '100%' }}>
              <colgroup>
                <col style={{ width: '20%' }} />
                <col style={{ width: '12%' }} />
                <col style={{ width: '10%' }} />
                <col style={{ width: '16%' }} />
                <col style={{ width: '14%' }} />
                <col style={{ width: '14%' }} />
                <col style={{ width: '14%' }} />
              </colgroup>
              <TableHeader>
                <TableRow>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide">Date</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide text-right">Duration</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide text-right">Hands</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide">Stakes</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide text-right">Won</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide text-right">bb/100</TableHead>
                  <TableHead className="px-3 py-1.5 h-auto text-[11px] uppercase tracking-wide text-right">EV bb/100</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {sessions.map((s, i) => (
                  i === 0 ? (
                    <LatestSessionRow
                      key={s.session_index}
                      summary={s}
                      detail={latestDetail ?? null}
                      onClick={() => navigate(`/sessions/${s.session_index}`)}
                    />
                  ) : (
                    <SessionRow
                      key={s.session_index}
                      session={s}
                      onClick={() => navigate(`/sessions/${s.session_index}`)}
                    />
                  )
                ))}
              </TableBody>
            </Table>
          </div>
        </Card>
      )}
    </div>
  );
}

// ── Session Detail View ──────────────────────────────────────────────

function SessionDetail({ index }: { index: number }) {
  const [unit, setUnit] = useState<'bb' | 'usd'>('bb');
  const [selectedHandId, setSelectedHandId] = useState<string | null>(null);
  const [handsPage, setHandsPage] = useState(1);
  const [handsPerPage, setHandsPerPage] = useState(50);

  const { data, isPending } = useQuery({
    queryKey: queryKeys.sessions.detail(index),
    queryFn: () => getSessionDetail(index),
  });

  const stats = data?.stats;
  const graph = useMemo(() => data?.graph ?? [], [data]);

  // Compute date_from/date_to from session boundaries for hands query
  // Use raw ISO strings directly — avoid Date→toISOString() which shifts to UTC
  const dateFrom = stats?.start_time?.slice(0, 19);
  const dateTo = stats?.end_time?.slice(0, 19);

  const handsQueryParams = useMemo(() => ({
    page: handsPage,
    per_page: handsPerPage,
    date_from: dateFrom,
    date_to: dateTo,
    sort: 'played_at',
    order: 'desc' as const,
  }), [handsPage, handsPerPage, dateFrom, dateTo]);

  const { data: handsData, isPending: handsLoading } = useQuery({
    queryKey: queryKeys.hands.list(handsQueryParams),
    queryFn: () => getHands(handsQueryParams),
    enabled: !!dateFrom && !!dateTo,
  });

  const hands = handsData?.hands ?? [];
  const selectedIdx = selectedHandId ? hands.findIndex(h => h.id === selectedHandId) : -1;

  const hasEVData = useMemo(() => graph.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [graph]);

  const mainKey = unit === 'bb' ? 'cumulative_bb' : 'cumulative_usd';
  const evKey = unit === 'bb' ? 'cumulative_ev_bb' : 'cumulative_ev_usd';
  const sdKey = unit === 'bb' ? 'cumulative_showdown_bb' : 'cumulative_showdown_usd';
  const nsdKey = unit === 'bb' ? 'cumulative_nonshowdown_bb' : 'cumulative_nonshowdown_usd';

  const last = graph[graph.length - 1];
  const sdBB = last?.cumulative_showdown_bb ?? 0;
  const sdUSD = last?.cumulative_showdown_usd ?? 0;
  const nsdBB = last?.cumulative_nonshowdown_bb ?? 0;
  const nsdUSD = last?.cumulative_nonshowdown_usd ?? 0;
  const n0 = graph.length;
  const sdRateBB = n0 > 0 ? (sdBB / n0) * 100 : 0;
  const nsdRateBB = n0 > 0 ? (nsdBB / n0) * 100 : 0;

  if (isPending) {
    return (
      <div className="max-w-6xl mx-auto space-y-1.5">
        <Skeleton className="h-8 w-64 mb-3" />
        <Card className="gap-0 py-0 p-2"><Skeleton className="h-[300px] w-full rounded" /></Card>
        <Card className="gap-0 py-0"><Skeleton className="h-32 w-full" /></Card>
      </div>
    );
  }

  if (!stats) {
    return (
      <div className="max-w-6xl mx-auto">
        <EmptyState variant="no-data" />
      </div>
    );
  }

  const n = stats.hands;
  const durationHrs = stats.duration_minutes / 60;

  return (
    <div className="max-w-6xl mx-auto space-y-1.5">
      {/* Header info strip */}
      <div className="flex items-center gap-2 mb-1">
        <h1 className="text-[18px] font-bold text-text">
          {formatSessionDate(stats.start_time)}
        </h1>
        <span className="text-sm text-text-muted">
          {formatTime(stats.start_time)} – {formatTime(stats.end_time)}
        </span>
        <Badge variant="secondary">{formatDuration(stats.duration_minutes)}</Badge>
        {stats.stakes.map(st => (
          <Badge key={st} variant="secondary">{formatStakes(st)}</Badge>
        ))}
      </div>

      {/* Section 1: Graph */}
      {graph.length > 0 && (
        <Card className="gap-0 py-0 p-2">
          <div className="flex items-center gap-2.5 px-2 py-1">
            <ToggleGroup type="single" value={unit} onValueChange={(v) => { if (v) setUnit(v as 'bb' | 'usd'); }}>
              <ToggleGroupItem value="bb" className="h-7 text-xs px-3">BB</ToggleGroupItem>
              <ToggleGroupItem value="usd" className="h-7 text-xs px-3">$</ToggleGroupItem>
            </ToggleGroup>
          </div>
          <div className="flex justify-center gap-4 mt-1.5 mb-1 text-xs text-text-muted">
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-4 h-0.5 rounded" style={{ background: '#fbbf24' }} />
              Actual
            </span>
            {hasEVData && (
              <span className="flex items-center gap-1.5">
                <span className="inline-block w-4 h-0.5 rounded" style={{ background: '#06b6d4', opacity: 0.8 }} />
                All-in EV
              </span>
            )}
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-4 h-0.5 rounded" style={{ background: '#22c55e' }} />
              Showdown
            </span>
            <span className="flex items-center gap-1.5">
              <span className="inline-block w-4 h-0.5 rounded" style={{ background: '#ef4444' }} />
              Non-Showdown
            </span>
          </div>
          <ResponsiveContainer width="100%" height={300}>
            <ComposedChart data={graph} margin={{ top: 4, right: 16, bottom: 4, left: 8 }}>
              <defs>
                <linearGradient id="sessionGradient" x1="0" y1="0" x2="0" y2="1">
                  <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.25} />
                  <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                </linearGradient>
              </defs>
              <CartesianGrid vertical={false} stroke="oklch(0.268 0.007 34.298)" />
              <XAxis
                dataKey="hand_number"
                type="number"
                domain={[0, 'dataMax']}
                stroke="oklch(0.553 0.013 58.071)"
                tick={{ fontSize: 11, fill: 'oklch(0.553 0.013 58.071)' }}
                axisLine={false}
                tickLine={false}
              />
              <YAxis
                stroke="oklch(0.553 0.013 58.071)"
                tick={{ fontSize: 11, fill: 'oklch(0.553 0.013 58.071)' }}
                axisLine={false}
                tickLine={false}
                width={50}
                tickFormatter={(v: number) => unit === 'usd' ? `$${v}` : String(v)}
              />
              <Tooltip
                content={<SessionTooltip unit={unit} />}
              />
              <ReferenceLine y={0} stroke="oklch(0.553 0.013 58.071 / 50%)" strokeDasharray="4 4" />
              <Area
                type="monotone"
                dataKey={mainKey}
                name={mainKey}
                fill="url(#sessionGradient)"
                stroke="#fbbf24"
                strokeWidth={2}
                dot={false}
                connectNulls
                isAnimationActive={false}
                baseValue={0}
              />
              {hasEVData && (
                <Line
                  type="monotone"
                  dataKey={evKey}
                  name={evKey}
                  stroke="#06b6d4"
                  strokeWidth={1.5}
                  dot={false}
                  connectNulls
                  strokeDasharray="6 3"
                  opacity={0.8}
                  isAnimationActive={false}
                />
              )}
              <Line
                type="monotone"
                dataKey={sdKey}
                name={sdKey}
                stroke="#22c55e"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
              <Line
                type="monotone"
                dataKey={nsdKey}
                name={nsdKey}
                stroke="#ef4444"
                strokeWidth={1.5}
                dot={false}
                connectNulls
                isAnimationActive={false}
              />
            </ComposedChart>
          </ResponsiveContainer>
        </Card>
      )}

      {/* Section 2: Results summary */}
      <Card className="gap-0 py-0 overflow-hidden">
        <div className="px-4 py-2 text-xs font-mono text-text-muted">
          {n} hands · {stats.hands_per_hour > 0 ? `${stats.hands_per_hour}/hr · ` : ''}{formatDuration(stats.duration_minutes)}
        </div>
        <div className="grid grid-cols-2 border-t border-border">
          <div className="px-4 py-3 grid grid-cols-2 gap-x-4">
            <div className={`text-xl font-bold font-mono ${clr(stats.won_usd)}`}>{fmtUSD(stats.won_usd)}</div>
            <div className={`text-xl font-bold font-mono ${clr(stats.bb_per_100)}`}>{stats.bb_per_100.toFixed(2)}</div>
            <div className={`text-sm font-mono ${clr(stats.won_bb)}`}>{fmtBB(stats.won_bb)}</div>
            <div className="text-sm font-mono text-text-muted">bb/100</div>
            <div className="text-[10px] text-text-muted uppercase tracking-wide">Won</div>
            <div className="text-[10px] text-text-muted uppercase tracking-wide">Rate</div>
          </div>
          <div className="px-4 py-3 border-l border-border grid grid-cols-2 gap-x-4">
            {hasEVData ? (
              <>
                <div className={`text-xl font-bold font-mono ${clr(stats.ev_usd)}`}>{fmtUSD(stats.ev_usd)}</div>
                <div className={`text-xl font-bold font-mono ${clr(stats.ev_bb_per_100)}`}>{stats.ev_bb_per_100.toFixed(2)}</div>
                <div className={`text-sm font-mono ${clr(stats.ev_bb)}`}>{fmtBB(stats.ev_bb)}</div>
                <div className="text-sm font-mono text-text-muted">EV bb/100</div>
                <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
              </>
            ) : (
              <>
                <div className="text-xl font-bold font-mono text-text-muted">&mdash;</div>
                <div className="text-xl font-bold font-mono text-text-muted">&mdash;</div>
                <div className="text-sm font-mono text-text-muted">&nbsp;</div>
                <div className="text-sm font-mono text-text-muted">&nbsp;</div>
                <div className="text-[10px] text-text-muted uppercase tracking-wide">Won EV</div>
                <div className="text-[10px] text-text-muted uppercase tracking-wide">EV Rate</div>
              </>
            )}
          </div>
        </div>
        <div className="grid grid-cols-5 gap-x-6 px-4 py-2.5 border-t border-border">
          <div>
            <div className={`text-sm font-bold font-mono ${durationHrs > 0 ? clr(stats.usd_per_hour) : 'text-text-muted'}`}>
              {durationHrs > 0 ? `${stats.usd_per_hour >= 0 ? '' : '-'}$${Math.abs(stats.usd_per_hour).toFixed(2)}/hr` : '\u2014'}
            </div>
            <div className="text-xs text-text-muted">
              $/hr {durationHrs > 0 && <span className={`font-mono ${clr(stats.bb_per_hour)}`}>{stats.bb_per_hour.toFixed(1)} BB</span>}
            </div>
          </div>
          <div>
            <div className={`text-sm font-bold font-mono ${clr(sdUSD)}`}>{fmtUSD(sdUSD)}</div>
            <div className="text-xs text-text-muted">Showdown <span className={`font-mono ${clr(sdRateBB)}`}>{sdRateBB.toFixed(1)}/100</span></div>
          </div>
          <div>
            <div className={`text-sm font-bold font-mono ${clr(nsdUSD)}`}>{fmtUSD(nsdUSD)}</div>
            <div className="text-xs text-text-muted">Non-SD <span className={`font-mono ${clr(nsdRateBB)}`}>{nsdRateBB.toFixed(1)}/100</span></div>
          </div>
          <div>
            <div className="text-sm font-bold font-mono text-text-muted">{fmtUSD(stats.rake_usd)}</div>
            <div className="text-xs text-text-muted">Rake <span className="font-mono">{fmtBB(stats.rake_bb)}</span></div>
          </div>
          <div>
            <div className="text-sm font-bold font-mono text-text">{stats.hands_per_hour > 0 ? Math.round(stats.hands_per_hour) : '\u2014'}</div>
            <div className="text-xs text-text-muted">Hands/hr</div>
          </div>
        </div>
      </Card>

      {/* Section 3: Play stats */}
      <Card className="gap-0 py-0 overflow-hidden">
        <CardHeader className="px-3 py-1.5">
          <h2 className="text-xs font-semibold text-text">Play Stats</h2>
        </CardHeader>
        <div className="grid grid-cols-3 sm:grid-cols-5 lg:grid-cols-9 gap-px bg-border border-t border-border">
          <PlayStatBox label="VPIP" value={stats.vpip_pct} />
          <PlayStatBox label="PFR" value={stats.pfr_pct} />
          <PlayStatBox label="3-Bet" value={stats.three_bet_pct} />
          <PlayStatBox label="CBet Flop" value={stats.cbet_flop_pct} />
          <PlayStatBox label="WTSD" value={stats.wtsd_pct} />
          <PlayStatBox label="W$SD" value={stats.wsd_pct} />
          <PlayStatBox label="WWSF" value={stats.wwsf_pct} />
          <PlayStatBox label="Steal" value={stats.steal_pct} />
          <PlayStatBox label="AFq Flop" value={stats.afq_flop_pct} />
        </div>
      </Card>

      {/* Section 4: Biggest hands */}
      {(data!.biggest_wins.length > 0 || data!.biggest_losses.length > 0) && (
        <div className="grid grid-cols-1 md:grid-cols-2 gap-1.5">
          <BigHandsCard
            title="Biggest Wins"
            hands={data!.biggest_wins}
            onHandClick={setSelectedHandId}
          />
          <BigHandsCard
            title="Biggest Losses"
            hands={data!.biggest_losses}
            onHandClick={setSelectedHandId}
          />
        </div>
      )}

      {/* Section 5: Hand Explorer */}
      <Card className="overflow-hidden gap-0 py-0">
        <CardHeader className="px-3 py-1.5">
          <h2 className="text-xs font-semibold text-text">Hands</h2>
        </CardHeader>
        {handsLoading ? (
          <CardContent className="px-3 py-3">
            <Skeleton className="h-48 w-full" />
          </CardContent>
        ) : hands.length === 0 ? (
          <CardContent className="px-3 py-6 text-center text-sm text-text-muted">
            No hands in this session
          </CardContent>
        ) : (
          <>
            <div className="overflow-x-auto">
              <Table>
                <TableHeader>
                  <TableRow className="text-[13px] uppercase tracking-wide">
                    <TableHead className="py-2 px-2 h-auto">Preflop</TableHead>
                    <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                    <TableHead className="py-2 pl-4 pr-2 h-auto">Flop</TableHead>
                    <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                    <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                    <TableHead className="py-2 pl-4 pr-2 h-auto">Turn</TableHead>
                    <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                    <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                    <TableHead className="py-2 pl-4 pr-2 h-auto">River</TableHead>
                    <TableHead className="py-2 px-1 h-auto text-center">Pot</TableHead>
                    <TableHead className="py-2 px-2 h-auto">Actions</TableHead>
                    <TableHead className="py-2 pl-4 pr-2 h-auto">Stakes</TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right">Won</TableHead>
                    <TableHead className="py-2 px-2 h-auto text-right">Date</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {hands.map((h) => {
                    const wonUsd = h.won_bb * h.bb_amount;
                    return (
                      <TableRow
                        key={h.id}
                        onClick={() => setSelectedHandId(h.id)}
                        className={`cursor-pointer transition-colors text-[15px] ${
                          selectedHandId === h.id ? 'bg-primary/10' : 'hover:bg-surface-hover'
                        }`}
                      >
                        <TableCell className="py-1.5 px-2">
                          <CardBoxPair card1={h.card1} card2={h.card2} />
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          <Actions items={h.preflop_actions} trimFolds />
                        </TableCell>
                        <TableCell className="py-1.5 pl-4 pr-2">
                          <CardBoxRow cards={h.flop_cards} />
                        </TableCell>
                        <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                          {h.flop_cards.length > 0 ? Math.round(h.flop_pot) : ''}
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          <Actions items={h.flop_actions} />
                        </TableCell>
                        <TableCell className="py-1.5 pl-4 pr-2">
                          {h.turn_card && <CardBox card={h.turn_card} />}
                        </TableCell>
                        <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                          {h.turn_card ? Math.round(h.turn_pot) : ''}
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          <Actions items={h.turn_actions} />
                        </TableCell>
                        <TableCell className="py-1.5 pl-4 pr-2">
                          {h.river_card && <CardBox card={h.river_card} />}
                        </TableCell>
                        <TableCell className="py-1.5 px-1 text-center font-mono text-[14px] text-text-muted">
                          {h.river_card ? Math.round(h.river_pot) : ''}
                        </TableCell>
                        <TableCell className="py-1.5 px-2">
                          <Actions items={h.river_actions} />
                        </TableCell>
                        <TableCell className="py-1.5 pl-4 pr-2 font-mono text-[15px] text-text-muted">
                          {formatStakes(h.stakes)}
                        </TableCell>
                        <TableCell className={`py-1.5 px-2 text-right font-mono text-[15px] font-semibold ${
                          wonUsd > 0.005 ? 'text-green' : wonUsd < -0.005 ? 'text-red' : 'text-text-muted'
                        }`}>
                          {Math.abs(wonUsd) < 0.005
                            ? '\u2014'
                            : `${wonUsd < 0 ? '-' : ''}${Math.abs(wonUsd).toFixed(2)}$`}
                        </TableCell>
                        <TableCell className="py-1.5 px-2 text-right text-[14px] text-text-muted whitespace-nowrap">
                          {formatRelativeDate(h.played_at)}
                        </TableCell>
                      </TableRow>
                    );
                  })}
                </TableBody>
              </Table>
            </div>
            {handsData && handsData.total_pages > 1 && (
              <Pagination
                page={handsData.page}
                totalPages={handsData.total_pages}
                perPage={handsPerPage}
                onPageChange={setHandsPage}
                onPerPageChange={(pp) => { setHandsPerPage(pp); setHandsPage(1); }}
              />
            )}
          </>
        )}
      </Card>

      {/* Hand Drawer */}
      {selectedHandId && (
        <HandDrawer
          handId={selectedHandId}
          onClose={() => setSelectedHandId(null)}
          onPrev={() => { if (selectedIdx > 0) setSelectedHandId(hands[selectedIdx - 1].id); }}
          onNext={() => { if (selectedIdx >= 0 && selectedIdx < hands.length - 1) setSelectedHandId(hands[selectedIdx + 1].id); }}
          onTagsChanged={() => { queryClient.invalidateQueries({ queryKey: ['hands'] }); }}
        />
      )}
    </div>
  );
}

// ── Session Table Rows ──────────────────────────────────────────────

function SessionRow({
  session: s,
  onClick,
}: {
  session: { session_index: number; start_time: string; duration_minutes: number; hands: number; stakes: string[]; won_usd: number; bb_per_100: number; ev_bb_per_100: number };
  onClick: () => void;
}) {
  return (
    <TableRow
      className="cursor-pointer hover:bg-surface-hover transition-colors"
      onClick={onClick}
    >
      <TableCell className="px-3 py-1.5 font-mono text-text">
        {formatSessionDate(s.start_time)}
        <span className="text-text-muted ml-1.5 text-xs">{formatTime(s.start_time)}</span>
      </TableCell>
      <TableCell className="px-3 py-1.5 font-mono text-text-muted text-right">
        {formatDuration(s.duration_minutes)}
      </TableCell>
      <TableCell className="px-3 py-1.5 font-mono text-text text-right">{s.hands}</TableCell>
      <TableCell className="px-3 py-1.5">
        <div className="flex flex-wrap gap-1">
          {s.stakes.map(st => (
            <Badge key={st} variant="secondary" className="text-[11px] px-1.5 py-0">{formatStakes(st)}</Badge>
          ))}
        </div>
      </TableCell>
      <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.won_usd)}`}>{fmtUSD(s.won_usd)}</TableCell>
      <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.bb_per_100)}`}>{s.bb_per_100.toFixed(2)}</TableCell>
      <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.ev_bb_per_100)}`}>{s.ev_bb_per_100.toFixed(2)}</TableCell>
    </TableRow>
  );
}

function LatestSessionRow({
  summary: s,
  detail,
  onClick,
}: {
  summary: { session_index: number; start_time: string; end_time: string; duration_minutes: number; hands: number; stakes: string[]; won_usd: number; won_bb: number; ev_usd: number; ev_bb: number; bb_per_100: number; ev_bb_per_100: number; rake_usd: number; rake_bb: number };
  detail: SessionDetailResponse | null;
  onClick: () => void;
}) {
  const graph = useMemo(() => detail?.graph ?? [], [detail]);
  const stats = detail?.stats;
  const hasEVData = useMemo(() => graph.some(d => d.cumulative_ev_bb !== d.cumulative_bb), [graph]);
  const durationHrs = s.duration_minutes / 60;

  return (
    <>
      {/* Normal row cells */}
      <TableRow
        className="cursor-pointer hover:bg-surface-hover transition-colors border-b-0"
        onClick={onClick}
      >
        <TableCell className="px-3 py-1.5 font-mono text-text">
          {formatSessionDate(s.start_time)}
          <span className="text-text-muted ml-1.5 text-xs">{formatTime(s.start_time)}</span>
        </TableCell>
        <TableCell className="px-3 py-1.5 font-mono text-text-muted text-right">
          {formatDuration(s.duration_minutes)}
        </TableCell>
        <TableCell className="px-3 py-1.5 font-mono text-text text-right">{s.hands}</TableCell>
        <TableCell className="px-3 py-1.5">
          <div className="flex flex-wrap gap-1">
            {s.stakes.map(st => (
              <Badge key={st} variant="secondary" className="text-[11px] px-1.5 py-0">{formatStakes(st)}</Badge>
            ))}
          </div>
        </TableCell>
        <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.won_usd)}`}>{fmtUSD(s.won_usd)}</TableCell>
        <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.bb_per_100)}`}>{s.bb_per_100.toFixed(2)}</TableCell>
        <TableCell className={`px-3 py-1.5 font-mono text-right ${colorVal(s.ev_bb_per_100)}`}>{s.ev_bb_per_100.toFixed(2)}</TableCell>
      </TableRow>

      {/* Expanded detail row */}
      <TableRow className="hover:bg-transparent cursor-pointer" onClick={onClick}>
        <TableCell colSpan={7} className="p-0">
          <div className="grid grid-cols-[1fr_260px] border-t border-border/50">
            {/* Mini graph */}
            <div className="py-1 pl-2 pr-0">
              {graph.length > 0 ? (
                <ResponsiveContainer width="100%" height={140}>
                  <ComposedChart data={graph} margin={{ top: 4, right: 8, bottom: 4, left: 0 }}>
                    <defs>
                      <linearGradient id="latestGradient" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="#fbbf24" stopOpacity={0.25} />
                        <stop offset="100%" stopColor="#fbbf24" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid vertical={false} stroke="oklch(0.268 0.007 34.298)" />
                    <XAxis dataKey="hand_number" type="number" domain={[0, 'dataMax']} hide />
                    <YAxis
                      stroke="oklch(0.553 0.013 58.071)"
                      tick={{ fontSize: 10, fill: 'oklch(0.553 0.013 58.071)' }}
                      axisLine={false} tickLine={false} width={40}
                    />
                    <ReferenceLine y={0} stroke="oklch(0.553 0.013 58.071 / 50%)" strokeDasharray="4 4" />
                    <Area
                      type="monotone" dataKey="cumulative_bb" name="cumulative_bb"
                      fill="url(#latestGradient)" stroke="#fbbf24" strokeWidth={2}
                      dot={false} connectNulls isAnimationActive={false} baseValue={0}
                    />
                    {hasEVData && (
                      <Line
                        type="monotone" dataKey="cumulative_ev_bb" name="cumulative_ev_bb"
                        stroke="#06b6d4" strokeWidth={1.5} dot={false} connectNulls
                        strokeDasharray="6 3" opacity={0.8} isAnimationActive={false}
                      />
                    )}
                    <Line
                      type="monotone" dataKey="cumulative_showdown_bb" name="cumulative_showdown_bb"
                      stroke="#22c55e" strokeWidth={1.5} dot={false} connectNulls
                      isAnimationActive={false}
                    />
                    <Line
                      type="monotone" dataKey="cumulative_nonshowdown_bb" name="cumulative_nonshowdown_bb"
                      stroke="#ef4444" strokeWidth={1.5} dot={false} connectNulls
                      isAnimationActive={false}
                    />
                  </ComposedChart>
                </ResponsiveContainer>
              ) : (
                <div className="h-[140px] flex items-center justify-center">
                  <Skeleton className="h-[120px] w-full rounded" />
                </div>
              )}
            </div>

            {/* Key stats */}
            <div className="border-l border-border/50 px-4 py-2 flex flex-col justify-center gap-1">
              <div className="grid grid-cols-2 gap-x-3">
                <div className={`text-lg font-bold font-mono ${clr(s.won_usd)}`}>{fmtUSD(s.won_usd)}</div>
                <div className={`text-lg font-bold font-mono ${clr(s.bb_per_100)}`}>{s.bb_per_100.toFixed(2)}</div>
                <div className={`text-xs font-mono ${clr(s.won_bb)}`}>{fmtBB(s.won_bb)}</div>
                <div className="text-xs font-mono text-text-muted">bb/100</div>
              </div>
              {hasEVData && (
                <div className="grid grid-cols-2 gap-x-3 pt-1 border-t border-border/50">
                  <div className={`text-sm font-bold font-mono ${clr(s.ev_usd)}`}>{fmtUSD(s.ev_usd)}</div>
                  <div className={`text-sm font-bold font-mono ${clr(s.ev_bb_per_100)}`}>{s.ev_bb_per_100.toFixed(2)}</div>
                  <div className="text-[10px] text-text-muted">EV Won</div>
                  <div className="text-[10px] text-text-muted">EV bb/100</div>
                </div>
              )}
              <div className="flex items-center gap-3 pt-1 border-t border-border/50 text-xs text-text-muted font-mono">
                <span className={durationHrs > 0 ? clr(stats?.usd_per_hour ?? 0) : ''}>
                  {durationHrs > 0 && stats ? `${stats.usd_per_hour >= 0 ? '' : '-'}$${Math.abs(stats.usd_per_hour).toFixed(2)}/hr` : '\u2014'}
                </span>
                <span>{s.hands} hands</span>
                <span>{stats?.hands_per_hour ? `${Math.round(stats.hands_per_hour)}/hr` : ''}</span>
              </div>
            </div>
          </div>

          {/* Play stats strip */}
          {stats && (
            <div className="grid grid-cols-9 gap-px bg-border border-t border-border/50">
              <MiniStatBox label="VPIP" value={stats.vpip_pct} />
              <MiniStatBox label="PFR" value={stats.pfr_pct} />
              <MiniStatBox label="3-Bet" value={stats.three_bet_pct} />
              <MiniStatBox label="CBet" value={stats.cbet_flop_pct} />
              <MiniStatBox label="WTSD" value={stats.wtsd_pct} />
              <MiniStatBox label="W$SD" value={stats.wsd_pct} />
              <MiniStatBox label="WWSF" value={stats.wwsf_pct} />
              <MiniStatBox label="Steal" value={stats.steal_pct} />
              <MiniStatBox label="AFq" value={stats.afq_flop_pct} />
            </div>
          )}
        </TableCell>
      </TableRow>
    </>
  );
}

function MiniStatBox({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="bg-background px-2 py-1.5 text-center">
      <div className="text-sm font-bold font-mono text-text">
        {value !== null ? `${value.toFixed(1)}` : '\u2014'}
      </div>
      <div className="text-[9px] text-text-muted uppercase tracking-wide">{label}</div>
    </div>
  );
}

// ── Subcomponents ────────────────────────────────────────────────────

function PlayStatBox({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="bg-background px-3 py-2.5 text-center">
      <div className="text-lg font-bold font-mono text-text">
        {value !== null ? `${value.toFixed(1)}%` : '\u2014'}
      </div>
      <div className="text-[10px] text-text-muted uppercase tracking-wide">{label}</div>
    </div>
  );
}

function BigHandsCard({
  title,
  hands,
  onHandClick,
}: {
  title: string;
  hands: SessionBigHand[];
  onHandClick: (id: string) => void;
}) {
  if (hands.length === 0) return null;
  return (
    <Card className="gap-0 py-0 overflow-hidden">
      <CardHeader className="px-3 py-1.5">
        <h2 className="text-xs font-semibold text-text">{title}</h2>
      </CardHeader>
      <div className="divide-y divide-border">
        {hands.map((h) => (
          <div
            key={h.hand_id}
            className="flex items-center gap-3 px-3 py-1.5 cursor-pointer hover:bg-surface-hover transition-colors"
            onClick={() => onHandClick(h.hand_id)}
          >
            <CardBoxPair card1={h.card1} card2={h.card2} />
            <Badge variant="secondary" className="text-[11px] px-1.5 py-0">{h.position}</Badge>
            <span className={`font-mono font-semibold ${clr(h.won_bb)}`}>
              {h.won_bb > 0 ? '+' : ''}{h.won_bb.toFixed(1)} BB
            </span>
            <span className={`font-mono text-sm ${clr(h.won_usd)}`}>
              {fmtUSD(h.won_usd)}
            </span>
            <span className="text-xs text-text-muted ml-auto">{formatStakes(h.stakes)}</span>
          </div>
        ))}
      </div>
    </Card>
  );
}

interface SessionTooltipProps {
  active?: boolean;
  payload?: Array<{ name: string; value: number; color: string; payload?: Record<string, unknown> }>;
  label?: number;
  unit: 'bb' | 'usd';
}

function SessionTooltip({ active, payload, label, unit }: SessionTooltipProps) {
  if (!active || !payload?.length) return null;
  const point = payload[0]?.payload as SessionGraphPoint | undefined;
  const prefix = unit === 'usd' ? '$' : '';
  const suffix = unit === 'bb' ? ' BB' : '';
  const names: Record<string, string> = {
    cumulative_bb: 'Actual',
    cumulative_ev_bb: 'All-in EV',
    cumulative_showdown_bb: 'Showdown',
    cumulative_nonshowdown_bb: 'Non-Showdown',
    cumulative_usd: 'Actual',
    cumulative_ev_usd: 'All-in EV',
    cumulative_showdown_usd: 'Showdown',
    cumulative_nonshowdown_usd: 'Non-Showdown',
  };
  return (
    <div style={{
      backgroundColor: 'oklch(0.216 0.006 56.043)',
      border: '1px solid oklch(1 0 0 / 10%)',
      borderRadius: '8px',
      color: 'oklch(0.985 0.001 106.423)',
      padding: '8px 12px',
      fontSize: '13px',
    }}>
      {point?.played_at && (
        <div style={{ marginBottom: 4, color: 'oklch(0.709 0.01 56.259)' }}>
          {new Date(point.played_at).toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit', hour12: false })}
        </div>
      )}
      <div style={{ marginBottom: 6, fontWeight: 600 }}>Hand #{Number(label)}</div>
      {payload.map((entry, i) => (
        <div key={i} style={{ display: 'flex', alignItems: 'center', gap: 6, marginBottom: 2 }}>
          <span style={{ width: 8, height: 8, borderRadius: '50%', backgroundColor: entry.color, display: 'inline-block', flexShrink: 0 }} />
          <span>{names[entry.name] ?? entry.name}: {prefix}{entry.value.toFixed(2)}{suffix}</span>
        </div>
      ))}
    </div>
  );
}
