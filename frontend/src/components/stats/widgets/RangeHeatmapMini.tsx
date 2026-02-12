import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getStatRange } from '@/lib/api';
import type { StatRangeCombo } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';
import { ChevronDown, ChevronRight } from 'lucide-react';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

function comboKey(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
}

function fmtCount(n: number): string {
  if (n === 0) return '';
  if (n >= 1000) return `${(n / 1000).toFixed(n >= 10000 ? 0 : 1)}k`;
  return String(n);
}

function fmtBb(v: number): string {
  if (v === 0) return '';
  const rounded = Math.round(v);
  if (rounded === 0) return '';
  return rounded > 0 ? `+${rounded}` : String(rounded);
}

interface RangeHeatmapMiniProps {
  statKey: string;
  filterParams: {
    stakes?: string;
    game_mode?: string;
    date_from?: string;
    date_to?: string;
  };
  position?: string;
}

function MiniGrid({
  comboMap,
  getValue,
  getColor,
  formatCell,
  label,
  formatTooltip,
  textColor,
}: {
  comboMap: Map<string, StatRangeCombo>;
  getValue: (c: StatRangeCombo | undefined) => number;
  getColor: (val: number) => string;
  formatCell: (c: StatRangeCombo | undefined) => string;
  label: string;
  formatTooltip: (key: string, c: StatRangeCombo | undefined) => string;
  textColor?: (val: number) => string;
}) {
  return (
    <div className="flex-1 min-w-0">
      <div className="text-[11px] text-text-muted mb-0.5 text-center font-medium">{label}</div>
      <div className="grid gap-[1px]" style={{ gridTemplateColumns: 'repeat(13, 1fr)' }}>
        {RANKS.map((_, row) =>
          RANKS.map((_, col) => {
            const key = comboKey(row, col);
            const combo = comboMap.get(key);
            const val = getValue(combo);
            const bg = getColor(val);
            const cellText = formatCell(combo);
            const color = textColor?.(val);
            const isPair = row === col;
            const isSuited = col > row;
            return (
              <div
                key={`${row}-${col}`}
                className="flex flex-col items-center justify-center rounded-[2px] overflow-hidden"
                style={{ background: bg, aspectRatio: '4 / 5' }}
                title={formatTooltip(key, combo)}
              >
                <span className={`text-[8px] leading-none font-mono ${
                  isPair ? 'text-yellow-400/90' : isSuited ? 'text-primary/80' : 'text-text-muted/60'
                }`}>
                  {key}
                </span>
                {cellText && (
                  <span
                    className="text-[8px] leading-none font-mono font-semibold mt-[1px]"
                    style={{ color: color ?? 'rgba(255,255,255,0.9)' }}
                  >
                    {cellText}
                  </span>
                )}
              </div>
            );
          }),
        )}
      </div>
    </div>
  );
}

export default function RangeHeatmapMini({ statKey, filterParams, position }: RangeHeatmapMiniProps) {
  const [expanded, setExpanded] = useState(false);

  const rangeParams = useMemo(() => ({
    position,
    stakes: filterParams.stakes,
    game_mode: filterParams.game_mode,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
  }), [position, filterParams]);

  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.statRange(statKey, rangeParams),
    queryFn: ({ signal }) => getStatRange(statKey, rangeParams, signal),
    enabled: expanded,
  });

  const comboMap = useMemo(() => {
    if (!data) return new Map<string, StatRangeCombo>();
    const m = new Map<string, StatRangeCombo>();
    for (const c of data.combos) m.set(c.combo, c);
    return m;
  }, [data]);

  const { activeCombos, maxActionFreq, maxFoldFreq } = useMemo(() => {
    let count = 0;
    let maf = 0;
    let mff = 0;
    for (const c of comboMap.values()) {
      if (c.actions > 0) count++;
      if (c.hands > 0) {
        maf = Math.max(maf, c.actions / c.hands);
        mff = Math.max(mff, (c.hands - c.actions) / c.hands);
      }
    }
    return { activeCombos: count, maxActionFreq: maf || 1, maxFoldFreq: mff || 1 };
  }, [comboMap]);

  // Range % = actual action frequency, not combo count / 169
  const rangePct = data && data.total_hands > 0
    ? (data.total_actions / data.total_hands * 100).toFixed(1)
    : '—';

  const actionFreqColor = (val: number) => {
    if (val === 0) return 'rgba(255,255,255,0.02)';
    const i = Math.min(val / maxActionFreq, 1);
    return `rgba(99, 102, 241, ${(i * 0.55 + 0.1).toFixed(2)})`;
  };

  const foldFreqColor = (val: number) => {
    if (val === 0) return 'rgba(255,255,255,0.02)';
    const i = Math.min(val / maxFoldFreq, 1);
    return `rgba(239, 68, 68, ${(i * 0.4 + 0.08).toFixed(2)})`;
  };

  const bb100Color = (val: number) => {
    if (val === 0) return 'rgba(255,255,255,0.03)';
    const clamp = Math.min(Math.abs(val) / 150, 1);
    const alpha = (clamp * 0.45 + 0.12).toFixed(2);
    return val > 0 ? `rgba(22, 163, 74, ${alpha})` : `rgba(220, 38, 38, ${alpha})`;
  };

  const bb100TextColor = (val: number) => {
    if (val > 0) return 'rgba(134, 239, 172, 0.95)';
    if (val < 0) return 'rgba(252, 165, 165, 0.95)';
    return 'rgba(255,255,255,0.4)';
  };

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-text-muted hover:text-text w-full"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Range Heatmap
        {data && (
          <span className="ml-auto font-mono">
            {activeCombos} combos, {rangePct}%
          </span>
        )}
      </button>

      {expanded && (
        <div className="mt-1">
          {isPending ? (
            <Skeleton className="h-[200px] w-full" />
          ) : data ? (
            <div className="flex gap-3">
              {/* Grid 1: Overall bb/100 */}
              <MiniGrid
                comboMap={comboMap}
                label="bb/100"
                getValue={(c) => c ? c.total_bb_per_100 : 0}
                getColor={bb100Color}
                formatCell={(c) => c && c.hands > 0 ? fmtBb(c.total_bb_per_100) : ''}
                textColor={bb100TextColor}
                formatTooltip={(key, c) =>
                  c && c.hands > 0
                    ? `${key}: ${c.total_bb_per_100 >= 0 ? '+' : ''}${c.total_bb_per_100} bb/100 (${c.hands}h)`
                    : `${key}: no data`
                }
              />
              {/* Grid 2: Action counts */}
              <MiniGrid
                comboMap={comboMap}
                label="Raise"
                getValue={(c) => c && c.hands > 0 ? c.actions / c.hands : 0}
                getColor={actionFreqColor}
                formatCell={(c) => c ? fmtCount(c.actions) : ''}
                formatTooltip={(key, c) =>
                  c && c.actions > 0
                    ? `${key}: raise ${(c.actions / c.hands * 100).toFixed(0)}% (${c.actions}/${c.hands})`
                    : `${key}: no raises`
                }
              />
              {/* Grid 3: Fold counts */}
              <MiniGrid
                comboMap={comboMap}
                label="Fold"
                getValue={(c) => c && c.hands > 0 ? (c.hands - c.actions) / c.hands : 0}
                getColor={foldFreqColor}
                formatCell={(c) => {
                  if (!c) return '';
                  return fmtCount(c.hands - c.actions);
                }}
                formatTooltip={(key, c) => {
                  if (!c || c.hands === 0) return `${key}: no data`;
                  const folds = c.hands - c.actions;
                  return `${key}: fold ${(folds / c.hands * 100).toFixed(0)}% (${folds}/${c.hands})`;
                }}
              />
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
