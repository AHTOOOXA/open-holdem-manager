import { useState } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getContinuingRange } from '@/lib/api';
import type { ContinuingCombo } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';
import { Skeleton } from '@/components/ui/skeleton';
import { ChevronDown, ChevronRight } from 'lucide-react';

interface Props {
  statKey: string;
  filterParams: { position?: string; stakes?: string; game_mode?: string; date_from?: string; date_to?: string };
  position?: string;
}

const RANKS = ['A', 'K', 'Q', 'J', 'T', '9', '8', '7', '6', '5', '4', '3', '2'];

function comboKey(r: number, c: number): string {
  if (r === c) return RANKS[r] + RANKS[c];
  if (r < c) return RANKS[r] + RANKS[c] + 's';
  return RANKS[c] + RANKS[r] + 'o';
}

function getColor(combo: ContinuingCombo | undefined): string {
  if (!combo || combo.total === 0) return 'transparent';
  const foldPct = combo.fold / combo.total;
  const raisePct = combo.raise_count / combo.total;
  if (foldPct > 0.6) return '#374151'; // gray
  if (raisePct > 0.4) return '#dc2626'; // red
  return '#3b82f6'; // blue for call
}

export default function ContinuingRangeHeatmap({ statKey, filterParams, position }: Props) {
  const [expanded, setExpanded] = useState(false);
  const params = { ...filterParams, position };
  const { data, isPending } = useQuery({
    queryKey: queryKeys.stats.continuingRange(statKey, params),
    queryFn: ({ signal }) => getContinuingRange(statKey, params, signal),
    enabled: expanded,
  });

  return (
    <div>
      <button
        onClick={() => setExpanded(!expanded)}
        className="flex items-center gap-1 text-[11px] text-muted-foreground hover:text-foreground"
      >
        {expanded ? <ChevronDown className="w-3 h-3" /> : <ChevronRight className="w-3 h-3" />}
        Continuing Range
      </button>
      {expanded && (
        isPending ? <Skeleton className="h-40 w-full mt-1" /> : (
          <div className="mt-1">
            {(!data || data.combos.length === 0) ? (
              <div className="text-[10px] text-muted-foreground">No hole card data</div>
            ) : (
              <>
                <div className="grid gap-px" style={{ gridTemplateColumns: `repeat(13, 1fr)` }}>
                  {RANKS.map((_, r) =>
                    RANKS.map((_, c) => {
                      const key = comboKey(r, c);
                      const combo = data.combos.find(x => x.combo === key);
                      return (
                        <div
                          key={`${r}-${c}`}
                          className="aspect-square flex items-center justify-center text-[7px] text-white rounded-sm cursor-default"
                          style={{ backgroundColor: getColor(combo), minWidth: 0 }}
                          title={combo ? `${key}: F${combo.fold} C${combo.call} R${combo.raise_count}` : key}
                        >
                          {key.length <= 3 ? key : ''}
                        </div>
                      );
                    })
                  )}
                </div>
                <div className="flex gap-3 mt-1 text-[9px] text-muted-foreground">
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#374151' }} />Fold</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#3b82f6' }} />Call</span>
                  <span className="flex items-center gap-1"><span className="w-2 h-2 rounded-sm" style={{ background: '#dc2626' }} />Raise</span>
                </div>
              </>
            )}
          </div>
        )
      )}
    </div>
  );
}
