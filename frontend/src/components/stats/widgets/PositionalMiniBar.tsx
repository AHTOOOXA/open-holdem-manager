import type { PositionalStats } from '@/lib/api';
import { BENCHMARKS, getStatHealth } from '@/lib/benchmarks';

const POSITIONS = ['EP', 'MP', 'CO', 'BTN', 'SB', 'BB'] as const;
type Pos = (typeof POSITIONS)[number];

interface PositionalMiniBarProps {
  positionalStats: PositionalStats;
  statKey: string;
  currentPosition?: string;
  onPositionClick: (pos: string) => void;
}

function barColor(statKey: string, pos: Pos, value: number | null, sample: number): string {
  const benchmarks = BENCHMARKS[statKey];
  const bench = benchmarks?.[pos.toLowerCase() as keyof typeof benchmarks] ?? benchmarks?.total;
  if (!bench) return 'bg-primary/60';
  const health = getStatHealth(value, bench, sample, 30);
  if (health.status === 'green') return 'bg-green/70';
  if (health.status === 'yellow') return 'bg-yellow-500/60';
  if (health.status === 'red') return 'bg-red/70';
  return 'bg-primary/50';
}

export default function PositionalMiniBar({
  positionalStats,
  statKey,
  currentPosition,
  onPositionClick,
}: PositionalMiniBarProps) {
  const values = POSITIONS.map((pos) => {
    const sv = positionalStats[pos.toLowerCase() as keyof PositionalStats] as { value: number | null; sample: number };
    return { pos, value: sv.value, sample: sv.sample };
  });

  const maxVal = Math.max(...values.map((v) => Math.abs(v.value ?? 0)), 1);

  return (
    <div className="flex flex-col gap-[3px]">
      {values.map(({ pos, value, sample }) => {
        const isActive = currentPosition?.toUpperCase() === pos;
        const pct = value != null ? Math.abs(value) / maxVal * 100 : 0;
        return (
          <button
            key={pos}
            onClick={() => onPositionClick(pos)}
            className={`flex items-center gap-1.5 h-[18px] rounded-sm transition-colors group ${
              isActive ? 'bg-primary/10 ring-1 ring-primary/30' : 'hover:bg-surface-hover'
            }`}
          >
            <span className="w-7 text-[11px] text-text-muted text-right font-mono shrink-0">
              {pos}
            </span>
            <div className="flex-1 h-[10px] bg-border/30 rounded-sm overflow-hidden">
              <div
                className={`h-full rounded-sm transition-all ${barColor(statKey, pos, value, sample)}`}
                style={{ width: `${pct}%` }}
              />
            </div>
            <span className="w-10 text-[11px] text-text-muted text-right font-mono shrink-0">
              {value != null ? `${value.toFixed(1)}%` : '\u2014'}
            </span>
          </button>
        );
      })}
    </div>
  );
}
