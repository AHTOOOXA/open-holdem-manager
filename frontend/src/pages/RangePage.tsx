import { useState, useEffect, useMemo, useCallback } from 'react';
import { getRangeStats, getFilterOptions } from '@/lib/api';
import type { ComboStats, RangeResponse, FilterOptions } from '@/lib/api';
import FilterBar from '@/components/FilterBar';
import EmptyState from '@/components/EmptyState';
import { Card } from '@/components/ui/card';
import { ToggleGroup, ToggleGroupItem } from '@/components/ui/toggle-group';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

type ColorBy = 'bb100' | 'ev_bb100' | 'won_bb' | 'frequency' | 'hands';

function comboKey(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's'; // upper triangle = suited
  return r2 + r1 + 'o'; // lower triangle = offsuit
}

function comboLabel(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
}

function getMetricValue(combo: ComboStats | undefined, colorBy: ColorBy): number | null {
  if (!combo) return null;
  switch (colorBy) {
    case 'bb100': return combo.bb_per_100;
    case 'ev_bb100': return combo.ev_bb_per_100;
    case 'won_bb': return combo.won_bb;
    case 'frequency': return combo.hands > 0 ? (combo.vpip / combo.hands) * 100 : 0;
    case 'hands': return combo.hands;
    default: return null;
  }
}

function getCellColor(value: number | null, colorBy: ColorBy, maxAbs: number): string {
  if (value === null) return 'transparent';
  if (colorBy === 'hands') {
    const intensity = maxAbs > 0 ? Math.min(value / maxAbs, 1) : 0;
    const alpha = Math.round(intensity * 45 + 8);
    return `rgba(99, 102, 241, ${alpha / 100})`;
  }
  if (colorBy === 'frequency') {
    const intensity = Math.min(Math.abs(value) / 100, 1);
    const alpha = Math.round(intensity * 50 + 8);
    return `rgba(99, 102, 241, ${alpha / 100})`;
  }
  // Green/red: high floor so even small win/loss is clearly tinted
  if (value === 0) return 'rgba(255,255,255,0.03)';
  const clamp = maxAbs > 0 ? Math.min(Math.abs(value) / maxAbs, 1) : 0;
  // alpha range: 0.20 (floor) to 0.65 (max) — always clearly visible
  const alpha = (clamp * 0.45 + 0.20).toFixed(2);
  if (value > 0) return `rgba(22, 163, 74, ${alpha})`;  // bright green
  return `rgba(220, 38, 38, ${alpha})`;                  // bright red
}

function formatCellValue(value: number | null, colorBy: ColorBy): string {
  if (value === null) return '';
  switch (colorBy) {
    case 'bb100':
    case 'ev_bb100':
      return value.toFixed(0);
    case 'won_bb':
      if (Math.abs(value) >= 1000) return `${(value / 1000).toFixed(1)}k`;
      return value.toFixed(0);
    case 'frequency':
      return value.toFixed(0);
    case 'hands':
      return String(value);
  }
}

const MIN_SAMPLE = 30;

const POSITIONS = ['All', 'EP', 'MP', 'CO', 'BTN', 'SB', 'BB'];

const COLOR_OPTIONS: { value: ColorBy; label: string }[] = [
  { value: 'bb100', label: 'bb/100' },
  { value: 'ev_bb100', label: 'EV bb/100' },
  { value: 'won_bb', label: 'Total BB' },
  { value: 'frequency', label: 'VPIP %' },
  { value: 'hands', label: 'Hands' },
];

export default function RangePage() {
  const [data, setData] = useState<RangeResponse | null>(null);
  const [filterOpts, setFilterOpts] = useState<FilterOptions | null>(null);
  const [loading, setLoading] = useState(true);
  const [position, setPosition] = useState('All');
  const [stakes, setStakes] = useState('');
  const [gameMode, setGameMode] = useState('');
  const [colorBy, setColorBy] = useState<ColorBy>('bb100');
  const [hovered, setHovered] = useState<string | null>(null);
  const [selected, setSelected] = useState<string | null>(null);

  useEffect(() => {
    getFilterOptions().then(setFilterOpts).catch(() => {});
  }, []);

  const fetchData = useCallback(async () => {
    setLoading(true);
    try {
      const params: Record<string, string> = {};
      if (position !== 'All') params.position = position;
      if (stakes) params.stakes = stakes;
      if (gameMode) params.game_mode = gameMode;
      const result = await getRangeStats(params);
      setData(result);
    } catch {
      setData(null);
    } finally {
      setLoading(false);
    }
  }, [position, stakes, gameMode]);

  useEffect(() => { fetchData(); }, [fetchData]);

  // Build combo lookup map
  const comboMap = useMemo(() => {
    if (!data) return new Map<string, ComboStats>();
    const m = new Map<string, ComboStats>();
    for (const c of data.combos) m.set(c.combo, c);
    return m;
  }, [data]);

  // Compute max absolute value for color scaling
  const maxAbs = useMemo(() => {
    if (!data) return 1;
    let max = 0;
    for (const c of data.combos) {
      const v = getMetricValue(c, colorBy);
      if (v !== null) max = Math.max(max, Math.abs(v));
    }
    return max || 1;
  }, [data, colorBy]);

  // Biggest leaks: top 5 hands losing most total BB
  const biggestLeaks = useMemo(() => {
    if (!data) return [];
    return [...data.combos]
      .filter(c => c.won_bb < 0 && c.hands >= MIN_SAMPLE)
      .sort((a, b) => a.won_bb - b.won_bb)
      .slice(0, 5);
  }, [data]);

  // Biggest winners
  const biggestWinners = useMemo(() => {
    if (!data) return [];
    return [...data.combos]
      .filter(c => c.won_bb > 0 && c.hands >= MIN_SAMPLE)
      .sort((a, b) => b.won_bb - a.won_bb)
      .slice(0, 5);
  }, [data]);

  const activeCombo = selected ?? hovered;
  const detail = activeCombo ? comboMap.get(activeCombo) : null;

  return (
    <div className="max-w-[1400px] mx-auto space-y-2">
      {/* Filter Bar */}
      <FilterBar
        stakes={stakes}
        onStakesChange={(v) => { setStakes(v); setSelected(null); }}
        gameMode={gameMode}
        onGameModeChange={(v) => { setGameMode(v); setSelected(null); }}
        showDateRange={false}
        showDatePresets={false}
        filterOptions={filterOpts}
      >
        {/* Position */}
        <ToggleGroup type="single" value={position} onValueChange={(v) => { if (v) { setPosition(v); setSelected(null); } }}>
          {POSITIONS.map(p => (
            <ToggleGroupItem key={p} value={p} className="h-7 text-xs px-2.5">
              {p}
            </ToggleGroupItem>
          ))}
        </ToggleGroup>
        {/* Color by */}
        <Select value={colorBy} onValueChange={(v) => setColorBy(v as ColorBy)}>
          <SelectTrigger className="w-[110px] h-7 text-xs">
            <SelectValue />
          </SelectTrigger>
          <SelectContent>
            {COLOR_OPTIONS.map(o => (
              <SelectItem key={o.value} value={o.value}>{o.label}</SelectItem>
            ))}
          </SelectContent>
        </Select>
        {/* Hand count */}
        {data && (
          <span className="text-xs text-text-muted">
            {data.total_hands.toLocaleString()} hands
          </span>
        )}
      </FilterBar>

      {loading && !data ? (
        <div className="text-center text-text-muted py-20">Loading...</div>
      ) : !data || data.total_hands === 0 ? (
        <EmptyState variant={stakes ? 'no-match' : 'no-data'} onClearFilters={stakes ? () => setStakes('') : undefined} />
      ) : (
        <div className="flex flex-wrap lg:flex-nowrap gap-5">
          {/* Matrix */}
          <div className="shrink-0">
            <div
              className="grid gap-[2px]"
              style={{ gridTemplateColumns: `32px repeat(13, 1fr)` }}
            >
              {/* Header row */}
              <div />
              {RANKS.map(r => (
                <div key={r} className="text-center text-sm text-text-muted font-mono pb-1">
                  {r}
                </div>
              ))}
              {/* Matrix rows */}
              {RANKS.map((_, row) => (
                <>
                  {/* Row label */}
                  <div key={`label-${row}`} className="flex items-center justify-center text-sm text-text-muted font-mono pr-1">
                    {RANKS[row]}
                  </div>
                  {RANKS.map((_, col) => {
                    const key = comboKey(row, col);
                    const combo = comboMap.get(key);
                    const value = getMetricValue(combo, colorBy);
                    const bg = getCellColor(value, colorBy, maxAbs);
                    const lowSample = combo ? combo.hands < MIN_SAMPLE : true;
                    const isActive = activeCombo === key;
                    const isSuited = col > row;
                    const isPair = col === row;

                    return (
                      <div
                        key={`${row}-${col}`}
                        className={`relative flex flex-col items-center justify-center cursor-pointer transition-all
                          ${isPair ? 'rounded-sm' : ''}
                          ${isActive ? 'ring-1 ring-primary z-10' : ''}
                          ${lowSample ? 'opacity-50' : ''}
                        `}
                        style={{
                          backgroundColor: bg,
                          aspectRatio: '5/4',
                          border: '1px solid oklch(1 0 0 / 10%)',
                        }}
                        onMouseEnter={() => setHovered(key)}
                        onMouseLeave={() => setHovered(null)}
                        onClick={() => setSelected(selected === key ? null : key)}
                      >
                        <span className={`text-[15px] font-mono font-medium leading-none ${
                          isSuited ? 'text-primary' : isPair ? 'text-yellow' : 'text-text-muted'
                        }`}>
                          {comboLabel(row, col)}
                        </span>
                        {combo && combo.hands > 0 && (
                          <span className={`text-[14px] font-mono font-semibold leading-none mt-1 ${
                            value !== null && (colorBy === 'bb100' || colorBy === 'ev_bb100' || colorBy === 'won_bb')
                              ? value > 0 ? 'text-green' : value < 0 ? 'text-red' : 'text-text-muted'
                              : 'text-text'
                          }`}>
                            {formatCellValue(value, colorBy)}
                          </span>
                        )}
                        {lowSample && combo && combo.hands > 0 && (
                          <span className="absolute bottom-0.5 right-1 text-[10px] text-text-muted font-mono">
                            {combo.hands}
                          </span>
                        )}
                      </div>
                    );
                  })}
                </>
              ))}
            </div>
            {/* Legend */}
            <div className="flex items-center gap-5 mt-3 text-xs text-text-muted">
              <span><span className="text-primary font-mono">AKs</span> = suited</span>
              <span><span className="text-yellow font-mono">AA</span> = pair</span>
              <span><span className="text-text-muted font-mono">AKo</span> = offsuit</span>
              <span className="opacity-50">faded = &lt;{MIN_SAMPLE} hands</span>
            </div>
          </div>

          {/* Right panel: detail + leaks */}
          <div className="w-full lg:w-auto lg:min-w-[280px] flex-1">
            {/* Combo detail */}
            {detail ? (
              <Card className="gap-0 py-0 p-3 mb-1.5">
                <div className="flex items-center justify-between mb-2">
                  <span className="text-2xl font-bold font-mono">{activeCombo}</span>
                  <span className="text-sm text-text-muted">
                    {detail.hands} hands
                    {detail.hands < MIN_SAMPLE && (
                      <span className="text-yellow ml-1">(low sample)</span>
                    )}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-x-6 gap-y-2 text-[15px]">
                  <DetailRow label="Won" value={`${detail.won_bb >= 0 ? '+' : ''}${detail.won_bb.toFixed(1)} BB`} color={detail.won_bb >= 0 ? 'text-green' : 'text-red'} />
                  <DetailRow label="bb/100" value={detail.bb_per_100.toFixed(1)} color={detail.bb_per_100 >= 0 ? 'text-green' : 'text-red'} />
                  <DetailRow label="EV Won" value={`${detail.ev_bb >= 0 ? '+' : ''}${detail.ev_bb.toFixed(1)} BB`} color={detail.ev_bb >= 0 ? 'text-green' : 'text-red'} />
                  <DetailRow label="EV bb/100" value={detail.ev_bb_per_100.toFixed(1)} color={detail.ev_bb_per_100 >= 0 ? 'text-green' : 'text-red'} />
                  <DetailRow label="VPIP" value={`${detail.hands > 0 ? ((detail.vpip / detail.hands) * 100).toFixed(0) : 0}%`} />
                  <DetailRow label="PFR" value={`${detail.hands > 0 ? ((detail.pfr / detail.hands) * 100).toFixed(0) : 0}%`} />
                  <DetailRow label="3-Bet" value={`${detail.hands > 0 ? ((detail.three_bet / detail.hands) * 100).toFixed(0) : 0}%`} />
                  <DetailRow label="WTSD" value={detail.wtsd_opp > 0 ? `${((detail.wtsd / detail.wtsd_opp) * 100).toFixed(0)}%` : '--'} sub={detail.wtsd_opp > 0 ? `${detail.wtsd}/${detail.wtsd_opp}` : undefined} />
                  <DetailRow label="W$SD" value={detail.wsd_opp > 0 ? `${((detail.wsd / detail.wsd_opp) * 100).toFixed(0)}%` : '--'} sub={detail.wsd_opp > 0 ? `${detail.wsd}/${detail.wsd_opp}` : undefined} />
                </div>
              </Card>
            ) : (
              <Card className="p-3 mb-2 text-text-muted text-[15px]">
                Hover or click a cell to see details
              </Card>
            )}

            {/* Biggest leaks */}
            {biggestLeaks.length > 0 && (
              <Card className="gap-0 py-0 p-3 mb-1.5">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-2">Biggest Leaks</h3>
                <div className="space-y-2">
                  {biggestLeaks.map(c => (
                    <div
                      key={c.combo}
                      className="flex items-center justify-between text-[15px] cursor-pointer hover:bg-surface-hover rounded px-2 py-1 -mx-2"
                      onMouseEnter={() => setHovered(c.combo)}
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => setSelected(selected === c.combo ? null : c.combo)}
                    >
                      <span className="font-mono font-medium">{c.combo}</span>
                      <span className="flex items-center gap-3">
                        <span className="text-red font-mono">{c.won_bb.toFixed(0)} BB</span>
                        <span className="text-text-muted text-sm">{c.hands}h</span>
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}

            {/* Biggest winners */}
            {biggestWinners.length > 0 && (
              <Card className="gap-0 py-0 p-3">
                <h3 className="text-sm font-medium text-text-muted uppercase tracking-wide mb-2">Top Winners</h3>
                <div className="space-y-2">
                  {biggestWinners.map(c => (
                    <div
                      key={c.combo}
                      className="flex items-center justify-between text-[15px] cursor-pointer hover:bg-surface-hover rounded px-2 py-1 -mx-2"
                      onMouseEnter={() => setHovered(c.combo)}
                      onMouseLeave={() => setHovered(null)}
                      onClick={() => setSelected(selected === c.combo ? null : c.combo)}
                    >
                      <span className="font-mono font-medium">{c.combo}</span>
                      <span className="flex items-center gap-3">
                        <span className="text-green font-mono">+{c.won_bb.toFixed(0)} BB</span>
                        <span className="text-text-muted text-sm">{c.hands}h</span>
                      </span>
                    </div>
                  ))}
                </div>
              </Card>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

function DetailRow({ label, value, color, sub }: { label: string; value: string; color?: string; sub?: string }) {
  return (
    <div className="flex justify-between items-baseline">
      <span className="text-text-muted">{label}</span>
      <span className={`font-mono font-medium ${color ?? 'text-text'}`}>
        {value}
        {sub && <span className="text-xs text-text-muted ml-1">({sub})</span>}
      </span>
    </div>
  );
}
