import { queryOptions } from '@tanstack/react-query';
import { getHandDetail } from '@/lib/api';
import { queryKeys } from '@/lib/query-keys';

/**
 * Cache key of one hand's detail for a row player (`null`: the hero). The panel, quick replay, history dialog,
 * drawer and Copy Hand History all read this one entry, so a hand opened in one is instant in the others.
 */
export function handDetailKey(handId: string, playerId?: number) {
  return [...queryKeys.hands.detail(handId), playerId ?? null] as const;
}

/** Query options of a hand's detail (callers may override `staleTime`). */
export function handDetailQuery(handId: string, playerId?: number) {
  return queryOptions({
    queryKey: handDetailKey(handId, playerId),
    queryFn: ({ signal }) => getHandDetail(handId, playerId, signal),
  });
}
