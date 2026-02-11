import { ResponsiveContainer, LineChart, Line, ReferenceLine, Tooltip } from 'recharts';
import type { TrendPoint } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface TrendSparklineProps {
  points: TrendPoint[];
  overallPct: number;
  isLoading: boolean;
}

function CustomTooltip({ active, payload }: { active?: boolean; payload?: Array<{ payload: TrendPoint }> }) {
  if (!active || !payload?.[0]) return null;
  const pt = payload[0].payload;
  return (
    <div className="bg-surface border border-border rounded px-2 py-1 text-[11px] text-text shadow-md">
      Hand #{pt.hand_number}: {pt.rolling_pct.toFixed(1)}%
    </div>
  );
}

export default function TrendSparkline({ points, overallPct, isLoading }: TrendSparklineProps) {
  if (isLoading) return <Skeleton className="h-[50px] w-full" />;
  if (!points.length) return null;

  return (
    <div className="h-[50px] w-full">
      <ResponsiveContainer width="100%" height="100%">
        <LineChart data={points} margin={{ top: 4, right: 4, bottom: 4, left: 4 }}>
          <Line
            type="monotone"
            dataKey="rolling_pct"
            stroke="#6366f1"
            strokeWidth={1.5}
            dot={false}
            isAnimationActive={false}
          />
          <ReferenceLine
            y={overallPct}
            stroke="#6366f1"
            strokeDasharray="4 3"
            strokeOpacity={0.4}
          />
          <Tooltip
            content={<CustomTooltip />}
            cursor={false}
          />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
