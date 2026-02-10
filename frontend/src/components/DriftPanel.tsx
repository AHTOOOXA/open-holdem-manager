import type { DriftStat } from '@/lib/api';
import { getBenchmarkForPosition } from '@/lib/benchmarks';
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from '@/components/ui/tooltip';

/** Drift stat key → display name mapping (drift uses DB column names) */
const DRIFT_DISPLAY: Record<string, string> = {
  vpip: 'VPIP',
  pfr: 'PFR',
  three_bet: '3-Bet',
  fold_to_3bet: 'Fold to 3-Bet',
  cbet_flop: 'C-Bet Flop',
  fold_to_cbet_flop: 'Fold to CBet Flop',
  went_to_showdown: 'WTSD',
  won_at_showdown: 'W$SD',
  steal: 'Steal',
  fold_to_steal: 'Fold to Steal',
  wwsf: 'WWSF',
  afq_flop: 'AFq Flop',
};

/** Map drift stat to benchmark key for midpoint comparison */
const DRIFT_TO_BENCHMARK: Record<string, string> = {
  vpip: 'vpip',
  pfr: 'pfr',
  three_bet: 'three_bet',
  fold_to_3bet: 'fold_to_3bet',
  cbet_flop: 'cbet_flop',
  fold_to_cbet_flop: 'fold_to_cbet_flop',
  went_to_showdown: 'wtsd',
  won_at_showdown: 'wsd',
  steal: 'steal',
  fold_to_steal: 'vs_steal_fold',
  wwsf: 'wwsf',
};

function DriftStatCard({ drift }: { drift: DriftStat }) {
  const displayName = DRIFT_DISPLAY[drift.stat] || drift.stat;
  const arrow = drift.direction === 'up' ? '\u2191' : '\u2193';

  // Color: green if drifting toward benchmark, red if away
  let arrowColor = 'text-yellow';
  const benchKey = DRIFT_TO_BENCHMARK[drift.stat];
  if (benchKey) {
    const benchmark = getBenchmarkForPosition(benchKey);
    if (benchmark) {
      const midpoint = (benchmark.low + benchmark.high) / 2;
      const lifetimeDist = Math.abs(drift.lifetime_avg - midpoint);
      const windowDist = Math.abs(drift.window_avg - midpoint);
      arrowColor = windowDist < lifetimeDist ? 'text-green' : 'text-red';
    }
  }

  return (
    <Tooltip>
      <TooltipTrigger asChild>
        <div className="flex items-center gap-2 px-2.5 py-1.5 bg-surface rounded border border-border cursor-help">
          <span className={`text-[16px] font-bold ${arrowColor}`}>{arrow}</span>
          <div className="min-w-0">
            <div className="text-[12px] font-semibold text-text">{displayName}</div>
            <div className="text-[11px] text-text-muted">
              {drift.lifetime_avg.toFixed(1)}% &rarr; {drift.window_avg.toFixed(1)}%
            </div>
          </div>
        </div>
      </TooltipTrigger>
      <TooltipContent side="bottom" className="max-w-[260px] text-xs">
        <div className="space-y-1">
          <div className="font-semibold">{drift.interpretation}</div>
          <div className="text-text-muted">
            Lifetime: {drift.lifetime_avg.toFixed(1)}% ({drift.lifetime_n.toLocaleString()} opp)
          </div>
          <div className="text-text-muted">
            Recent {drift.window_n.toLocaleString()} opp: {drift.window_avg.toFixed(1)}%
            {' '}({drift.ci_lower.toFixed(1)}–{drift.ci_upper.toFixed(1)}%)
          </div>
        </div>
      </TooltipContent>
    </Tooltip>
  );
}

export default function DriftPanel({ stats, totalHands }: {
  stats: DriftStat[];
  totalHands: number;
}) {
  if (totalHands < 20000 || stats.length === 0) return null;

  return (
    <div className="border border-border rounded overflow-hidden mb-3">
      <div className="px-3 py-2 bg-surface flex items-center gap-2">
        <span className="text-[13px] font-bold text-text">Strategy Drift</span>
        <span className="text-[11px] text-text-muted">Recent play differs from your lifetime averages</span>
      </div>
      <div className="px-3 py-2">
        <div className="flex flex-wrap gap-2">
          {[...stats]
            .sort((a, b) => Math.abs(b.drift_pct) - Math.abs(a.drift_pct))
            .map((d) => (
              <DriftStatCard key={d.stat} drift={d} />
            ))}
        </div>
      </div>
    </div>
  );
}
