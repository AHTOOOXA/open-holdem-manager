import { useMemo } from 'react';
import { useQuery } from '@tanstack/react-query';
import { getDrift } from '@/lib/api';
import type { DriftStat } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

export interface UseDriftResult {
  driftMap: Map<string, DriftStat>;
  stats: DriftStat[];
  totalHands: number;
}

export function useDrift(params: {
  stakes?: string;
  game_mode?: string;
  date_from?: string;
  date_to?: string;
  enabled?: boolean;
}): UseDriftResult {
  const { stakes, game_mode, date_from, date_to, enabled = true } = params;

  const filterParams = useMemo(() => ({
    stakes,
    game_mode,
    date_from,
    date_to,
  }), [stakes, game_mode, date_from, date_to]);

  const { data } = useQuery({
    queryKey: queryKeys.drift(filterParams),
    queryFn: () => getDrift(filterParams),
    enabled,
  });

  const driftMap = useMemo(() => {
    const map = new Map<string, DriftStat>();
    if (data?.stats) {
      for (const s of data.stats) {
        map.set(s.stat, s);
      }
    }
    return map;
  }, [data]);

  return {
    driftMap,
    stats: data?.stats ?? [],
    totalHands: data?.total_hands ?? 0,
  };
}
