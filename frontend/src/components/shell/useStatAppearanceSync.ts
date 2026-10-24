import { useEffect, useSyncExternalStore } from 'react';
import { useQuery } from '@tanstack/react-query';
import { configQueryKey, getConfig } from '@/lib/config/api';
import type { StatAppearance } from '@/lib/config/types';
import { getStatAppearanceVersion, setStatAppearance, subscribeStatAppearance } from '@/lib/format';

function isAppearance(v: unknown): v is StatAppearance {
  return typeof v === 'object' && v !== null && typeof (v as StatAppearance).one_decimal_below === 'number';
}

/**
 * Loads Configuration > Stat Appearance and applies it to the number formatters (lib/format/h2n.ts).
 * Returns a version that changes when the formatting rules change, so a screen can remount and
 * re-render its numbers.
 */
export function useStatAppearanceSync(): number {
  const { data } = useQuery({
    queryKey: configQueryKey('stat_appearance'),
    queryFn: () => getConfig<StatAppearance>('stat_appearance'),
    staleTime: Infinity,
    retry: false,
  });
  useEffect(() => {
    if (isAppearance(data?.value)) setStatAppearance(data.value);
  }, [data]);
  return useSyncExternalStore(subscribeStatAppearance, getStatAppearanceVersion);
}
