import { useState, useEffect, useMemo } from 'react';
import { getDrift } from '@/lib/api';
import type { DriftStat, DriftResponse } from '@/lib/api';

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
  const [data, setData] = useState<DriftResponse | null>(null);

  useEffect(() => {
    if (!enabled) return;

    let cancelled = false;

    getDrift({ stakes, game_mode, date_from, date_to })
      .then((resp) => { if (!cancelled) setData(resp); })
      .catch(() => { if (!cancelled) setData(null); });

    return () => { cancelled = true; };
  }, [stakes, game_mode, date_from, date_to, enabled]);

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
