import { useState, useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getRangeStats } from '@/lib/api';
import type { ComboStats } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';
import { ChevronDown, ChevronRight } from 'lucide-react';

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

// Stats that have meaningful range heatmap data
const RANGE_STAT_METRIC: Record<string, (c: ComboStats) => number> = {
  vpip: (c) => c.hands > 0 ? c.vpip / c.hands * 100 : 0,
  pfr: (c) => c.hands > 0 ? c.pfr / c.hands * 100 : 0,
  open_raise: (c) => c.hands > 0 ? c.pfr / c.hands * 100 : 0,
  three_bet: (c) => c.hands > 0 ? c.three_bet / c.hands * 100 : 0,
  three_bet_ip: (c) => c.hands > 0 ? c.three_bet / c.hands * 100 : 0,
  three_bet_oop: (c) => c.hands > 0 ? c.three_bet / c.hands * 100 : 0,
  four_bet: (c) => c.hands > 0 ? c.pfr / c.hands * 100 : 0,
  call_open_raise: (c) => c.hands > 0 ? (c.vpip - c.pfr) / c.hands * 100 : 0,
  limp: (c) => c.hands > 0 ? (c.vpip - c.pfr) / c.hands * 100 : 0,
  fold_to_3bet: (c) => c.hands > 0 ? c.pfr / c.hands * 100 : 0,
  fold_to_4bet: (c) => c.hands > 0 ? c.three_bet / c.hands * 100 : 0,
};

function comboKey(row: number, col: number): string {
  const r1 = RANKS[row];
  const r2 = RANKS[col];
  if (row === col) return r1 + r2;
  if (col > row) return r1 + r2 + 's';
  return r2 + r1 + 'o';
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

export default function RangeHeatmapMini({ statKey, filterParams, position }: RangeHeatmapMiniProps) {
  const [expanded, setExpanded] = useState(false);
  const metricFn = RANGE_STAT_METRIC[statKey];

  const rangeParams = useMemo(() => ({
    position,
    stakes: filterParams.stakes,
    game_mode: filterParams.game_mode,
    date_from: filterParams.date_from,
    date_to: filterParams.date_to,
  }), [position, filterParams]);

  const { data, isPending } = useQuery({
    queryKey: queryKeys.range(rangeParams),
    queryFn: () => getRangeStats(rangeParams),
    enabled: expanded && !!metricFn,
  });

  const comboMap = useMemo(() => {
    if (!data) return new Map<string, ComboStats>();
    const m = new Map<string, ComboStats>();
    for (const c of data.combos) m.set(c.combo, c);
    return m;
  }, [data]);

  const { combosWithData, maxVal } = useMemo(() => {
    if (!metricFn) return { combosWithData: 0, maxVal: 1 };
    let count = 0;
    let max = 0;
    for (let row = 0; row < 13; row++) {
      for (let col = 0; col < 13; col++) {
        const combo = comboMap.get(comboKey(row, col));
        if (combo && combo.hands > 0) {
          count++;
          max = Math.max(max, metricFn(combo));
        }
      }
    }
    return { combosWithData: count, maxVal: max || 1 };
  }, [comboMap, metricFn]);

  if (!metricFn) return null;

  const rangePct = data ? (combosWithData / 169 * 100).toFixed(0) : '—';

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
            {combosWithData} combos, {rangePct}% range
          </span>
        )}
      </button>

      {expanded && (
        <div className="mt-1">
          {isPending ? (
            <Skeleton className="h-[180px] w-full" />
          ) : data ? (
            <div
              className="grid gap-[1px]"
              style={{ gridTemplateColumns: 'repeat(13, 1fr)' }}
            >
              {RANKS.map((_, row) =>
                RANKS.map((_, col) => {
                  const key = comboKey(row, col);
                  const combo = comboMap.get(key);
                  const val = combo ? metricFn(combo) : 0;
                  const intensity = maxVal > 0 ? Math.min(val / maxVal, 1) : 0;
                  const alpha = (intensity * 0.55 + 0.05).toFixed(2);
                  const bg = val > 0 ? `rgba(99, 102, 241, ${alpha})` : 'rgba(255,255,255,0.02)';
                  const isPair = row === col;
                  const isSuited = col > row;
                  return (
                    <div
                      key={key}
                      className="aspect-square flex items-center justify-center rounded-[2px]"
                      style={{ background: bg }}
                      title={`${key}: ${combo ? `${val.toFixed(1)}% (${combo.hands}h)` : 'No data'}`}
                    >
                      <span className={`text-[7px] leading-none font-mono ${
                        isPair ? 'text-yellow-400/80' : isSuited ? 'text-primary/70' : 'text-text-muted/50'
                      } ${(!combo || combo.hands < 3) ? 'opacity-40' : ''}`}>
                        {key}
                      </span>
                    </div>
                  );
                }),
              )}
            </div>
          ) : null}
        </div>
      )}
    </div>
  );
}
