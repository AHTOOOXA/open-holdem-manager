import { useQuery } from '@tanstack/react-query';
import { getRangeStats } from '@/lib/api';
import type { ComboStats } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
}

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

function comboKey(r: number, c: number): string {
  if (r === c) return RANKS[r] + RANKS[c];
  if (r < c) return RANKS[r] + RANKS[c] + 's';
  return RANKS[c] + RANKS[r] + 'o';
}

function MiniGrid({ combos, label }: { combos: ComboStats[]; label: string }) {
  const comboMap = new Map(combos.map(c => [c.combo, c]));

  return (
    <div className="flex-1 min-w-0">
      <div className="text-[10px] text-muted-foreground mb-0.5 text-center">{label}</div>
      <div className="grid gap-px" style={{ gridTemplateColumns: 'repeat(13, 1fr)' }}>
        {RANKS.map((_, r) =>
          RANKS.map((_, c) => {
            const key = comboKey(r, c);
            const combo = comboMap.get(key);
            const intensity = combo ? Math.min(combo.three_bet / Math.max(combo.hands, 1), 1) : 0;
            const bg = intensity > 0
              ? `rgba(99, 102, 241, ${0.2 + intensity * 0.8})`
              : 'transparent';
            return (
              <div
                key={`${r}-${c}`}
                className="aspect-square flex items-center justify-center text-[6px] text-white/70 rounded-sm"
                style={{ backgroundColor: bg, minWidth: 0 }}
                title={combo ? `${key}: ${combo.hands} hands, 3b ${(combo.three_bet / Math.max(combo.hands, 1) * 100).toFixed(0)}%` : key}
              />
            );
          })
        )}
      </div>
    </div>
  );
}

export default function RangeComparison({ filterParams }: Props) {
  // Fetch IP positions (CO, BTN) and OOP positions (EP, MP, SB, BB) separately
  const ipParams = { ...filterParams, position: 'BTN' }; // simplified: BTN as IP example
  const oopParams = { ...filterParams, position: 'SB' }; // simplified: SB as OOP example

  const { data: ipData, isPending: ipLoading } = useQuery({
    queryKey: queryKeys.range({ ...ipParams, label: 'ip' }),
    queryFn: () => getRangeStats(ipParams),
  });
  const { data: oopData, isPending: oopLoading } = useQuery({
    queryKey: queryKeys.range({ ...oopParams, label: 'oop' }),
    queryFn: () => getRangeStats(oopParams),
  });

  if (ipLoading || oopLoading) return <Skeleton className="h-36 w-full" />;
  if (!ipData && !oopData) return null;

  return (
    <div>
      <div className="text-[11px] text-muted-foreground mb-1">Range Comparison</div>
      <div className="flex gap-2">
        <MiniGrid combos={ipData?.combos ?? []} label="IP (BTN)" />
        <MiniGrid combos={oopData?.combos ?? []} label="OOP (SB)" />
      </div>
    </div>
  );
}
