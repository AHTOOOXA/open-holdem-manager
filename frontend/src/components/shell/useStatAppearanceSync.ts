import { useEffect } from 'react';
import { useQuery } from '@tanstack/react-query';
import { configQueryKey, getConfig } from '@/lib/config/api';
import type { StatAppearance } from '@/lib/config/types';
import { setStatAppearance } from '@/lib/format';
import { cacheAppearance, restoreCachedAppearance } from '@/lib/format/appearance-cache';

// Format like the saved settings from the very first render (the server value follows)
restoreCachedAppearance();

function isAppearance(v: unknown): v is StatAppearance {
  return typeof v === 'object' && v !== null && typeof (v as StatAppearance).one_decimal_below === 'number';
}

/**
 * Loads Configuration > Stat Appearance and applies it to the number formatters (lib/format/h2n.ts).
 * Components that format stats subscribe with `useStatAppearanceVersion` and re-render in place.
 */
export function useStatAppearanceSync(): void {
  const { data } = useQuery({
    queryKey: configQueryKey('stat_appearance'),
    queryFn: () => getConfig<StatAppearance>('stat_appearance'),
    staleTime: Infinity,
    retry: false,
  });
  useEffect(() => {
    if (isAppearance(data?.value)) {
      setStatAppearance(data.value);
      cacheAppearance(data.value);
    }
  }, [data]);
}
