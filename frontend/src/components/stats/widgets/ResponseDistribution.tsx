import type { ResponseDistributionData } from '@/lib/api';
import { Skeleton } from '@/components/ui/skeleton';

interface ResponseDistributionProps {
  distribution: ResponseDistributionData | null;
  isLoading: boolean;
}

export default function ResponseDistribution({ distribution, isLoading }: ResponseDistributionProps) {
  if (isLoading) return <Skeleton className="h-[40px] w-full" />;
  if (!distribution || distribution.total === 0) return null;

  const { fold_pct, call_pct, raise_pct, fold_count, call_count, raise_count } = distribution;

  const segments = [
    { label: 'Fold', pct: fold_pct, count: fold_count, color: 'bg-text-muted/40', textColor: 'text-text-muted' },
    { label: 'Call', pct: call_pct, count: call_count, color: 'bg-primary/60', textColor: 'text-primary' },
    { label: 'Raise', pct: raise_pct, count: raise_count, color: 'bg-red/60', textColor: 'text-red' },
  ];

  return (
    <div>
      {/* Labels */}
      <div className="flex justify-between text-[11px] mb-1">
        {segments.map((s) => (
          <span key={s.label} className={s.textColor}>
            {s.label} {s.pct.toFixed(0)}%
            <span className="text-text-muted/60 ml-0.5">({s.count})</span>
          </span>
        ))}
      </div>
      {/* Stacked bar */}
      <div className="flex h-[14px] rounded-sm overflow-hidden gap-[1px]">
        {segments.map((s) =>
          s.pct > 0 ? (
            <div
              key={s.label}
              className={`${s.color} transition-all`}
              style={{ width: `${s.pct}%` }}
            />
          ) : null,
        )}
      </div>
    </div>
  );
}
